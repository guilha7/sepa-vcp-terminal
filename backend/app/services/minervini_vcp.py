from typing import Any, Optional

import numpy as np
import pandas as pd

from app.services.quant_signals import evaluate_multi_strategy_signals


def _round_price(val: float) -> float:
    if val >= 100:
        return round(val, 2)
    if val >= 1:
        return round(val, 3)
    if val >= 0.01:
        return round(val, 5)
    return round(val, 7)


def compute_weighted_return(closes: pd.Series) -> Optional[float]:
    """
    IBD / Minervini style weighted relative return:
    40% 3-month (63d), 20% 6-month (126d), 20% 9-month (189d), 20% 12-month (252d).
    """
    n = len(closes)
    if n < 30:
        return None
    cur = float(closes.iloc[-1])
    if cur <= 0:
        return None

    horizons = [(63, 0.40), (126, 0.20), (189, 0.20), (252, 0.20)]
    total_w = 0.0
    weighted = 0.0
    for lookback, w in horizons:
        if n > lookback:
            prev = float(closes.iloc[-(lookback + 1)])
            if prev > 0:
                weighted += w * ((cur - prev) / prev)
                total_w += w
    if total_w == 0.0:
        first = float(closes.iloc[0])
        return (cur - first) / first if first > 0 else None
    return weighted / total_w


def compute_rs_line_series(
    asset_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame],
) -> tuple[list[dict[str, Any]], bool, bool]:
    """
    Computes date-aligned Relative Strength (RS) line normalized to base 100,
    plus Mark Minervini's signature 'RS New High' and 'RS New High Before Price' signals.
    Returns (rs_line_points, rs_new_high, rs_new_high_before_price).
    """
    if asset_df is None or asset_df.empty or benchmark_df is None or benchmark_df.empty:
        return [], False, False

    a = asset_df[["date", "close", "high"]].copy()
    b = benchmark_df[["date", "close"]].rename(columns={"close": "bench_close"}).copy()
    merged = pd.merge(a, b, on="date", how="inner")
    if len(merged) < 30:
        return [], False, False

    merged["ratio"] = merged["close"].astype(float) / merged["bench_close"].astype(float).replace(0, np.nan)
    merged = merged.dropna(subset=["ratio"]).reset_index(drop=True)
    if merged.empty:
        return [], False, False

    base = float(merged["ratio"].iloc[0])
    if base <= 0:
        return [], False, False
    merged["rs_norm"] = (merged["ratio"] / base) * 100.0

    # Check 52-week (252 trading sessions) RS high vs price high
    win = merged.iloc[-min(len(merged), 252) :]
    rs_52w_max = float(win["rs_norm"].max())
    recent_rs_max = float(win["rs_norm"].iloc[-5:].max())
    rs_new_high = bool(rs_52w_max > 0 and recent_rs_max >= rs_52w_max * 0.995)

    price_52w_high = float(win["high"].max())
    cur_price = float(win["close"].iloc[-1])
    price_below_52w_high = bool(price_52w_high > 0 and cur_price < price_52w_high * 0.992)

    rs_new_high_before_price = bool(rs_new_high and price_below_52w_high)

    points = [
        {"time": str(row["date"]), "value": round(float(row["rs_norm"]), 2)}
        for _, row in merged.iterrows()
    ]
    return points, rs_new_high, rs_new_high_before_price


def compute_relative_strength(
    asset_df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame],
    asset_ticker: str = "",
    benchmark_ticker: str = "SPY",
) -> dict[str, Any]:
    """Computes Relative Strength ratio, rating, and RS New High Before Price footprint."""
    asset_ret = compute_weighted_return(asset_df["close"])
    _, rs_new_high, rs_new_high_before_price = compute_rs_line_series(asset_df, benchmark_df)

    if asset_ret is None:
        return {
            "benchmark": benchmark_ticker,
            "asset_weighted_return_pct": None,
            "benchmark_weighted_return_pct": None,
            "rs_ratio": None,
            "outperforms_benchmark": False,
            "rs_rating": 50,
            "rs_new_high": False,
            "rs_new_high_before_price": False,
        }

    if benchmark_df is None or benchmark_df.empty:
        return {
            "benchmark": benchmark_ticker,
            "asset_weighted_return_pct": round(asset_ret * 100, 2),
            "benchmark_weighted_return_pct": None,
            "rs_ratio": round(1.0 + asset_ret, 3),
            "outperforms_benchmark": asset_ret > 0,
            "rs_rating": int(np.clip(50 + asset_ret * 60, 1, 99)),
            "rs_new_high": False,
            "rs_new_high_before_price": False,
        }

    bench_ret = compute_weighted_return(benchmark_df["close"])
    if bench_ret is None:
        bench_ret = 0.0

    denom = max(1.0 + bench_ret, 0.05)
    rs_ratio = (1.0 + asset_ret) / denom
    outperforms = rs_ratio > 1.0 if asset_ticker != benchmark_ticker else asset_ret > 0.15
    rs_rating = int(np.clip(50 + (rs_ratio - 1.0) * 110, 1, 99))

    return {
        "benchmark": benchmark_ticker,
        "asset_weighted_return_pct": round(asset_ret * 100, 2),
        "benchmark_weighted_return_pct": round(bench_ret * 100, 2),
        "rs_ratio": round(rs_ratio, 3),
        "outperforms_benchmark": bool(outperforms),
        "rs_rating": rs_rating,
        "rs_new_high": rs_new_high,
        "rs_new_high_before_price": rs_new_high_before_price,
    }


