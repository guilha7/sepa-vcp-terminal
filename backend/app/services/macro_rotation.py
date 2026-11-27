import time
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.config import CRYPTO_SECTORS, US_SECTOR_ETFS, settings
from app.database import db
from app.services.crypto_derivatives import get_crypto_derivatives_radar
from app.services.market_data import get_batch_ohlcv
from app.services.notifications import notification_service
from app.services.trader_edge import get_upcoming_macro_events


def compute_ibd_market_timing(df: Optional[pd.DataFrame], ticker: str = "SPY") -> dict[str, Any]:
    """
    William O'Neil / IBD Market Timing:
    - Distribution Days (last 25 sessions): close <= -0.20% on volume > prev session.
      Expires automatically if index rallies >= +5% above the distribution day's close.
    - Follow-Through Day (FTD): Day 4-10 of a rally attempt after a 20d swing low,
      closing >= +1.25% on higher volume than prior day.
    """
    if df is None or len(df) < 55:
        return {
            "ticker": ticker,
            "distribution_days": 0,
            "distribution_dates": [],
            "follow_through_day": False,
            "ftd_date": None,
            "status": "INDISPONIVEL",
            "label": "Dados insuficientes",
        }

    closes = df["close"].astype(float).values
    lows = df["low"].astype(float).values
    vols = df["volume"].astype(float).values
    dates = df["date"].astype(str).values
    n = len(df)

    # 1. Distribution Days over last 25 trading sessions (with authentic +5% rally expiry)
    start_idx = max(1, n - 25)
    dist_dates: list[str] = []
    for i in range(start_idx, n):
        prev_c = closes[i - 1]
        if prev_c <= 0:
            continue
        pct_chg = (closes[i] - prev_c) / prev_c * 100.0
        if pct_chg <= -0.20 and vols[i] > vols[i - 1]:
            # Check if invalidated by subsequent +5% rally from this close
            future_max = float(np.max(closes[i + 1 :])) if i + 1 < n else closes[i]
            if future_max < closes[i] * 1.05:
                dist_dates.append(str(dates[i]))

    dist_count = len(dist_dates)

    # 2. Follow-Through Day (FTD) detection in last 10 sessions
    ftd_detected = False
    ftd_date = None
    low_window_start = max(1, n - 25)
    local_low_idx = low_window_start + int(np.argmin(lows[low_window_start : n - 3])) if n - 3 > low_window_start else low_window_start
    for day_offset in range(4, 12):
        idx = local_low_idx + day_offset
        if idx >= n or idx < 1:
            continue
        # Ensure rally attempt wasn't undercut before FTD
        if float(np.min(lows[local_low_idx + 1 : idx + 1])) < lows[local_low_idx] * 0.995:
            continue
        pct_chg = (closes[idx] - closes[idx - 1]) / closes[idx - 1] * 100.0 if closes[idx - 1] > 0 else 0.0
        if pct_chg >= 1.25 and vols[idx] > vols[idx - 1]:
            if idx >= n - 10:
                ftd_detected = True
                ftd_date = str(dates[idx])

    price = float(closes[-1])
    sma50 = float(np.mean(closes[-50:]))
    sma200 = float(np.mean(closes[-200:])) if n >= 200 else sma50

    if price < sma50 and price < sma200:
        if ftd_detected:
            status, label = "RALLY_ATTEMPT_FTD", "Follow-Through Day (Tentativa de Fundo)"
        else:
            status, label = "MARKET_IN_CORRECTION", "Mercado em Correção (Defensivo)"
    elif dist_count >= 6:
        status, label = "MARKET_IN_CORRECTION", f"Distribuição Pesada ({dist_count} dias)"
    elif dist_count >= 4:
        status, label = "UPTREND_UNDER_PRESSURE", f"Tendência sob Pressão ({dist_count} dias dist.)"
    else:
        status, label = "UPTREND_CONFIRMED", f"Tendência Confirmada ({dist_count} dias dist.)"

    return {
        "ticker": ticker,
        "distribution_days": dist_count,
        "distribution_dates": dist_dates[-6:],
        "follow_through_day": ftd_detected,
        "ftd_date": ftd_date,
        "status": status,
        "label": label,
    }


