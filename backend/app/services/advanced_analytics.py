import logging
from typing import Any, Optional

import numpy as np
import pandas as pd
import yfinance as yf

from app.config import settings
from app.database import db
from app.services.market_data import is_crypto_ticker

logger = logging.getLogger(__name__)


def _safe_float(val: Any) -> Optional[float]:
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return None
        f = float(val)
        return None if (np.isnan(f) or np.isinf(f)) else f
    except Exception:
        return None


def compute_volume_quality(df: pd.DataFrame) -> dict[str, Any]:
    """
    William O'Neil / IBD Institutional Volume Footprint:
    - Up/Down Volume Ratio over last 50 sessions (total volume on up days / total volume on down days)
    - Accumulation/Distribution Grade A (strong buying) -> E (strong selling)
    - Count of high-volume (>= 1.25x avg) up days vs down days in the last 20 sessions
    """
    if df is None or len(df) < 25:
        return {
            "available": False,
            "up_down_volume_ratio_50d": None,
            "acc_dist_grade": "N/D",
            "acc_dist_label": "Histórico insuficiente",
            "high_vol_up_20d": 0,
            "high_vol_down_20d": 0,
        }

    work = df.copy()
    work["prev_close"] = work["close"].shift(1)
    work["vol_sma50"] = work["volume"].rolling(50, min_periods=20).mean()

    last50 = work.tail(50).dropna(subset=["prev_close"])
    up_vol = float(last50.loc[last50["close"] > last50["prev_close"], "volume"].sum())
    down_vol = float(last50.loc[last50["close"] < last50["prev_close"], "volume"].sum())

    if down_vol > 0:
        ud_ratio = round(up_vol / down_vol, 2)
    elif up_vol > 0:
        ud_ratio = 3.0
    else:
        ud_ratio = 1.0

    if ud_ratio >= 1.5:
        grade, label = "A", "Acumulação Institucional Forte"
    elif ud_ratio >= 1.2:
        grade, label = "B", "Acumulação Moderada"
    elif ud_ratio >= 0.9:
        grade, label = "C", "Neutro / Equilibrado"
    elif ud_ratio >= 0.7:
        grade, label = "D", "Distribuição Moderada"
    else:
        grade, label = "E", "Distribuição Institucional Forte"

    last20 = work.tail(20).dropna(subset=["prev_close", "vol_sma50"])
    hv_up = int(((last20["close"] > last20["prev_close"]) & (last20["volume"] >= last20["vol_sma50"] * 1.25)).sum())
    hv_down = int(((last20["close"] < last20["prev_close"]) & (last20["volume"] >= last20["vol_sma50"] * 1.25)).sum())

    return {
        "available": True,
        "up_down_volume_ratio_50d": ud_ratio,
        "acc_dist_grade": grade,
        "acc_dist_label": label,
        "high_vol_up_20d": hv_up,
        "high_vol_down_20d": hv_down,
    }