def evaluate_trend_template(
    df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame],
    ticker: str,
    asset_type: str = "stock",
    benchmark_ticker: str = "SPY",
) -> dict[str, Any]:
    """Evaluates Mark Minervini's 8 Strict Stage 2 Trend Template Rules."""
    n = len(df)
    closes = df["close"].astype(float)
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)

    price = float(closes.iloc[-1])
    sma50_s = closes.rolling(50).mean()
    sma150_s = closes.rolling(150).mean()
    sma200_s = closes.rolling(200).mean()

    sma50 = float(sma50_s.iloc[-1]) if n >= 50 and pd.notna(sma50_s.iloc[-1]) else None
    sma150 = float(sma150_s.iloc[-1]) if n >= 150 and pd.notna(sma150_s.iloc[-1]) else None
    sma200 = float(sma200_s.iloc[-1]) if n >= 200 and pd.notna(sma200_s.iloc[-1]) else None
    sma200_22d_ago = (
        float(sma200_s.iloc[-23])
        if n >= 223 and pd.notna(sma200_s.iloc[-23])
        else None
    )

    lookback_52w = min(n, 252)
    low_52w = float(lows.iloc[-lookback_52w:].min())
    high_52w = float(highs.iloc[-lookback_52w:].max())

    pct_above_52w_low = ((price - low_52w) / low_52w * 100.0) if low_52w > 0 else 0.0
    pct_below_52w_high = ((high_52w - price) / high_52w * 100.0) if high_52w > 0 else 100.0

    sma200_trending_up = False
    sma200_change_22d_pct = None
    if sma200 is not None and sma200_22d_ago is not None and sma200_22d_ago > 0:
        sma200_change_22d_pct = (sma200 - sma200_22d_ago) / sma200_22d_ago * 100.0
        recent_200 = sma200_s.iloc[-23:].dropna()
        if len(recent_200) >= 22:
            x = np.arange(len(recent_200), dtype=float)
            slope = float(np.polyfit(x, recent_200.values, 1)[0])
            sma200_trending_up = (sma200 > sma200_22d_ago) and (slope > 0)

    rs = compute_relative_strength(df, benchmark_df, asset_ticker=ticker, benchmark_ticker=benchmark_ticker)

    r1 = bool(sma150 is not None and sma200 is not None and price > sma150 and price > sma200)
    r2 = bool(sma150 is not None and sma200 is not None and sma150 > sma200)
    r3 = bool(sma200_trending_up)
    r4 = bool(sma50 is not None and sma150 is not None and sma200 is not None and sma50 > sma150 and sma50 > sma200)
    r5 = bool(sma50 is not None and price > sma50)
    r6 = bool(pct_above_52w_low >= 30.0)
    r7 = bool(pct_below_52w_high <= 25.0)
    r8 = bool(rs["outperforms_benchmark"])

    def _fmt(v: Optional[float]) -> str:
        return f"{_round_price(v)}" if v is not None else "N/D"

    rules = [
        {
            "id": 1,
            "title": "Preço > SMA 150 e SMA 200",
            "passed": r1,
            "detail": f"Preço {_fmt(price)} vs SMA150 {_fmt(sma150)} / SMA200 {_fmt(sma200)}",
        },
        {
            "id": 2,
            "title": "SMA 150 > SMA 200",
            "passed": r2,
            "detail": f"SMA150 {_fmt(sma150)} vs SMA200 {_fmt(sma200)}",
        },
        {
            "id": 3,
            "title": "SMA 200 em tendência ascendente (>= 22 sessões)",
            "passed": r3,
            "detail": (
                f"SMA200 variou {sma200_change_22d_pct:+.2f}% nas últimas 22 sessões"
                if sma200_change_22d_pct is not None
                else "Histórico insuficiente (< 223 sessões)"
            ),
        },
        {
            "id": 4,
            "title": "SMA 50 > SMA 150 e SMA 200",
            "passed": r4,
            "detail": f"SMA50 {_fmt(sma50)} vs SMA150 {_fmt(sma150)} / SMA200 {_fmt(sma200)}",
        },
        {
            "id": 5,
            "title": "Preço > SMA 50",
            "passed": r5,
            "detail": f"Preço {_fmt(price)} vs SMA50 {_fmt(sma50)}",
        },
        {
            "id": 6,
            "title": "Preço >= 30% acima do mínimo 52 semanas",
            "passed": r6,
            "detail": f"+{pct_above_52w_low:.1f}% acima do mínimo 52s ({_fmt(low_52w)})",
        },
        {
            "id": 7,
            "title": "Preço a <= 25% do máximo 52 semanas",
            "passed": r7,
            "detail": f"-{pct_below_52w_high:.1f}% abaixo do máximo 52s ({_fmt(high_52w)})",
        },
        {
            "id": 8,
            "title": f"Força Relativa (RS) superior a {benchmark_ticker}",
            "passed": r8,
            "detail": (
                f"RS Ratio {rs['rs_ratio']:.2f} (Ativo {rs['asset_weighted_return_pct']:+.1f}% vs "
                f"{benchmark_ticker} {rs['benchmark_weighted_return_pct']:+.1f}%)"
                + (" • RS NEW HIGH!" if rs.get("rs_new_high_before_price") else "")
                if rs["rs_ratio"] is not None and rs["benchmark_weighted_return_pct"] is not None
                else "RS indisponível"
            ),
        },
    ]

    passed_count = sum(1 for r in rules if r["passed"])
    return {
        "passed": passed_count == 8,
        "passed_count": passed_count,
        "total_rules": 8,
        "rules": rules,
        "metrics": {
            "price": _round_price(price),
            "sma50": _round_price(sma50) if sma50 is not None else None,
            "sma150": _round_price(sma150) if sma150 is not None else None,
            "sma200": _round_price(sma200) if sma200 is not None else None,
            "low_52w": _round_price(low_52w),
            "high_52w": _round_price(high_52w),
            "pct_above_52w_low": round(pct_above_52w_low, 2),
            "pct_below_52w_high": round(pct_below_52w_high, 2),
            "sma200_change_22d_pct": round(sma200_change_22d_pct, 2) if sma200_change_22d_pct is not None else None,
        },
        "relative_strength": rs,
    }


