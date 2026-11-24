"""
SEPA/VCP Cloud Monitor — Corre grátis no GitHub Actions mesmo com o PC desligado!
Modos suportados:
  - alerts  : Alertas de Preço (alertas_cloud.json) + Mudança Semáforo Macro + IBD Distribution/FTD
  - full    : Tudo em alerts + Scanner Multi-Estratégia (Breakout VCP, Pocket Pivot, Episodic Pivot, Funding Extremo)
  - morning : Briefing Matinal estruturado (Macro + IBD + Breadth + Líderes + Cripto + Top 3 Setups do Dia)
  - weekly  : Resumo Semanal de Domingo (Rotação Semanal + 3 Weeks Tight + Cripto Derivados)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import db
from app.services.macro_rotation import compute_macro_and_rotation
from app.services.market_data import get_latest_price, is_crypto_ticker, normalize_ticker
from app.services.notifications import notification_service
from app.services.scanner_service import run_sepa_vcp_scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("cloud_monitor")

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "alertas_cloud.json"
DEFAULT_STATE_PATH = PROJECT_ROOT / "cloud_state.json"


def _load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(fallback)
    except Exception as exc:
        logger.warning("Erro ao ler %s: %s", path, exc)
        return dict(fallback)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_morning_briefing_message(macro: dict[str, Any], scan: dict[str, Any]) -> tuple[str, str, str]:
    """Formats a crisp, zero-spam Morning Briefing for Telegram/Discord."""
    tl = macro.get("macro_traffic_light") or {}
    ibd = macro.get("ibd_timing") or {}
    br = macro.get("market_breadth") or {}
    us_leaders = (macro.get("us_rotation") or {}).get("leaders") or []
    cr_deriv = macro.get("crypto_derivatives") or {}
    alt = cr_deriv.get("altseason") or {}

    regime = tl.get("regime", "CAUTELA")
    level = "success" if regime == "RISK_ON" else ("danger" if regime == "RISK_OFF" else "warning")
    spy_dist = (ibd.get("spy") or {}).get("distribution_days", 0)
    qqq_dist = (ibd.get("qqq") or {}).get("distribution_days", 0)

    leaders_txt = ", ".join(f"{s['ticker']} ({s['rs_1m']:+.1f}%)" for s in us_leaders[:3]) or "N/D"
    btc_funding = None
    for a in cr_deriv.get("assets") or []:
        if a.get("ticker") == "BTC-USD":
            btc_funding = a.get("funding_rate_pct")
            break

    top_setups = [
        o for o in (scan.get("opportunities") or [])
        if o.get("liquidity", {}).get("passed", True) and not o.get("earnings_within_14d")
    ][:3]

    setup_lines = []
    for o in top_setups:
        plan = o.get("trade_plan") or {}
        q = o.get("quant") or {}
        tags = ", ".join((q.get("active_tags") or [])[:2])
        tag_str = f" [{tags}]" if tags else ""
        setup_lines.append(
            f"• {o['ticker']} ({o['score']}/100){tag_str} — Pivô {plan.get('entry_pivot')} | "
            f"Stop -{plan.get('stop_loss_pct')}% | ADR {q.get('adr_pct_20d') or 'N/D'}%"
        )

    ftd_line = "\n🚀 FOLLOW-THROUGH DAY ativo no índice!" if ibd.get("any_ftd") else ""
    funding_str = f"{btc_funding:+.4f}%" if btc_funding is not None else "N/D"

    msg = (
        f"🚦 Macro: {tl.get('label')} ({tl.get('score')}/100)\n"
        f"📊 IBD Dist. Days: SPY {spy_dist} | QQQ {qqq_dist}{ftd_line}\n"
        f"📈 Breadth: {br.get('pct_above_sma50', 'N/D')}% > SMA50 | 4% Up/Down 5d: {br.get('up_4pct_5d', 0)}/{br.get('down_4pct_5d', 0)}\n"
        f"💰 Setores Líderes: {leaders_txt}\n"
        f"₿ Cripto: {alt.get('regime', 'N/D')} ({alt.get('altseason_index', 'N/D')}/100) | Funding BTC: {funding_str}\n\n"
        f"🎯 Top Setups p/ Vigiar Hoje:\n"
        + ("\n".join(setup_lines) if setup_lines else "• Sem setups fortes fora de earnings hoje.")
    )
    return "Briefing Matinal — SEPA/VCP Desk", msg, level


def build_weekly_summary_message(macro: dict[str, Any], scan: dict[str, Any]) -> tuple[str, str, str]:
    """Formats Sunday Weekly Review for Telegram/Discord (Sector Rotation + 3 Weeks Tight + Leaders)."""
    tl = macro.get("macro_traffic_light") or {}
    us_leaders = (macro.get("us_rotation") or {}).get("leaders") or []
    us_laggards = (macro.get("us_rotation") or {}).get("laggards") or []
    opps = scan.get("opportunities") or []

    wt3_tickers = [
        o["ticker"] for o in opps
        if o.get("quant", {}).get("three_weeks_tight", {}).get("detected") and o.get("trend_template", {}).get("passed")
    ][:5]
    s2_top = [o["ticker"] for o in opps if o.get("trend_template", {}).get("passed")][:6]

    msg = (
        f"📅 Revisão Semanal de Mercado\n"
        f"🚦 Regime: {tl.get('label')} ({tl.get('score')}/100)\n"
        f"🟢 Entradas de Capital: {', '.join(s['ticker'] for s in us_leaders[:3]) or 'N/D'}\n"
        f"🔴 Saídas de Capital: {', '.join(s['ticker'] for s in us_laggards[:3]) or 'N/D'}\n"
        f"🔥 Top Stage 2 (8/8): {', '.join(s2_top) if s2_top else 'Nenhum esta semana'}\n"
        f"🎯 3 Weeks Tight (prontos p/ 2ª feira): {', '.join(wt3_tickers) if wt3_tickers else 'Nenhum detetado'}"
    )
    return "Resumo Semanal — SEPA/VCP Desk", msg, "info"


def run_cloud_monitor(
    mode: str = "alerts",
    config_path: Path = DEFAULT_CONFIG_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
    send_test_ping: bool = False,
    dry_run: bool = False,
    price_overrides: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """Executes one cloud monitoring pass and dispatches smart Telegram/Discord alerts."""
    cfg = _load_json(
        config_path,
        {
            "check_macro_shift": True,
            "check_vcp_breakouts": True,
            "breakout_min_score": 70,
            "price_alerts": [],
            "custom_watchlist": [],
        },
    )
    state = _load_json(
        state_path,
        {
            "last_macro_regime": None,
            "triggered_price_alerts": {},
            "notified_breakouts": {},
            "notified_events": {},
            "last_run_utc": None,
        },
    )
    state.setdefault("triggered_price_alerts", {})
    state.setdefault("notified_breakouts", {})
    state.setdefault("notified_events", {})

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).isoformat()
    dispatched: list[dict[str, Any]] = []

    def _emit(title: str, message: str, level: str, category: str, ticker: Optional[str] = None):
        item = {"title": title, "message": message, "level": level, "category": category, "ticker": ticker}
        dispatched.append(item)
        if dry_run:
            logger.info("[DRY-RUN] %s | %s", title, message)
            return
        res = notification_service.dispatch(
            title=title,
            message=message,
            level=level,
            category=category,
            ticker=ticker,
            persist_alert=False,
        )
        logger.info("Notificação enviada (%s): telegram=%s discord=%s errors=%s", title, res["telegram"], res["discord"], res["errors"])

    if send_test_ping:
        _emit(
            title="Teste Cloud 24/7 (GitHub Actions)",
            message="O monitor gratuito na nuvem está ativo! Vais receber alertas aqui mesmo com o teu PC desligado.",
            level="success",
            category="CLOUD_TEST",
        )

    # --- Special Scheduled Digests: Morning Briefing & Sunday Weekly Summary ---
    if mode in ("morning", "weekly"):
        macro = compute_macro_and_rotation(force_refresh=True)
        scan = run_sepa_vcp_scan(asset_type=None, force_refresh=(mode == "weekly"))
        if mode == "morning":
            t, m, lv = build_morning_briefing_message(macro, scan)
            _emit(t, m, lv, "MORNING_BRIEFING")
        else:
            t, m, lv = build_weekly_summary_message(macro, scan)
            _emit(t, m, lv, "WEEKLY_SUMMARY")

        state["last_run_utc"] = now_iso
        if not dry_run:
            _save_json(state_path, state)
        return {
            "mode": mode,
            "macro_regime": macro.get("macro_traffic_light", {}).get("regime"),
            "dispatched_count": len(dispatched),
            "dispatched": dispatched,
            "dry_run": dry_run,
        }

    # --- 1. Custom Price Alerts from alertas_cloud.json ---
    price_cache: dict[str, float] = dict(price_overrides or {})
    price_alerts = cfg.get("price_alerts") or []
    checked_price_count = 0

    for alert in price_alerts:
        if not alert.get("enabled", True):
            continue
        raw_ticker = str(alert.get("ticker") or "").strip()
        if not raw_ticker:
            continue
        ticker = normalize_ticker(raw_ticker)
        cond = str(alert.get("condition") or "ABOVE").upper()
        try:
            target = float(alert["target_price"])
        except Exception:
            continue

        alert_id = str(alert.get("id") or f"{ticker}:{cond}:{target}")
        sig = f"{alert_id}|{ticker}|{cond}|{target}"
        if sig in state["triggered_price_alerts"]:
            continue

        checked_price_count += 1
        if ticker not in price_cache:
            px, _ = get_latest_price(ticker, force_refresh=True)
            if px is not None:
                price_cache[ticker] = px

        if ticker not in price_cache:
            continue

        live = float(price_cache[ticker])
        hit = (cond == "ABOVE" and live >= target) or (cond == "BELOW" and live <= target)
        if hit:
            state["triggered_price_alerts"][sig] = now_iso
            op_txt = "cruzou ACIMA de" if cond == "ABOVE" else "caiu ABAIXO de"
            notes = f"\nNota: {alert['notes']}" if alert.get("notes") else ""
            _emit(
                title=f"Alerta de Preço (Cloud): {ticker}",
                message=f"{ticker} {op_txt} {target} (Preço atual: {live:.4f}){notes}",
                level="success" if cond == "ABOVE" else "warning",
                category="PRICE_ALERT",
                ticker=ticker,
            )

    # --- 2. Macro Regime Shift + IBD Distribution / FTD + Extreme Crypto Funding ---
    macro_regime = None
    if cfg.get("check_macro_shift", True):
        try:
            macro = compute_macro_and_rotation(force_refresh=True)
            tl = macro["macro_traffic_light"]
            macro_regime = tl["regime"]
            prev_regime = state.get("last_macro_regime")
            state["last_macro_regime"] = macro_regime
            if prev_regime and prev_regime != macro_regime:
                level = "success" if macro_regime == "RISK_ON" else ("danger" if macro_regime == "RISK_OFF" else "warning")
                _emit(
                    title=f"Mudança Semáforo Macro: {prev_regime} → {macro_regime}",
                    message=f"Novo regime: {tl['label']} (Score {tl['score']}/100).\n{tl['guidance']}",
                    level=level,
                    category="MACRO_SHIFT",
                )

            # IBD Distribution Days >= 5 or Follow-Through Day alerts (max once/day)
            ibd = macro.get("ibd_timing") or {}
            if ibd.get("any_ftd") and state["notified_events"].get("IBD_FTD") != today_str:
                state["notified_events"]["IBD_FTD"] = today_str
                _emit(
                    title="IBD Follow-Through Day (Sinal de Fundo!)",
                    message=f"SPY: {(ibd.get('spy') or {}).get('ftd_date') or '—'} | QQQ: {(ibd.get('qqq') or {}).get('ftd_date') or '—'}. Confirmada entrada institucional em rally!",
                    level="success",
                    category="IBD_FTD",
                )
            elif ibd.get("max_distribution_days", 0) >= 5 and state["notified_events"].get("IBD_DIST") != today_str:
                state["notified_events"]["IBD_DIST"] = today_str
                _emit(
                    title=f"Alerta Distribuição Institucional ({ibd['max_distribution_days']} dias)",
                    message=f"SPY: {(ibd.get('spy') or {}).get('distribution_days', 0)} dias | QQQ: {(ibd.get('qqq') or {}).get('distribution_days', 0)} dias nos últimos 25 pregões. Reduz exposição e protege lucros!",
                    level="danger",
                    category="IBD_DISTRIBUTION",
                )

            # Extreme Crypto Funding Rate alerts (once/day per asset)
            for ext in (macro.get("crypto_derivatives") or {}).get("extreme_funding_alerts") or []:
                ev_key = f"FUNDING:{ext['ticker']}:{ext['code']}"
                if state["notified_events"].get(ev_key) != today_str:
                    state["notified_events"][ev_key] = today_str
                    _emit(
                        title=f"Funding Extremo ({ext['code']}): {ext['ticker']}",
                        message=ext["detail"],
                        level="warning" if ext["code"] == "EUFORIA" else "success",
                        category="CRYPTO_FUNDING",
                        ticker=ext["ticker"],
                    )
        except Exception as exc:
            logger.warning("Falha na verificação Macro: %s", exc)

    # --- 3. Full Multi-Strategy Scan (Breakout VCP + Episodic Pivot + Pocket Pivot + Earnings < 5d) ---
    breakouts_found: list[str] = []
    if mode == "full" and cfg.get("check_vcp_breakouts", True):
        try:
            for tk in cfg.get("custom_watchlist") or []:
                norm = normalize_ticker(str(tk))
                atype = "crypto" if is_crypto_ticker(norm) else "stock"
                db.upsert_watchlist_ticker(norm, atype, enabled=True)

            scan = run_sepa_vcp_scan(asset_type=None, force_refresh=True)
            min_score = float(cfg.get("breakout_min_score", 70))
            for opp in scan.get("opportunities") or []:
                if not opp.get("liquidity", {}).get("passed", True):
                    continue
                q = opp.get("quant") or {}
                is_breakout = opp.get("status") == "BREAKOUT"
                is_vcp_ready = opp.get("status") == "VCP_PRONTO" and opp.get("score", 0) >= max(min_score, 78)
                is_ep = bool(q.get("episodic_pivot", {}).get("detected"))
                is_pp = bool(q.get("pocket_pivot", {}).get("detected")) and opp.get("score", 0) >= max(min_score, 72)

                if not (is_breakout or is_vcp_ready or is_ep or is_pp):
                    continue
                if opp.get("score", 0) < min_score and not is_ep:
                    continue

                tk = opp["ticker"]
                if state["notified_breakouts"].get(tk) == today_str:
                    continue

                state["notified_breakouts"][tk] = today_str
                breakouts_found.append(tk)
                plan = opp.get("trade_plan") or {}
                vcp = opp.get("vcp") or {}
                earn_warn = (
                    f"\n⚠️ EARNINGS em {opp['days_to_earnings']} dias ({opp['next_earnings_date']})!"
                    if opp.get("earnings_within_14d")
                    else ""
                )
                label = (
                    "EPISODIC PIVOT"
                    if is_ep
                    else ("BREAKOUT VCP" if is_breakout else ("POCKET PIVOT" if is_pp else "VCP PRONTO (VDU)"))
                )
                _emit(
                    title=f"{label}: {tk} (Score {opp['score']}/100)",
                    message=(
                        f"Preço: {opp['price']} ({opp['daily_change_pct']:+.2f}%) | ADR: {q.get('adr_pct_20d') or 'N/D'}%\n"
                        f"Pivô: {plan.get('entry_pivot')} | Stop -{plan.get('stop_loss_pct')}% ({plan.get('stop_loss_price')})\n"
                        f"Alvos: 2R {plan.get('target_2r')} | 3R {plan.get('target_3r')} | Vol: {vcp.get('breakout_volume_ratio')}x"
                        f"{earn_warn}"
                    ),
                    level="success" if (is_breakout or is_ep) else "info",
                    category="BREAKOUT",
                    ticker=tk,
                )
        except Exception as exc:
            logger.warning("Falha no scan SEPA/VCP cloud: %s", exc)

    if len(state["notified_breakouts"]) > 100:
        state["notified_breakouts"] = {k: v for k, v in state["notified_breakouts"].items() if v == today_str}
    if len(state["notified_events"]) > 100:
        state["notified_events"] = {k: v for k, v in state["notified_events"].items() if v == today_str}

    state["last_run_utc"] = now_iso
    if not dry_run:
        _save_json(state_path, state)

    summary = {
        "mode": mode,
        "checked_price_alerts": checked_price_count,
        "macro_regime": macro_regime,
        "breakouts_notified": breakouts_found,
        "dispatched_count": len(dispatched),
        "dispatched": dispatched,
        "dry_run": dry_run,
    }
    logger.info("Monitor Cloud concluído: %s", json.dumps(summary, ensure_ascii=False))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="SEPA/VCP 24/7 Cloud Monitor (GitHub Actions)")
    parser.add_argument("--mode", choices=["alerts", "full", "morning", "weekly"], default="alerts")
    parser.add_argument("--test-ping", action="store_true", help="Envia mensagem de teste imediata")
    parser.add_argument("--dry-run", action="store_true", help="Não envia notificações externas nem altera cloud_state.json")
    args = parser.parse_args()

    has_tg = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    has_dc = bool(os.getenv("DISCORD_WEBHOOK_URL"))
    if not args.dry_run and not (has_tg or has_dc):
        logger.warning(
            "Nenhum canal configurado nas variáveis de ambiente (TELEGRAM_BOT_TOKEN/CHAT_ID ou DISCORD_WEBHOOK_URL)."
        )

    run_cloud_monitor(mode=args.mode, send_test_ping=args.test_ping, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