def compute_stockbee_breadth(extra_dfs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """
    Pradeep Bonde (Stockbee Market Monitor) Internal Market Breadth:
    - % of scanned stocks trading above SMA 50 (T2108 proxy) and SMA 200
    - Count of 4% Up days (up >= +4% on rising volume) vs 4% Down days (<= -4% on rising vol)
    - 5-day rolling ratio of 4% breakouts vs breakdowns
    """
    stock_dfs: dict[str, pd.DataFrame] = {}

    # Combine provided ETFs/stocks with cached stock OHLCV from watchlist
    watchlist_stocks = [w["ticker"] for w in db.get_watchlist(asset_type="stock", only_enabled=True)]
    for tk in watchlist_stocks:
        if tk in extra_dfs and extra_dfs[tk] is not None and not extra_dfs[tk].empty:
            stock_dfs[tk] = extra_dfs[tk]
        else:
            cached = db.cache_get(f"ohlcv:{tk}:15mo", allow_stale=True)
            if isinstance(cached, dict) and cached.get("records"):
                stock_dfs[tk] = pd.DataFrame(cached["records"])

    for etf in US_SECTOR_ETFS.keys():
        if etf not in stock_dfs and etf in extra_dfs and extra_dfs[etf] is not None and not extra_dfs[etf].empty:
            stock_dfs[etf] = extra_dfs[etf]

    evaluated = 0
    above_50 = 0
    above_200 = 0
    up_4_today = 0
    down_4_today = 0
    up_4_5d = 0
    down_4_5d = 0

    for df in stock_dfs.values():
        if df is None or len(df) < 55:
            continue
        closes = df["close"].astype(float).values
        vols = df["volume"].astype(float).values
        n = len(closes)
        evaluated += 1
        cur = closes[-1]
        if cur > float(np.mean(closes[-50:])):
            above_50 += 1
        if n >= 200 and cur > float(np.mean(closes[-200:])):
            above_200 += 1

        # 4% Up / Down on rising volume today & last 5 sessions
        for k in range(1, min(6, n)):
            idx = n - k
            prev = closes[idx - 1]
            if prev <= 0:
                continue
            chg = (closes[idx] - prev) / prev * 100.0
            vol_up = vols[idx] >= vols[idx - 1]
            if chg >= 4.0 and vol_up:
                up_4_5d += 1
                if k == 1:
                    up_4_today += 1
            elif chg <= -4.0 and vol_up:
                down_4_5d += 1
                if k == 1:
                    down_4_today += 1

    pct_50 = round((above_50 / evaluated) * 100.0, 1) if evaluated > 0 else 50.0
    pct_200 = round((above_200 / evaluated) * 100.0, 1) if evaluated > 0 else 50.0
    ratio_5d = round(up_4_5d / max(down_4_5d, 1), 2)

    if pct_50 <= 20.0:
        state = "SOBREVENDA_EXTREMA"
        label = "Sobrevenda Extrema (< 20% > SMA50)"
        guidance = "Pânico generalizado — vigiar sinais de Follow-Through Day ou ressalto técnico."
    elif pct_50 >= 80.0:
        state = "SOBREAQUECIDO"
        label = "Sobreaquecido (> 80% > SMA50)"
        guidance = "Muitos ativos esticados — evitar perseguir breakouts tardios e proteger lucros."
    elif pct_50 >= 55.0 and ratio_5d >= 1.3:
        state = "AGRESSIVO_LONG"
        label = "Breadth Saudável (Breakouts a Funcionar)"
        guidance = "Participação larga de compradores — vento a favor para setups VCP e Pocket Pivots."
    elif pct_50 < 40.0 or ratio_5d < 0.7:
        state = "DEFENSIVO_CAIXA"
        label = "Breadth Fraco (Modo Defensivo)"
        guidance = "Mais quedas de 4% do que subidas — taxa de falha de breakouts é alta."
    else:
        state = "SELETIVO"
        label = "Breadth Seletivo / Misto"
        guidance = "Foca-te apenas nos 2–3 setores líderes e reduz o risco por posição."

    return {
        "universe_size": evaluated,
        "pct_above_sma50": pct_50,
        "pct_above_sma200": pct_200,
        "up_4pct_today": up_4_today,
        "down_4pct_today": down_4_today,
        "up_4pct_5d": up_4_5d,
        "down_4pct_5d": down_4_5d,
        "ratio_5d": ratio_5d,
        "state": state,
        "label": label,
        "guidance": guidance,
    }


def _pct_return(series: pd.Series, days: int) -> Optional[float]:
    if series is None or len(series) <= days:
        return None
    cur = float(series.iloc[-1])
    prev = float(series.iloc[-(days + 1)])
    if prev <= 0:
        return None
    return round((cur - prev) / prev * 100.0, 2)


def _trend_snapshot(df: Optional[pd.DataFrame], ticker: str, label: str) -> dict[str, Any]:
    if df is None or df.empty:
        return {
            "ticker": ticker,
            "label": label,
            "price": None,
            "daily_change_pct": None,
            "sma50": None,
            "sma200": None,
            "above_sma50": None,
            "above_sma200": None,
            "sma50_above_sma200": None,
            "return_1w": None,
            "return_1m": None,
            "return_3m": None,
            "trend_state": "INDISPONIVEL",
            "sparkline": [],
        }

    closes = df["close"].astype(float)
    price = float(closes.iloc[-1])
    prev = float(closes.iloc[-2]) if len(closes) >= 2 else price
    daily = round((price - prev) / prev * 100.0, 2) if prev > 0 else 0.0

    sma50 = float(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else None
    sma200 = float(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else None
    above_50 = bool(sma50 is not None and price > sma50)
    above_200 = bool(sma200 is not None and price > sma200)
    golden = bool(sma50 is not None and sma200 is not None and sma50 > sma200)

    if above_50 and above_200 and golden:
        state = "ALTA_FORTE"
    elif above_200:
        state = "NEUTRO_POSITIVO"
    elif above_50:
        state = "RECUPERACAO"
    else:
        state = "BAIXA"

    spark = [round(float(x), 4) for x in closes.iloc[-min(len(closes), 30):].tolist()]
    return {
        "ticker": ticker,
        "label": label,
        "price": round(price, 2),
        "daily_change_pct": daily,
        "sma50": round(sma50, 2) if sma50 is not None else None,
        "sma200": round(sma200, 2) if sma200 is not None else None,
        "above_sma50": above_50,
        "above_sma200": above_200,
        "sma50_above_sma200": golden,
        "return_1w": _pct_return(closes, 5),
        "return_1m": _pct_return(closes, 21),
        "return_3m": _pct_return(closes, 63),
        "trend_state": state,
        "sparkline": spark,
    }


def compute_macro_and_rotation(force_refresh: bool = False) -> dict[str, Any]:
    """
    Module 1:
    - Macro Traffic Light (Risk-On / Cautela / Risk-Off) crossing SPY, QQQ, BTC-USD vs SMA50/200,
      ^VIX, ^TNX (10Y Yield), DX-Y.NYB (US Dollar Index).
    - Sector Rotation Map for 11 US Sector ETFs and major Crypto Sectors (1W, 1M, 3M perf & RS).
    """
    cache_key = "macro:overview"
    if not force_refresh:
        cached = db.cache_get(cache_key)
        if cached and isinstance(cached, dict):
            # Always evaluate imminent FOMC/CPI/NFP calendar fresh (zero-cost)
            cached["macro_events"] = get_upcoming_macro_events()
            return cached

    macro_tickers = ["SPY", "QQQ", "BTC-USD", "^VIX", "^TNX", "DX-Y.NYB"]
    sector_tickers = list(US_SECTOR_ETFS.keys())
    crypto_tickers: list[str] = []
    for sec in CRYPTO_SECTORS.values():
        crypto_tickers.extend(sec["tickers"])

    all_tickers = list(dict.fromkeys(macro_tickers + sector_tickers + crypto_tickers))
    dfs, _, warnings = get_batch_ohlcv(all_tickers, period="15mo", force_refresh=force_refresh)

    # --- 1. Macro Traffic Light Scoring ---
    spy_snap = _trend_snapshot(dfs.get("SPY"), "SPY", "S&P 500 (SPY)")
    qqq_snap = _trend_snapshot(dfs.get("QQQ"), "QQQ", "Nasdaq 100 (QQQ)")
    btc_snap = _trend_snapshot(dfs.get("BTC-USD"), "BTC-USD", "Bitcoin (BTC)")
    vix_snap = _trend_snapshot(dfs.get("^VIX"), "^VIX", "Volatilidade (VIX)")
    tnx_snap = _trend_snapshot(dfs.get("^TNX"), "^TNX", "US 10Y Yield (^TNX)")
    dxy_snap = _trend_snapshot(dfs.get("DX-Y.NYB"), "DX-Y.NYB", "Índice Dólar (DXY)")

    # Normalize ^TNX display (yfinance quotes ^TNX in tenths or exact pct depending on feed, e.g. 4.25 vs 42.5)
    if tnx_snap["price"] is not None and tnx_snap["price"] > 20.0:
        tnx_snap["price"] = round(tnx_snap["price"] / 10.0, 3)
        if tnx_snap["sma50"]:
            tnx_snap["sma50"] = round(tnx_snap["sma50"] / 10.0, 3)
        if tnx_snap["sma200"]:
            tnx_snap["sma200"] = round(tnx_snap["sma200"] / 10.0, 3)

    score = 0.0
    max_possible = 0.0
    factors: list[dict[str, Any]] = []

    def _score_equity_bench(snap: dict, weight: float, name: str):
        nonlocal score, max_possible
        if snap["price"] is None:
            factors.append({"name": name, "status": "neutro", "points": 0, "detail": "Dados temporariamente indisponíveis."})
            return
        max_possible += weight
        pts = 0.0
        if snap["above_sma200"]:
            pts += weight * 0.45
        if snap["above_sma50"]:
            pts += weight * 0.35
        if snap["sma50_above_sma200"]:
            pts += weight * 0.20
        score += pts
        status = "positivo" if pts >= weight * 0.75 else ("neutro" if pts >= weight * 0.4 else "negativo")
        factors.append(
            {
                "name": name,
                "status": status,
                "points": round(pts, 1),
                "detail": (
                    f"Preço {snap['price']} | SMA50 {snap['sma50'] or 'N/D'} | SMA200 {snap['sma200'] or 'N/D'} "
                    f"({'acima de ambas' if snap['above_sma50'] and snap['above_sma200'] else 'pressão técnica'})"
                ),
            }
        )

    _score_equity_bench(spy_snap, 25.0, "Tendência S&P 500 (SPY)")
    _score_equity_bench(qqq_snap, 25.0, "Tendência Nasdaq 100 (QQQ)")
    _score_equity_bench(btc_snap, 15.0, "Apetite a Risco Cripto (BTC)")

    # VIX factor (weight 15)
    if vix_snap["price"] is not None:
        max_possible += 15.0
        vix = vix_snap["price"]
        if vix < 16.5:
            pts, st, msg = 15.0, "positivo", f"VIX em {vix:.2f} (< 16.5): baixa volatilidade, ambiente construtivo."
        elif vix < 21.0:
            pts, st, msg = 10.0, "neutro", f"VIX em {vix:.2f} (16.5–21): volatilidade controlada."
        elif vix < 26.0:
            pts, st, msg = 4.0, "neutro", f"VIX em {vix:.2f} (21–26): nervosismo elevado — gerir risco."
        else:
            pts, st, msg = 0.0, "negativo", f"VIX em {vix:.2f} (> 26): stress elevado de mercado."
        score += pts
        factors.append({"name": "Volatilidade (VIX)", "status": st, "points": pts, "detail": msg})

    # 10Y Treasury Yield factor (weight 10)
    if tnx_snap["price"] is not None:
        max_possible += 10.0
        y10 = tnx_snap["price"]
        chg_1m = tnx_snap["return_1m"] or 0.0
        if y10 <= 4.35 and chg_1m < 6.0:
            pts, st, msg = 10.0, "positivo", f"Yield 10Y em {y10:.2f}% ({chg_1m:+.1f}% em 1M): estável para ações de crescimento."
        elif y10 <= 4.85 and chg_1m < 10.0:
            pts, st, msg = 5.5, "neutro", f"Yield 10Y em {y10:.2f}% ({chg_1m:+.1f}% em 1M): alguma pressão nas valorizações."
        else:
            pts, st, msg = 1.0, "negativo", f"Yield 10Y em {y10:.2f}% ({chg_1m:+.1f}% em 1M): juros altos/em disparo pesam no risco."
        score += pts
        factors.append({"name": "Obrigações EUA 10A (^TNX)", "status": st, "points": pts, "detail": msg})

    # US Dollar Index factor (weight 10)
    if dxy_snap["price"] is not None:
        max_possible += 10.0
        dxy = dxy_snap["price"]
        dxy_above_50 = dxy_snap["above_sma50"]
        dxy_1m = dxy_snap["return_1m"] or 0.0
        if not dxy_above_50 or dxy_1m <= 0.5:
            pts, st, msg = 10.0, "positivo", f"DXY em {dxy:.2f} ({dxy_1m:+.1f}% em 1M): dólar controlado favorece ações e cripto."
        elif dxy_1m <= 2.5:
            pts, st, msg = 5.5, "neutro", f"DXY em {dxy:.2f} ({dxy_1m:+.1f}% em 1M): fortalecimento moderado do dólar."
        else:
            pts, st, msg = 1.0, "negativo", f"DXY em {dxy:.2f} ({dxy_1m:+.1f}% em 1M): dólar forte cria vento contrário a ativos de risco."
        score += pts
        factors.append({"name": "Índice do Dólar (DXY)", "status": st, "points": pts, "detail": msg})

    normalized_score = round((score / max_possible * 100.0), 1) if max_possible > 0 else 50.0

    if normalized_score >= 68.0:
        regime = "RISK_ON"
        regime_label = "Risk-On (Mercado Favorável)"
        color = "green"
        guidance = (
            "Ambiente macro alinhado com tendências de alta. Breakouts de VCP em setores líderes têm maior "
            "probabilidade de seguimento. Mantém sempre o stop-loss máximo de 6%."
        )
    elif normalized_score >= 42.0:
        regime = "CAUTELA"
        regime_label = "Cautela / Neutro (Mercado Seletivo)"
        color = "yellow"
        guidance = (
            "Sinais mistos entre índices, volatilidade ou juros. Sê altamente seletivo: prioriza apenas os "
            "setores líderes de Força Relativa, reduz o tamanho das posições e realiza lucros parciais em 2R."
        )
    else:
        regime = "RISK_OFF"
        regime_label = "Risk-Off (Modo Defensivo)"
        color = "red"
        guidance = (
            "Ambiente macro adverso ou em tendência de baixa. Segundo Minervini, a prioridade é preservar "
            "capital: evita novos breakouts agressivos, mantém liquidez e aguarda o regresso acima da SMA 50."
        )

    # --- 2. US Sector Rotation (11 ETFs vs SPY) ---
    spy_c = dfs["SPY"]["close"].astype(float) if "SPY" in dfs and not dfs["SPY"].empty else None
    spy_1w = _pct_return(spy_c, 5) or 0.0
    spy_1m = _pct_return(spy_c, 21) or 0.0
    spy_3m = _pct_return(spy_c, 63) or 0.0

    us_sectors: list[dict[str, Any]] = []
    for etf, pt_name in US_SECTOR_ETFS.items():
        df = dfs.get(etf)
        if df is None or df.empty:
            continue
        c = df["close"].astype(float)
        r1w = _pct_return(c, 5) or 0.0
        r1m = _pct_return(c, 21) or 0.0
        r3m = _pct_return(c, 63) or 0.0
        rs_1w = round(r1w - spy_1w, 2)
        rs_1m = round(r1m - spy_1m, 2)
        rs_3m = round(r3m - spy_3m, 2)
        # Composite rotation momentum score (weighted RS + absolute return)
        composite_rs = round(0.45 * rs_1m + 0.35 * rs_3m + 0.20 * rs_1w, 2)
        sma50 = float(c.rolling(50).mean().iloc[-1]) if len(c) >= 50 else None
        price = float(c.iloc[-1])
        us_sectors.append(
            {
                "ticker": etf,
                "name": pt_name,
                "price": round(price, 2),
                "return_1w": r1w,
                "return_1m": r1m,
                "return_3m": r3m,
                "rs_1w": rs_1w,
                "rs_1m": rs_1m,
                "rs_3m": rs_3m,
                "composite_rs": composite_rs,
                "above_sma50": bool(sma50 is not None and price > sma50),
                "flow_direction": "INFLOW" if composite_rs >= 0.5 else ("OUTFLOW" if composite_rs <= -0.5 else "NEUTRAL"),
            }
        )

    us_sectors.sort(key=lambda x: x["composite_rs"], reverse=True)
    us_leaders = us_sectors[:4]
    us_laggards = list(reversed(us_sectors[-4:])) if len(us_sectors) >= 4 else []

    # --- 3. Crypto Sector Rotation (Equal-weight baskets vs BTC-USD) ---
    btc_c = dfs["BTC-USD"]["close"].astype(float) if "BTC-USD" in dfs and not dfs["BTC-USD"].empty else None
    btc_1w = _pct_return(btc_c, 7) or 0.0
    btc_1m = _pct_return(btc_c, 30) or 0.0
    btc_3m = _pct_return(btc_c, 90) or 0.0

    crypto_sectors: list[dict[str, Any]] = []
    for sec_id, meta in CRYPTO_SECTORS.items():
        r1w_vals, r1m_vals, r3m_vals = [], [], []
        active_members = []
        for tk in meta["tickers"]:
            df = dfs.get(tk)
            if df is None or len(df) < 10:
                continue
            c = df["close"].astype(float)
            w_ret = _pct_return(c, 7)
            m_ret = _pct_return(c, 30)
            q_ret = _pct_return(c, 90)
            if w_ret is not None:
                r1w_vals.append(w_ret)
            if m_ret is not None:
                r1m_vals.append(m_ret)
            if q_ret is not None:
                r3m_vals.append(q_ret)
            active_members.append(tk.replace("-USD", ""))

        if not active_members:
            continue

        avg_1w = round(float(np.mean(r1w_vals)), 2) if r1w_vals else 0.0
        avg_1m = round(float(np.mean(r1m_vals)), 2) if r1m_vals else 0.0
        avg_3m = round(float(np.mean(r3m_vals)), 2) if r3m_vals else 0.0
        rs_1w = round(avg_1w - btc_1w, 2)
        rs_1m = round(avg_1m - btc_1m, 2)
        rs_3m = round(avg_3m - btc_3m, 2)
        composite_rs = round(0.45 * rs_1m + 0.35 * rs_3m + 0.20 * rs_1w, 2)

        crypto_sectors.append(
            {
                "id": sec_id,
                "name": meta["name"],
                "members": active_members,
                "return_1w": avg_1w,
                "return_1m": avg_1m,
                "return_3m": avg_3m,
                "rs_1w": rs_1w,
                "rs_1m": rs_1m,
                "rs_3m": rs_3m,
                "composite_rs": composite_rs,
                "flow_direction": "INFLOW" if composite_rs >= 1.0 else ("OUTFLOW" if composite_rs <= -1.0 else "NEUTRAL"),
            }
        )

    crypto_sectors.sort(key=lambda x: x["composite_rs"], reverse=True)
    crypto_leaders = crypto_sectors[:3]
    crypto_laggards = list(reversed(crypto_sectors[-3:])) if len(crypto_sectors) >= 3 else []

    ibd_spy = compute_ibd_market_timing(dfs.get("SPY"), "SPY")
    ibd_qqq = compute_ibd_market_timing(dfs.get("QQQ"), "QQQ")
    breadth = compute_stockbee_breadth(dfs)
    crypto_derivs = get_crypto_derivatives_radar(dfs, force_refresh=force_refresh)

    payload = {
        "updated_at": time.time(),
        "macro_traffic_light": {
            "regime": regime,
            "label": regime_label,
            "color": color,
            "score": normalized_score,
            "guidance": guidance,
            "factors": factors,
            "benchmarks": [spy_snap, qqq_snap, btc_snap, vix_snap, tnx_snap, dxy_snap],
        },
        "ibd_timing": {
            "spy": ibd_spy,
            "qqq": ibd_qqq,
            "max_distribution_days": max(ibd_spy["distribution_days"], ibd_qqq["distribution_days"]),
            "any_ftd": bool(ibd_spy["follow_through_day"] or ibd_qqq["follow_through_day"]),
        },
        "market_breadth": breadth,
        "macro_events": get_upcoming_macro_events(),
        "crypto_derivatives": crypto_derivs,
        "us_rotation": {
            "benchmark": "SPY",
            "benchmark_returns": {"1w": spy_1w, "1m": spy_1m, "3m": spy_3m},
            "sectors": us_sectors,
            "leaders": us_leaders,
            "laggards": us_laggards,
        },
        "crypto_rotation": {
            "benchmark": "BTC-USD",
            "benchmark_returns": {"1w": btc_1w, "1m": btc_1m, "3m": btc_3m},
            "sectors": crypto_sectors,
            "leaders": crypto_leaders,
            "laggards": crypto_laggards,
        },
        "warnings": warnings,
    }

    db.cache_set(cache_key, "macro", payload, settings.cache_ttl_prices)
    notification_service.check_macro_regime_shift(regime, regime_label, normalized_score)
    return payload