def _extract_swing_contractions(base_df: pd.DataFrame, asset_type: str = "stock") -> tuple[list[dict[str, Any]], str]:
    """
    ZigZag / Real Swing Pivot detector for Mark Minervini VCP contractions.
    Automatically adapts to short bases (3 weeks) up to long bases (18 weeks)
    and returns exact date/price coordinates for direct chart visualization.
    """
    n = len(base_df)
    if n < 15:
        return [], "none"

    highs = base_df["high"].astype(float).values
    lows = base_df["low"].astype(float).values
    dates = base_df["date"].astype(str).values

    # Locate the starting peak of the consolidation base (highest high in first 80% of window)
    search_end = max(int(n * 0.80), 5)
    start_peak_idx = int(np.argmax(highs[:search_end]))
    # If base peak is too close to the end (< 12 bars left), fall back to full base start
    if n - start_peak_idx < 12:
        start_peak_idx = 0

    # ZigZag threshold (reversal %)
    rev_pct = 0.025 if asset_type == "stock" else 0.045

    pivots: list[tuple[int, str, float]] = [(start_peak_idx, "H", float(highs[start_peak_idx]))]
    mode = "seeking_low"
    extreme_idx = start_peak_idx
    extreme_val = float(lows[start_peak_idx])

    for i in range(start_peak_idx + 1, n):
        if mode == "seeking_low":
            if lows[i] < extreme_val:
                extreme_val = float(lows[i])
                extreme_idx = i
            elif extreme_val > 0 and (highs[i] - extreme_val) / extreme_val >= rev_pct:
                pivots.append((extreme_idx, "L", extreme_val))
                mode = "seeking_high"
                extreme_idx = i
                extreme_val = float(highs[i])
        else:
            if highs[i] > extreme_val:
                extreme_val = float(highs[i])
                extreme_idx = i
            elif extreme_val > 0 and (extreme_val - lows[i]) / extreme_val >= rev_pct:
                pivots.append((extreme_idx, "H", extreme_val))
                mode = "seeking_low"
                extreme_idx = i
                extreme_val = float(lows[i])

    # Close out the trailing leg if meaningful
    if mode == "seeking_low" and extreme_idx > pivots[-1][0]:
        pivots.append((extreme_idx, "L", extreme_val))
    elif mode == "seeking_high" and extreme_idx > pivots[-1][0]:
        pivots.append((extreme_idx, "H", extreme_val))

    # Build Peak -> Trough contraction legs
    legs: list[dict[str, Any]] = []
    for k in range(len(pivots) - 1):
        i1, kind1, val1 = pivots[k]
        i2, kind2, val2 = pivots[k + 1]
        if kind1 == "H" and kind2 == "L" and val1 > 0 and val2 < val1:
            depth = round((val1 - val2) / val1 * 100.0, 2)
            if depth >= 1.5:
                legs.append(
                    {
                        "leg": len(legs) + 1,
                        "start_date": dates[i1],
                        "end_date": dates[i2],
                        "high_price": _round_price(val1),
                        "low_price": _round_price(val2),
                        "depth_pct": depth,
                    }
                )

    # Keep the most recent 2..4 legs (Minervini's 2T-4T contractions)
    if len(legs) >= 2:
        recent_legs = legs[-4:]
        for idx, lg in enumerate(recent_legs, start=1):
            lg["leg"] = idx
        return recent_legs, "zigzag_swings"

    # Fallback: adaptive 3-segment base structure with exact coordinates
    b_len = len(base_df)
    cut1 = max(int(b_len * 0.45), 6)
    cut2 = max(int(b_len * 0.78), cut1 + 5)
    segs = [base_df.iloc[:cut1], base_df.iloc[cut1:cut2], base_df.iloc[cut2:]]
    fb_legs: list[dict[str, Any]] = []
    for idx, seg in enumerate(segs, start=1):
        if seg.empty:
            continue
        hi_idx = int(seg["high"].astype(float).idxmax())
        lo_idx = int(seg["low"].astype(float).idxmin())
        hi_v = float(seg.loc[hi_idx, "high"])
        lo_v = float(seg.loc[lo_idx, "low"])
        depth = round((hi_v - lo_v) / hi_v * 100.0, 2) if hi_v > 0 else 0.0
        s_date = str(seg.iloc[0]["date"])
        e_date = str(seg.iloc[-1]["date"])
        fb_legs.append(
            {
                "leg": idx,
                "start_date": s_date,
                "end_date": e_date,
                "high_price": _round_price(hi_v),
                "low_price": _round_price(lo_v),
                "depth_pct": depth,
            }
        )
    return fb_legs, "base_segments"