def compute_asset_personality_backtest(df: pd.DataFrame) -> dict[str, Any]:
    """
    Asset Personality Mini-Backtest (Last ~2 Years, pure pandas/numpy):
    1. Tests historical Stage-2 20-day high breakouts (with vol >= 1.2x SMA50) spaced >= 10 bars apart:
       - Did price reach +12% (2R target) BEFORE hitting -6% (Minervini stop)?
       - Tracks win rate, fakeout rate (closed below pivot within 5 sessions), and avg 20-day max gain.
    2. Identifies which Moving Average (SMA10, SMA21, SMA50) best fits the asset's trend pullbacks
       so the trader knows which Trailing Stop mode fits this asset's personality.
    """
    if df is None or len(df) < 120:
        return {
            "available": False,
            "breakout_signals": 0,
            "wins_2r": 0,
            "losses_stop": 0,
            "open_or_neutral": 0,
            "win_rate_pct": None,
            "fakeout_rate_pct": None,
            "avg_max_gain_20d_pct": None,
            "personality_code": "POUCOS_DADOS",
            "personality_label": "Histórico curto (< 6 meses)",
            "best_trailing_ma": "SMA21",
            "best_trailing_reason": "SMA 21 é o padrão equilibrado para swing trading.",
        }

    work = df.tail(520).reset_index(drop=True).copy()
    close = work["close"].astype(float).values
    high = work["high"].astype(float).values
    low = work["low"].astype(float).values
    vol = work["volume"].astype(float).values
    n = len(work)

    sma10 = pd.Series(close).rolling(10).mean().values
    sma21 = pd.Series(close).rolling(21).mean().values
    sma50 = pd.Series(close).rolling(50).mean().values
    vol_sma50 = pd.Series(vol).rolling(50, min_periods=20).mean().values
    prev_high_20 = pd.Series(high).shift(1).rolling(20).max().values

    wins = 0
    losses = 0
    neutral = 0
    fakeouts = 0
    max_gains_20d: list[float] = []
    last_signal_idx = -20

    # Walk forward up to n - 6 so each signal has at least 5 sessions to evaluate
    for i in range(55, n - 6):
        if i - last_signal_idx < 10:
            continue
        if np.isnan(sma50[i]) or np.isnan(prev_high_20[i]) or np.isnan(vol_sma50[i]):
            continue
        # Breakout condition: price above SMA50, closes above prior 20-day high, with volume expansion >= 1.2x
        if close[i] > sma50[i] and close[i] > prev_high_20[i] and vol_sma50[i] > 0 and vol[i] >= vol_sma50[i] * 1.2:
            last_signal_idx = i
            entry = close[i]
            stop_px = entry * 0.94   # -6% Minervini stop
            target_px = entry * 1.12  # +12% (2R)
            pivot_px = prev_high_20[i]

            outcome = "NEUTRAL"
            horizon = min(i + 45, n)
            for j in range(i + 1, horizon):
                if low[j] <= stop_px:
                    outcome = "LOSS"
                    break
                if high[j] >= target_px:
                    outcome = "WIN"
                    break

            if outcome == "WIN":
                wins += 1
            elif outcome == "LOSS":
                losses += 1
            else:
                neutral += 1

            # Fakeout check: closed back below breakout pivot within 5 sessions
            end5 = min(i + 6, n)
            if np.any(close[i + 1 : end5] < pivot_px * 0.995):
                fakeouts += 1

            end20 = min(i + 21, n)
            if end20 > i + 1:
                peak_20 = float(np.max(high[i + 1 : end20]))
                max_gains_20d.append(((peak_20 - entry) / entry) * 100.0)

    total_signals = wins + losses + neutral
    decided = wins + losses
    win_rate = round((wins / decided) * 100.0, 1) if decided > 0 else None
    fakeout_rate = round((fakeouts / total_signals) * 100.0, 1) if total_signals > 0 else None
    avg_max_20d = round(float(np.mean(max_gains_20d)), 1) if max_gains_20d else None

    if total_signals < 2:
        p_code = "POUCOS_SINAIS"
        p_label = "Poucos breakouts Stage 2 nos últimos 2 anos"
    elif (win_rate is not None and win_rate >= 55.0) and (fakeout_rate is None or fakeout_rate <= 55.0):
        p_code = "TREND_CLEAN"
        p_label = "Respeita Breakouts — Excelente p/ SEPA/VCP"
    elif fakeout_rate is not None and fakeout_rate >= 65.0:
        p_code = "CHOPPY_FAKEOUT"
        p_label = "Propensa a Falsos Breakouts — Exigir Volume Forte"
    else:
        p_code = "EQUILIBRADA"
        p_label = "Comportamento Misto — Usar Parcial 2R + Breakeven"

    # Determine which Moving Average best tracks uptrend runs (close > SMA50)
    uptrend_mask = (~np.isnan(sma50)) & (close > sma50)
    uptrend_days = int(np.sum(uptrend_mask))
    if uptrend_days >= 30:
        above_10_pct = float(np.mean(close[uptrend_mask] > sma10[uptrend_mask]) * 100.0)
        above_21_pct = float(np.mean(close[uptrend_mask] > sma21[uptrend_mask]) * 100.0)
        # Compute 20d avg ADR to calibrate volatility
        adr_20 = float(np.mean((high[-20:] - low[-20:]) / np.maximum(close[-20:], 1e-6)) * 100.0)
        if above_10_pct >= 72.0 and adr_20 >= 4.0:
            best_ma = "SMA10"
            best_reason = f"Tendência explosiva ({above_10_pct:.0f}% dos dias em alta acima da SMA10; ADR {adr_20:.1f}%)."
        elif above_21_pct >= 68.0:
            best_ma = "SMA21"
            best_reason = f"Respeita bem a SMA 21 em tendências de alta ({above_21_pct:.0f}% das sessões acima)."
        else:
            best_ma = "SMA50"
            best_reason = f"Oscila com pullbacks mais fundos ({above_21_pct:.0f}% acima da SMA21) — dá mais espaço com SMA 50."
    else:
        best_ma = "SMA21"
        best_reason = "Padrão equilibrado (pouco tempo recente em tendência Stage 2)."

    return {
        "available": True,
        "breakout_signals": total_signals,
        "wins_2r": wins,
        "losses_stop": losses,
        "open_or_neutral": neutral,
        "win_rate_pct": win_rate,
        "fakeout_rate_pct": fakeout_rate,
        "avg_max_gain_20d_pct": avg_max_20d,
        "personality_code": p_code,
        "personality_label": p_label,
        "best_trailing_ma": best_ma,
        "best_trailing_reason": best_reason,
    }


