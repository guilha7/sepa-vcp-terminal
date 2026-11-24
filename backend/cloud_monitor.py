"""
SEPA/VCP Cloud Monitor — Corre grátis no GitHub Actions mesmo com o PC desligado!
Verifica:
  1. Alertas de Preço definidos em alertas_cloud.json
  2. Mudanças no Semáforo Macro (Risk-On / Cautela / Risk-Off)
  3. Breakouts VCP com volume >= 1.5x (modo full)
Evita alertas repetidos guardando estado em cloud_state.json.
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


def run_cloud_monitor(
    mode: str = "alerts",
    config_path: Path = DEFAULT_CONFIG_PATH,
    state_path: Path = DEFAULT_STATE_PATH,
    send_test_ping: bool = False,
    dry_run: bool = False,
    price_overrides: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """
    Executes one cloud monitoring pass and dispatches Telegram/Discord alerts.
    Returns a summary dictionary of all checks and dispatched notifications.
    """
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
            "last_run_utc": None,
        },
    )
    state.setdefault("triggered_price_alerts", {})
    state.setdefault("notified_breakouts", {})

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

        # Build deterministic signature so editing target_price re-arms the alert automatically!
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
            logger.warning("Preço indisponível para %s", ticker)
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

    # --- 2. Macro Regime Shift Check ---
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
        except Exception as exc:
            logger.warning("Falha na verificação Macro: %s", exc)

    # --- 3. Full SEPA/VCP Breakout Scan (in 'full' mode) ---
    breakouts_found: list[str] = []
    if mode == "full" and cfg.get("check_vcp_breakouts", True):
        try:
            # Include any custom watchlist tickers defined in alertas_cloud.json
            for tk in cfg.get("custom_watchlist") or []:
                norm = normalize_ticker(str(tk))
                atype = "crypto" if is_crypto_ticker(norm) else "stock"
                db.upsert_watchlist_ticker(norm, atype, enabled=True)

            scan = run_sepa_vcp_scan(asset_type=None, force_refresh=True)
            min_score = float(cfg.get("breakout_min_score", 70))
            for opp in scan.get("opportunities") or []:
                if not opp.get("liquidity", {}).get("passed", True):
                    continue
                is_breakout = opp.get("status") == "BREAKOUT"
                is_vcp_ready = opp.get("status") == "VCP_PRONTO" and opp.get("score", 0) >= max(min_score, 78)
                if not (is_breakout or is_vcp_ready):
                    continue
                if opp.get("score", 0) < min_score:
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
                label = "BREAKOUT VCP" if is_breakout else "VCP PRONTO (VDU)"
                _emit(
                    title=f"{label}: {tk} (Score {opp['score']}/100)",
                    message=(
                        f"Preço: {opp['price']} ({opp['daily_change_pct']:+.2f}%) | "
                        f"Pivô: {plan.get('entry_pivot')} | Stop -{plan.get('stop_loss_pct')}% ({plan.get('stop_loss_price')})\n"
                        f"Alvos: 2R {plan.get('target_2r')} | 3R {plan.get('target_3r')} | Vol: {vcp.get('breakout_volume_ratio')}x"
                        f"{earn_warn}"
                    ),
                    level="success" if is_breakout else "info",
                    category="BREAKOUT",
                    ticker=tk,
                )
        except Exception as exc:
            logger.warning("Falha no scan SEPA/VCP cloud: %s", exc)

    # Prune old breakout dates (> 14 entries keep recent)
    if len(state["notified_breakouts"]) > 100:
        state["notified_breakouts"] = {k: v for k, v in state["notified_breakouts"].items() if v == today_str}

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
    parser.add_argument("--mode", choices=["alerts", "full"], default="alerts")
    parser.add_argument("--test-ping", action="store_true", help="Envia mensagem de teste imediata")
    parser.add_argument("--dry-run", action="store_true", help="Não envia notificações externas nem altera cloud_state.json")
    args = parser.parse_args()

    # Check if at least one external channel is configured in env when not dry-run
    has_tg = bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))
    has_dc = bool(os.getenv("DISCORD_WEBHOOK_URL"))
    if not args.dry_run and not (has_tg or has_dc):
        logger.warning(
            "Nenhum canal configurado nas variáveis de ambiente (TELEGRAM_BOT_TOKEN/CHAT_ID ou DISCORD_WEBHOOK_URL). "
            "Adiciona-os em GitHub -> Settings -> Secrets and variables -> Actions."
        )

    run_cloud_monitor(mode=args.mode, send_test_ping=args.test_ping, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