def detect_vcp(df: pd.DataFrame, asset_type: str = "stock") -> dict[str, Any]:
    """
    Detects Mark Minervini's Volatility Contraction Pattern (VCP) using real swing pivots:
    - Adaptive base window (up to 90 trading sessions / ~18 weeks)
    - Successive volatility contractions (T1 > T2 > T3) with exact chart coordinates
    - Volume Dry-Up (VDU) near resistance/pivot
    - Valid Breakout confirmation (volume >= 1.5x 50d average)
    """
    n = len(df)
    if n < 45:
        return {
            "detected": False,
            "detection_method": "none",
            "contractions_pct": [],
            "contraction_legs": [],
            "contraction_count": 0,
            "volume_dry_up": False,
            "vdu_ratio": None,
            "breakout_signal": False,
            "breakout_volume_ratio": None,
            "pivot_price": None,
            "distance_to_pivot_pct": None,
            "is_extended": False,
            "atr_contracting": False,
            "quality_score": 0,
            "summary": "Histórico insuficiente para análise VCP.",
        }

    closes = df["close"].astype(float)
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    opens = df["open"].astype(float)
    vols = df["volume"].astype(float)

    price = float(closes.iloc[-1])
    prev_close = float(closes.iloc[-2])
    vol_today = float(vols.iloc[-1])
    vol_sma50 = float(vols.iloc[-50:].mean()) if n >= 50 else float(vols.mean())
    vol_sma50 = max(vol_sma50, 1e-9)

    # Adaptive consolidation window up to 90 sessions (~18 weeks), excluding very last bar for base pivots
    base_end = n - 1
    win_len = min(90, base_end)
    base_slice = df.iloc[base_end - win_len : base_end].reset_index(drop=True)

    legs, method = _extract_swing_contractions(base_slice, asset_type=asset_type)
    contractions = [lg["depth_pct"] for lg in legs]

    # ATR contraction confirmation (10d ATR vs 30d prior ATR)
    tr = pd.concat(
        [
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_pct = (tr / closes.replace(0, np.nan)) * 100.0
    atr_recent = float(atr_pct.iloc[-10:].mean())
    atr_prior = float(atr_pct.iloc[-40:-10].mean()) if n >= 40 else atr_recent
    atr_contracting = atr_recent < atr_prior * 0.90

    max_first = 38.0 if asset_type == "stock" else 55.0
    max_last = 12.0 if asset_type == "stock" else 18.0

    strict_3_step = False
    two_step_tight = False
    if len(contractions) >= 3:
        last3 = contractions[-3:]
        t1, t2, t3 = last3[0], last3[1], last3[2]
        strict_3_step = (t1 > t2 > t3) and (t3 <= max_last) and (t1 <= max_first) and (t1 >= t3 * 1.30)
        two_step_tight = (
            (t1 > t3)
            and (t2 >= t3 * 0.95)
            and (t3 <= max_last * 0.90)
            and (t1 <= max_first)
            and (t3 <= t1 * 0.65)
        )
    elif len(contractions) == 2:
        t1, t2 = contractions[0], contractions[1]
        two_step_tight = (t1 > t2) and (t2 <= max_last * 0.85) and (t1 <= max_first) and (t2 <= t1 * 0.65)

    contraction_count = 3 if strict_3_step else (2 if two_step_tight else (1 if len(contractions) >= 2 and contractions[-1] < contractions[0] else 0))

    # Pivot resistance: highest high of the prior 35 sessions excluding latest bar
    pivot_window = highs.iloc[max(0, n - 36) : n - 1]
    pivot_price = float(pivot_window.max())
    distance_to_pivot_pct = ((price - pivot_price) / pivot_price * 100.0) if pivot_price > 0 else 0.0

    # Volume Dry-Up (VDU)
    pre_vol_slice = vols.iloc[max(0, n - 8) : n - 1]
    vdu_avg_vol = float(pre_vol_slice.mean()) if not pre_vol_slice.empty else vol_today
    vdu_ratio = round(vdu_avg_vol / vol_sma50, 2)
    near_pivot = -10.0 <= distance_to_pivot_pct <= 4.0
    volume_dry_up = bool(vdu_ratio < 0.85 and near_pivot)

    # Breakout signal (>= 1.5x 50d avg volume)
    vol_ratio_today = round(vol_today / vol_sma50, 2)
    bullish_day = (price > prev_close) and (price >= float(opens.iloc[-1]) * 0.995)
    breakout_signal = bool(
        bullish_day
        and (-0.5 <= distance_to_pivot_pct <= 6.0)
        and (vol_ratio_today >= 1.5)
    )

    sma50 = float(closes.rolling(50).mean().iloc[-1]) if n >= 50 else price
    pct_above_sma50 = ((price - sma50) / sma50 * 100.0) if sma50 > 0 else 0.0
    is_extended = bool(distance_to_pivot_pct > 7.5 or pct_above_sma50 > 22.0)

    vcp_detected = bool((strict_3_step or (two_step_tight and (atr_contracting or volume_dry_up))) and distance_to_pivot_pct >= -12.0)

    quality = 0
    if strict_3_step:
        quality += 18
    elif two_step_tight:
        quality += 12
    elif contraction_count >= 1 and contractions and contractions[-1] <= max_last:
        quality += 6

    if atr_contracting:
        quality += 4
    if volume_dry_up:
        quality += 8
    if breakout_signal:
        quality += 10
    elif -4.0 <= distance_to_pivot_pct <= 1.5 and vcp_detected:
        quality += 5
    quality = min(quality, 35)

    c_str = " → ".join(f"{x:.1f}%" for x in contractions) if contractions else "N/D"
    if breakout_signal and vcp_detected:
        summary = f"Breakout VCP válido acima de {_round_price(pivot_price)} com volume {vol_ratio_today:.2f}x a média (swings: {c_str})."
    elif breakout_signal:
        summary = f"Breakout de volume ({vol_ratio_today:.2f}x) acima da resistência {_round_price(pivot_price)}."
    elif vcp_detected and volume_dry_up:
        summary = f"VCP maduro ({c_str}) com seca de volume ({vdu_ratio:.2f}x) junto ao pivô {_round_price(pivot_price)}."
    elif vcp_detected:
        summary = f"Contração VCP por swings ({c_str}) perto do pivô {_round_price(pivot_price)}."
    else:
        summary = f"Sem VCP clássico formado (swings recentes: {c_str})."

    return {
        "detected": vcp_detected,
        "detection_method": method,
        "contractions_pct": contractions,
        "contraction_legs": legs,
        "contraction_count": contraction_count,
        "volume_dry_up": volume_dry_up,
        "vdu_ratio": vdu_ratio,
        "breakout_signal": breakout_signal,
        "breakout_volume_ratio": vol_ratio_today,
        "pivot_price": _round_price(pivot_price),
        "distance_to_pivot_pct": round(distance_to_pivot_pct, 2),
        "is_extended": is_extended,
        "atr_contracting": bool(atr_contracting),
        "tight_low": _round_price(float(lows.iloc[-10:].min())),
        "quality_score": quality,
        "summary": summary,
    }


def compute_trade_plan(
    price: float,
    pivot_price: Optional[float],
    tight_low: Optional[float],
    max_stop_pct: float = 6.0,
) -> dict[str, Any]:
    """Computes pivot entry, tight technical stop-loss capped strictly at <= 6%, and 2R / 3R targets."""
    entry_ref = pivot_price if (pivot_price and pivot_price > 0 and price <= pivot_price * 1.03) else price
    max_stop_pct = min(max_stop_pct, 6.0)

    if tight_low and 0 < tight_low < entry_ref:
        raw_stop = tight_low * 0.995
        raw_stop_pct = (entry_ref - raw_stop) / entry_ref * 100.0
    else:
        raw_stop_pct = max_stop_pct

    stop_pct = round(min(max(raw_stop_pct, 2.5), max_stop_pct), 2)
    stop_price = entry_ref * (1.0 - stop_pct / 100.0)
    risk_per_unit = entry_ref - stop_price
    target_2r = entry_ref + 2.0 * risk_per_unit
    target_3r = entry_ref + 3.0 * risk_per_unit

    return {
        "entry_pivot": _round_price(entry_ref),
        "stop_loss_price": _round_price(stop_price),
        "stop_loss_pct": stop_pct,
        "target_2r": _round_price(target_2r),
        "target_2r_pct": round(stop_pct * 2.0, 2),
        "target_3r": _round_price(target_3r),
        "target_3r_pct": round(stop_pct * 3.0, 2),
    }


EU_SUFFIXES = (".DE", ".PA", ".AS", ".MC", ".MI", ".L", ".SW", ".ST")


def check_liquidity(df: pd.DataFrame, asset_type: str = "stock", ticker: str = "") -> dict[str, Any]:
    """Anti-error filter: ignores illiquid assets or penny stocks (calibrated for US, Europe & Portugal PSI)."""
    if df.empty:
        return {"passed": False, "avg_dollar_volume_50d": 0.0, "avg_volume_50d": 0.0, "reason": "Sem dados de volume"}

    tail = df.iloc[-min(len(df), 50) :]
    avg_vol = float(tail["volume"].mean())
    avg_dollar_vol = float((tail["close"] * tail["volume"]).mean())
    price = float(df["close"].iloc[-1])
    tk = (ticker or "").upper()

    if asset_type == "stock":
        if tk.endswith(".LS"):
            # Euronext Lisbon (PSI): major blue-chips like BCP/SON/EDP trade below 5€
            if price < 0.20:
                return {
                    "passed": False,
                    "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
                    "avg_volume_50d": round(avg_vol, 2),
                    "reason": "Preço inferior a 0.20€ (micro-cap evitada).",
                }
            if avg_dollar_vol < 100_000:
                return {
                    "passed": False,
                    "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
                    "avg_volume_50d": round(avg_vol, 2),
                    "reason": "Liquidez média diária insuficiente em Lisboa (< 100k€/dia).",
                }
        elif tk.endswith(EU_SUFFIXES):
            if price < 1.50:
                return {
                    "passed": False,
                    "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
                    "avg_volume_50d": round(avg_vol, 2),
                    "reason": "Preço inferior a 1.50€ (penny stock evitada).",
                }
            if avg_dollar_vol < 1_000_000:
                return {
                    "passed": False,
                    "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
                    "avg_volume_50d": round(avg_vol, 2),
                    "reason": "Liquidez média diária insuficiente na Europa (< 1M€/dia).",
                }
        else:
            if price < 5.0:
                return {
                    "passed": False,
                    "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
                    "avg_volume_50d": round(avg_vol, 2),
                    "reason": "Preço inferior a $5 (penny stock evitada no SEPA).",
                }
            if avg_dollar_vol < 5_000_000 or avg_vol < 150_000:
                return {
                    "passed": False,
                    "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
                    "avg_volume_50d": round(avg_vol, 2),
                    "reason": "Liquidez média diária insuficiente (< $5M/dia).",
                }
    else:
        if avg_dollar_vol < 1_000_000:
            return {
                "passed": False,
                "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
                "avg_volume_50d": round(avg_vol, 2),
                "reason": "Liquidez cripto insuficiente (< $1M/dia).",
            }

    return {
        "passed": True,
        "avg_dollar_volume_50d": round(avg_dollar_vol, 2),
        "avg_volume_50d": round(avg_vol, 2),
        "reason": "Liquidez institucional adequada.",
    }


def analyze_sepa_vcp(
    ticker: str,
    df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame],
    asset_type: str = "stock",
    benchmark_ticker: str = "SPY",
    fundamentals: Optional[dict[str, Any]] = None,
    data_source: str = "yfinance",
) -> dict[str, Any]:
    """Full Minervini SEPA + VCP evaluation returning score (0-100), RS New High signal, trade plan & explanations."""
    liquidity = check_liquidity(df, asset_type=asset_type, ticker=ticker)
    tt = evaluate_trend_template(
        df=df,
        benchmark_df=benchmark_df,
        ticker=ticker,
        asset_type=asset_type,
        benchmark_ticker=benchmark_ticker,
    )
    vcp = detect_vcp(df, asset_type=asset_type)
    price = tt["metrics"]["price"]
    prev_close = float(df["close"].iloc[-2]) if len(df) >= 2 else price
    daily_change_pct = round(((price - prev_close) / prev_close * 100.0), 2) if prev_close > 0 else 0.0

    trade_plan = compute_trade_plan(
        price=price,
        pivot_price=vcp.get("pivot_price"),
        tight_low=vcp.get("tight_low"),
        max_stop_pct=6.0,
    )

    quant = evaluate_multi_strategy_signals(
        df=df,
        benchmark_df=benchmark_df,
        asset_type=asset_type,
        fundamentals=fundamentals,
        rs_rating=tt["relative_strength"].get("rs_rating", 50),
        stop_loss_pct=trade_plan["stop_loss_pct"],
    )

    earnings_within_14d = bool((fundamentals or {}).get("earnings_within_14d", False))
    next_earnings_date = (fundamentals or {}).get("next_earnings_date")
    days_to_earnings = (fundamentals or {}).get("days_to_earnings")

    rs_info = tt["relative_strength"]
    score = tt["passed_count"] * 5.0
    score += (rs_info.get("rs_rating", 50) / 99.0) * 15.0
    score += float(vcp["quality_score"])

    dist = vcp.get("distance_to_pivot_pct")
    if dist is not None:
        if -3.0 <= dist <= 2.5:
            score += 10.0
        elif -7.0 <= dist <= 5.0:
            score += 6.0
        elif -12.0 <= dist <= 7.5:
            score += 3.0

    # Minervini Blue-Dot + Multi-Strategy Confluence Bonuses
    if rs_info.get("rs_new_high_before_price"):
        score += 4.0
    if quant["pocket_pivot"]["detected"]:
        score += 4.0
    if quant["ttm_squeeze"]["squeeze_fire_long"]:
        score += 4.0
    elif quant["ttm_squeeze"]["squeeze_on"]:
        score += 2.0
    if quant["episodic_pivot"]["detected"] or quant["high_tight_flag"]["detected"]:
        score += 5.0
    if quant["three_weeks_tight"]["detected"] and tt["passed"]:
        score += 3.0

    if vcp.get("is_extended") or quant["is_atr_overextended"]:
        score -= 12.0
    if earnings_within_14d:
        score -= 8.0
    if not liquidity["passed"]:
        score = min(score, 35.0)

    score = round(float(np.clip(score, 0.0, 100.0)), 1)

    if not tt["passed"]:
        status = "EM_OBSERVACAO" if tt["passed_count"] >= 6 else "FORA_STAGE2"
    elif vcp["breakout_signal"] and not vcp["is_extended"]:
        status = "BREAKOUT"
    elif vcp["detected"] and vcp["volume_dry_up"]:
        status = "VCP_PRONTO"
    elif vcp["detected"]:
        status = "VCP_FORMACAO"
    else:
        status = "STAGE_2"

    why_points: list[dict[str, str]] = []
    if tt["passed"]:
        why_points.append(
            {
                "topic": "Tendência Institucional (Stage 2)",
                "text": (
                    "Cumpre todas as 8 regras do Trend Template de Minervini: preço acima das SMAs 50, 150 e 200 "
                    "em alinhamento perfeito e SMA 200 em subida sustentável há mais de 22 sessões."
                ),
                "tone": "positive",
            }
        )
    else:
        failed_titles = [r["title"] for r in tt["rules"] if not r["passed"]][:3]
        why_points.append(
            {
                "topic": f"Trend Template ({tt['passed_count']}/8 regras)",
                "text": f"Ainda não cumpre integralmente o Stage 2. Falha em: {', '.join(failed_titles)}.",
                "tone": "warning",
            }
        )

    if rs_info.get("rs_new_high_before_price"):
        why_points.append(
            {
                "topic": "Sinal RS New High Before Price (Ponto Azul Minervini)",
                "text": (
                    f"A linha de Força Relativa face a {benchmark_ticker} atingiu novo máximo de 52 semanas ANTES "
                    f"do preço romper o seu máximo — sinal clássico de acumulação institucional silenciosa."
                ),
                "tone": "positive",
            }
        )
    elif rs_info.get("outperforms_benchmark"):
        why_points.append(
            {
                "topic": "Liderança de Mercado (Força Relativa)",
                "text": (
                    f"Está a superar o benchmark {benchmark_ticker} (RS Ratio {rs_info['rs_ratio']:.2f}, "
                    f"Rating RS ~{rs_info['rs_rating']}/99), indicando procura institucional acima da média."
                ),
                "tone": "positive",
            }
        )
    else:
        why_points.append(
            {
                "topic": "Força Relativa Fraca",
                "text": f"Performance relativa ainda abaixo de {benchmark_ticker}. Minervini privilegia líderes de RS.",
                "tone": "warning",
            }
        )

    c_list = vcp.get("contractions_pct") or []
    c_str = " → ".join(f"{x:.1f}%" for x in c_list) if c_list else "N/D"
    if vcp["detected"]:
        why_points.append(
            {
                "topic": "Contração de Volatilidade por Swings (VCP)",
                "text": (
                    f"Swings decrescentes detetados ({c_str}). A oferta está a ser absorvida em amplitudes cada vez "
                    f"mais apertadas antes de uma eventual rutura."
                ),
                "tone": "positive",
            }
        )
    else:
        why_points.append(
            {
                "topic": "Estrutura de Base / VCP",
                "text": f"As amplitudes recentes ({c_str}) ainda não mostram aperto clássico de VCP. Aguarda consolidação mais estreita.",
                "tone": "neutral",
            }
        )

    if vcp["breakout_signal"]:
        why_points.append(
            {
                "topic": "Confirmação de Breakout por Volume",
                "text": (
                    f"O preço rompeu a zona de pivô ({vcp['pivot_price']}) com volume {vcp['breakout_volume_ratio']:.2f}x "
                    f"acima da média de 50 dias (>= 1.5x), sinal típico de entrada institucional."
                ),
                "tone": "positive",
            }
        )
    elif vcp["volume_dry_up"]:
        why_points.append(
            {
                "topic": "Volume Dry-Up (Seca de Volume)",
                "text": (
                    f"Volume recente ({vcp['vdu_ratio']:.2f}x da média de 50 dias) secou junto à resistência ({vcp['pivot_price']}), "
                    f"mostrando ausência de pressão vendedora — ponto ideal de vigilância para rutura."
                ),
                "tone": "positive",
            }
        )

    why_points.append(
        {
            "topic": "Gestão de Risco Assimétrica (<= 6%)",
            "text": (
                f"Pivô sugerido em {trade_plan['entry_pivot']} com Stop-Loss técnico em {trade_plan['stop_loss_price']} "
                f"(-{trade_plan['stop_loss_pct']:.1f}%). Alvo 2R em {trade_plan['target_2r']} (+{trade_plan['target_2r_pct']:.1f}%) "
                f"e 3R em {trade_plan['target_3r']} (+{trade_plan['target_3r_pct']:.1f}%)."
            ),
            "tone": "neutral",
        }
    )

    if quant["pocket_pivot"]["detected"]:
        why_points.append(
            {
                "topic": "Pocket Pivot Detetado (Morales & Kacher)",
                "text": quant["pocket_pivot"]["summary"],
                "tone": "positive",
            }
        )
    if quant["ttm_squeeze"]["squeeze_fire_long"] or quant["ttm_squeeze"]["squeeze_on"]:
        why_points.append(
            {
                "topic": "TTM Squeeze (John Carter)",
                "text": quant["ttm_squeeze"]["summary"],
                "tone": "positive",
            }
        )
    if quant["episodic_pivot"]["detected"]:
        why_points.append(
            {
                "topic": "Episodic Pivot (Qullamaggie)",
                "text": (
                    f"Gap/explosão de +{quant['episodic_pivot']['gap_pct']}% em {quant['episodic_pivot']['date']} "
                    f"com volume {quant['episodic_pivot']['volume_ratio']}x — possível catalisador institucional."
                ),
                "tone": "positive",
            }
        )
    if quant["high_tight_flag"]["detected"]:
        why_points.append(
            {
                "topic": "High Tight Flag (O'Neil / Qullamaggie)",
                "text": (
                    f"Subida explosiva de +{quant['high_tight_flag']['pole_gain_pct']}% seguida de bandeira apertada "
                    f"({quant['high_tight_flag']['flag_depth_pct']}%) — padrão de alta potência."
                ),
                "tone": "positive",
            }
        )
    if quant["stop_too_tight_for_adr"]:
        why_points.append(
            {
                "topic": f"Atenção ao ADR% ({quant['adr_pct_20d']}%/dia)",
                "text": (
                    f"Este ativo varia {quant['adr_pct_20d']}% por dia; um stop de -{trade_plan['stop_loss_pct']}% "
                    f"equivale a apenas {quant['stop_in_adr_multiples']}x ADR (risco de ruído diário acionar o stop)."
                ),
                "tone": "warning",
            }
        )

    if vcp["is_extended"] or quant["is_atr_overextended"]:
        why_points.append(
            {
                "topic": "Aviso: Preço Esticado (Não Perseguir)",
                "text": (
                    f"O ativo está esticado ({quant['atr_extension_sma50']}x ATR face à SMA 50). "
                    f"Entrar agora aumenta o risco de pullback imediato ao stop."
                ),
                "tone": "danger",
            }
        )

    if earnings_within_14d:
        why_points.append(
            {
                "topic": "ALERTA EARNINGS (< 14 dias)",
                "text": (
                    f"Apresentação de resultados prevista para {next_earnings_date} (em {days_to_earnings} dias). "
                    f"Evita abrir posições novas sem almofada de lucro — o risco de gap noturno pode ultrapassar o stop de 6%."
                ),
                "tone": "danger",
            }
        )

    return {
        "ticker": ticker,
        "name": (fundamentals or {}).get("name") or ticker,
        "sector": (fundamentals or {}).get("sector") or ("Criptomoedas" if asset_type == "crypto" else None),
        "asset_type": asset_type,
        "data_source": data_source,
        "price": price,
        "daily_change_pct": daily_change_pct,
        "score": score,
        "status": status,
        "liquidity": liquidity,
        "trend_template": tt,
        "vcp": vcp,
        "quant": quant,
        "trade_plan": trade_plan,
        "earnings_within_14d": earnings_within_14d,
        "next_earnings_date": next_earnings_date,
        "days_to_earnings": days_to_earnings,
        "why_opportunity": why_points,
    }


def assign_cross_sectional_rs_ratings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Refines RS Rating (1-99) using cross-sectional percentile rank within each asset class."""
    for asset_cls in ("stock", "crypto"):
        subset = [
            r for r in results
            if r["asset_type"] == asset_cls
            and r["trend_template"]["relative_strength"].get("rs_ratio") is not None
        ]
        if len(subset) < 3:
            continue
        ratios = sorted(r["trend_template"]["relative_strength"]["rs_ratio"] for r in subset)
        n = len(ratios)
        for item in subset:
            val = item["trend_template"]["relative_strength"]["rs_ratio"]
            rank = sum(1 for x in ratios if x <= val)
            pct = int(round((rank / n) * 98) + 1)
            item["trend_template"]["relative_strength"]["rs_rating"] = min(max(pct, 1), 99)
    return results