def fetch_institutional_and_quarterly(
    ticker: str,
    quote_type: Optional[str] = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Fetches 24h-cached zero-cost institutional data via yfinance for equities:
    1. Short Interest (% Short Float, Days to Cover, Short Squeeze Risk) & Institutional Ownership
    2. SEC Insider Purchases vs Sales (last 6 months)
    3. Quarterly Earnings Surprises (last 4 quarters) & Minervini Code 33 Revenue/EPS Acceleration
    Cleanly returns available=False for Crypto & ETFs without unnecessary network calls.
    """
    if is_crypto_ticker(ticker) or (quote_type or "").upper() in ("ETF", "MUTUALFUND", "INDEX"):
        return {
            "available": False,
            "reason": "Cripto / ETF (sem dados SEC de Insiders ou Earnings trimestrais)",
            "short_interest": {},
            "insiders": {},
            "earnings_surprises": [],
            "beats_last_4": 0,
            "quarterly_financials": [],
            "code_33_acceleration": False,
        }

    cache_key = f"inst_q:{ticker}"
    if not force_refresh:
        cached = db.cache_get(cache_key)
        if cached and isinstance(cached, dict):
            return cached

    result: dict[str, Any] = {
        "available": True,
        "short_interest": {
            "short_float_pct": None,
            "days_to_cover": None,
            "institutional_held_pct": None,
            "insiders_held_pct": None,
            "squeeze_risk": "N/D",
        },
        "insiders": {
            "available": False,
            "buys_trans_6m": 0,
            "sells_trans_6m": 0,
            "net_shares_6m": None,
            "signal": "NEUTRO",
            "signal_label": "Sem atividade recente de insiders",
        },
        "earnings_surprises": [],
        "beats_last_4": 0,
        "quarterly_financials": [],
        "code_33_acceleration": False,
        "code_33_summary": "Dados trimestrais indisponíveis para este ativo.",
    }

    try:
        tk = yf.Ticker(ticker)
        info = tk.info or {}

        if (info.get("quoteType") or "").upper() in ("ETF", "MUTUALFUND", "INDEX"):
            result["available"] = False
            result["reason"] = "ETF / Fundo (sem dados de Insiders ou Earnings)"
            db.cache_set(cache_key, "fundamentals", result, settings.cache_ttl_fundamentals)
            return result

        # 1. Short Interest & Ownership
        short_fl = _safe_float(info.get("shortPercentOfFloat"))
        short_fl_pct = round(short_fl * 100.0, 2) if short_fl is not None else None
        # Some yfinance tickers occasionally return >1 as already percentage
        if short_fl_pct is not None and short_fl_pct > 100.0:
            short_fl_pct = round(short_fl_pct / 100.0, 2)
        dtc = _safe_float(info.get("shortRatio"))
        inst_pct = _safe_float(info.get("heldPercentInstitutions"))
        ins_pct = _safe_float(info.get("heldPercentInsiders"))

        squeeze = "BAIXO"
        if (short_fl_pct is not None and short_fl_pct >= 15.0) or (dtc is not None and dtc >= 5.0):
            squeeze = "ALTO"
        elif (short_fl_pct is not None and short_fl_pct >= 8.0) or (dtc is not None and dtc >= 3.5):
            squeeze = "MODERADO"
        elif short_fl_pct is None and dtc is None:
            squeeze = "N/D"

        result["short_interest"] = {
            "short_float_pct": short_fl_pct,
            "days_to_cover": round(dtc, 2) if dtc is not None else None,
            "institutional_held_pct": round(inst_pct * 100.0, 1) if inst_pct is not None else None,
            "insiders_held_pct": round(ins_pct * 100.0, 1) if ins_pct is not None else None,
            "squeeze_risk": squeeze,
        }

        # 2. SEC Insider Purchases (6m summary)
        try:
            ip = tk.insider_purchases
            if ip is not None and not ip.empty:
                label_col = ip.columns[0]
                buys_tr, sells_tr, net_sh = 0, 0, None
                for _, row in ip.iterrows():
                    lbl = str(row.get(label_col, "")).lower()
                    tr_val = _safe_float(row.get("Trans"))
                    sh_val = _safe_float(row.get("Shares"))
                    if lbl == "purchases":
                        buys_tr = int(tr_val or 0)
                    elif lbl == "sales":
                        sells_tr = int(tr_val or 0)
                    elif "net shares" in lbl and "%" not in lbl:
                        net_sh = sh_val

                if buys_tr > 0 and (net_sh is not None and net_sh > 0):
                    sig, sig_lbl = "COMPRA_INSIDERS", f"Compra Líquida ({buys_tr} compras vs {sells_tr} vendas em 6M)"
                elif buys_tr > 0 and buys_tr >= sells_tr:
                    sig, sig_lbl = "COMPRA_INSIDERS", f"Insiders Ativos na Compra ({buys_tr} compras vs {sells_tr} vendas)"
                elif sells_tr > buys_tr * 2 and sells_tr >= 5:
                    sig, sig_lbl = "VENDA_INSIDERS", f"Predomínio de Vendas ({sells_tr} vendas vs {buys_tr} compras em 6M)"
                else:
                    sig, sig_lbl = "NEUTRO", f"Atividade Mista ({buys_tr} compras / {sells_tr} vendas em 6M)"

                result["insiders"] = {
                    "available": True,
                    "buys_trans_6m": buys_tr,
                    "sells_trans_6m": sells_tr,
                    "net_shares_6m": int(net_sh) if net_sh is not None else None,
                    "signal": sig,
                    "signal_label": sig_lbl,
                }
        except Exception:
            pass

        # 3. Earnings Surprises (last 4 quarters)
        surprises: list[dict[str, Any]] = []
        try:
            eh = tk.earnings_history
            if eh is not None and not eh.empty:
                for idx_val, row in eh.tail(4).iterrows():
                    est = _safe_float(row.get("epsEstimate"))
                    act = _safe_float(row.get("epsActual"))
                    sp = _safe_float(row.get("surprisePercent"))
                    sp_pct = round(sp * 100.0, 1) if sp is not None else None
                    q_label = str(idx_val)[:10] if idx_val is not None else "—"
                    beat = bool(act is not None and est is not None and act >= est)
                    surprises.append(
                        {
                            "quarter": q_label,
                            "eps_estimate": round(est, 2) if est is not None else None,
                            "eps_actual": round(act, 2) if act is not None else None,
                            "surprise_pct": sp_pct,
                            "beat": beat,
                        }
                    )
        except Exception:
            pass

        result["earnings_surprises"] = surprises
        beats_count = sum(1 for s in surprises if s["beat"])
        result["beats_last_4"] = beats_count

        # 4. Quarterly Revenue & Net Income Acceleration (Minervini Code 33)
        q_rows: list[dict[str, Any]] = []
        try:
            qi = tk.quarterly_income_stmt
            if qi is not None and not qi.empty:
                cols = list(qi.columns)[:5]  # most recent first
                rev_key = next((k for k in ("Total Revenue", "Operating Revenue") if k in qi.index), None)
                ni_key = next((k for k in ("Net Income", "Net Income Common Stockholders") if k in qi.index), None)
                eps_key = next((k for k in ("Diluted EPS", "Basic EPS") if k in qi.index), None)

                raw_q = []
                for c in cols:
                    raw_q.append(
                        {
                            "quarter": str(c)[:10],
                            "revenue": _safe_float(qi.loc[rev_key, c]) if rev_key else None,
                            "net_income": _safe_float(qi.loc[ni_key, c]) if ni_key else None,
                            "eps": _safe_float(qi.loc[eps_key, c]) if eps_key else None,
                        }
                    )

                # Compute QoQ sequential change for the 4 most recent quarters (or YoY if 5th quarter exists)
                for idx_q in range(min(4, len(raw_q))):
                    cur = raw_q[idx_q]
                    prev = raw_q[idx_q + 1] if idx_q + 1 < len(raw_q) else None
                    rev_chg = None
                    ni_chg = None
                    if prev and cur["revenue"] is not None and prev["revenue"] and prev["revenue"] > 0:
                        rev_chg = round(((cur["revenue"] - prev["revenue"]) / abs(prev["revenue"])) * 100.0, 1)
                    if prev and cur["net_income"] is not None and prev["net_income"] and abs(prev["net_income"]) > 0:
                        ni_chg = round(((cur["net_income"] - prev["net_income"]) / abs(prev["net_income"])) * 100.0, 1)
                    q_rows.append(
                        {
                            "quarter": cur["quarter"],
                            "revenue": cur["revenue"],
                            "net_income": cur["net_income"],
                            "eps": round(cur["eps"], 2) if cur["eps"] is not None else None,
                            "rev_qoq_pct": rev_chg,
                            "ni_qoq_pct": ni_chg,
                        }
                    )
                # Reverse to chronological order (oldest -> newest) for intuitive reading left-to-right
                q_rows.reverse()
        except Exception:
            pass

        result["quarterly_financials"] = q_rows

        # Evaluate Code 33 / Earnings Acceleration signal
        rev_series = [q["revenue"] for q in q_rows if q.get("revenue") is not None]
        ni_series = [q["net_income"] for q in q_rows if q.get("net_income") is not None]
        rev_trending_up = len(rev_series) >= 3 and (rev_series[-1] > rev_series[-2] > rev_series[-3])
        ni_trending_up = len(ni_series) >= 3 and (ni_series[-1] > ni_series[-2] > ni_series[-3])
        strong_beats = len(surprises) >= 3 and beats_count >= 3

        code_33 = bool((rev_trending_up and ni_trending_up) or (rev_trending_up and strong_beats))
        result["code_33_acceleration"] = code_33
        if rev_trending_up and ni_trending_up:
            result["code_33_summary"] = (
                f"ACELERAÇÃO CODE 33 ATIVA: Receitas e Lucros a crescer nos últimos 3 trimestres consecutivos"
                + (f" ({beats_count}/{len(surprises)} Earnings acima do esperado)." if surprises else ".")
            )
        elif rev_trending_up and strong_beats:
            result["code_33_summary"] = (
                f"Forte Momentum Fundamental: Receitas em aceleração há 3 trimestres + {beats_count}/{len(surprises)} Earnings superados."
            )
        elif strong_beats:
            result["code_33_summary"] = (
                f"Consistência de Lucros: bateu estimativas em {beats_count}/{len(surprises)} trimestres recentes."
            )
        elif q_rows or surprises:
            result["code_33_summary"] = "Sem aceleração trimestral consecutiva (Code 33) neste momento."

    except Exception as exc:
        logger.debug("Dados institucionais/trimestrais parciais para %s: %s", ticker, exc)

    db.cache_set(cache_key, "fundamentals", result, settings.cache_ttl_fundamentals)
    return result
