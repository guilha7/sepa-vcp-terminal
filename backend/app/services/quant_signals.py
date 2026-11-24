"""
Multi-Strategy Quantitative Signal Engine (100% free OHLCV & fundamentals):
- Stan Weinstein: Stage Analysis (Stage 1 / 2 / 3 / 4) & Mansfield Relative Strength
- Kristjan Kullamägi (Qullamaggie): ADR% (20d), Episodic Pivot (EP), High Tight Flag (HTF)
- Gil Morales & Chris Kacher: Pocket Pivot (early institutional accumulation)
- John Carter: TTM Squeeze (Bollinger Bands inside Keltner Channels + momentum fire)
- William O'Neil (IBD): 3 Weeks Tight (3WT) & CAN SLIM fundamental sub-score
- Matt Caruso / TraderLion: ATR Extension from SMA 50
- Brian Shannon: Anchored VWAP (Swing Low & YTD)
"""

from typing import Any, Optional

import numpy as np
import pandas as pd


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or pd.isna(v):
            return None
        f = float(v)
        return None if (np.isnan(f) or np.isinf(f)) else f
    except Exception:
        return None


def compute_weinstein_stage(df: pd.DataFrame) -> dict[str, Any]:
    """
    Stan Weinstein 4-Stage Classification using the 30-week (~150-day) Moving Average:
    - Stage 1: Acumulação / Base (SMA150 plana após queda)
    - Stage 2: Tendência de Alta (Preço > SMA150 e SMA150 ascendente)
    - Stage 3: Distribuição / Topo (SMA150 a achatar após grande subida, volatilidade solta)
    - Stage 4: Tendência de Baixa (Preço < SMA150 e SMA150 descendente)
    """
    n = len(df)
    if n < 160:
        return {
            "stage": 0,
            "code": "INDEFINIDO",
            "label": "Histórico Curto",
            "sma150_slope_pct": None,
            "description": "Menos de 160 sessões para classificar a fase de Weinstein.",
        }

    closes = df["close"].astype(float)
    sma150 = closes.rolling(150).mean()
    price = float(closes.iloc[-1])
    cur_150 = float(sma150.iloc[-1])
    prev_150 = float(sma150.iloc[-21]) if pd.notna(sma150.iloc[-21]) else cur_150
    slope_pct = ((cur_150 - prev_150) / prev_150 * 100.0) if prev_150 > 0 else 0.0

    lookback_52w = min(n, 252)
    high_52w = float(df["high"].astype(float).iloc[-lookback_52w:].max())
    low_52w = float(df["low"].astype(float).iloc[-lookback_52w:].min())
    dist_from_high = ((high_52w - price) / high_52w * 100.0) if high_52w > 0 else 0.0
    dist_from_low = ((price - low_52w) / low_52w * 100.0) if low_52w > 0 else 0.0

    sma50 = float(closes.rolling(50).mean().iloc[-1])

    if price > cur_150 and slope_pct >= 0.45:
        stage, code, label = 2, "STAGE_2", "Stage 2 — Alta (Markup)"
        desc = "Fase ideal para compras: preço acima da média de 30 semanas ascendente."
    elif price < cur_150 and slope_pct <= -0.45:
        stage, code, label = 4, "STAGE_4", "Stage 4 — Queda (Markdown)"
        desc = "Tendência descendente confirmada — evitar compras."
    elif dist_from_high <= 28.0 and dist_from_low >= 35.0 and (price < sma50 or abs(slope_pct) < 0.8):
        stage, code, label = 3, "STAGE_3", "Stage 3 — Topo / Distribuição"
        desc = "Média de 30 semanas a perder força perto de máximos — cautela com falsos breakouts."
    else:
        stage, code, label = 1, "STAGE_1", "Stage 1 — Base / Acumulação"
        desc = "Consolidação lateral com média plana — aguardar rutura para Stage 2."

    return {
        "stage": stage,
        "code": code,
        "label": label,
        "sma150_slope_pct": round(slope_pct, 2),
        "description": desc,
    }


def compute_mansfield_rs(asset_df: pd.DataFrame, benchmark_df: Optional[pd.DataFrame]) -> Optional[float]:
    """
    Stan Weinstein Mansfield Relative Strength (zero-centered oscillator over 52 weeks):
    MRS = ((RP_now / SMA_52w(RP)) - 1) * 100
    Values > 0 indicate outperformance vs benchmark; < 0 indicates underperformance.
    """
    if asset_df is None or asset_df.empty or benchmark_df is None or benchmark_df.empty:
        return None
    a = asset_df[["date", "close"]].copy()
    b = benchmark_df[["date", "close"]].rename(columns={"close": "bclose"}).copy()
    m = pd.merge(a, b, on="date", how="inner")
    if len(m) < 60:
        return None
    rp = m["close"].astype(float) / m["bclose"].astype(float).replace(0, np.nan)
    rp = rp.dropna()
    if len(rp) < 60:
        return None
    win = min(len(rp), 252)
    sma_rp = float(rp.iloc[-win:].mean())
    if sma_rp <= 0:
        return None
    return round(((float(rp.iloc[-1]) / sma_rp) - 1.0) * 100.0, 2)


def compute_adr_and_atr_extension(df: pd.DataFrame) -> dict[str, Any]:
    """
    Qullamaggie ADR% (20-day Average Daily Range %) +
    Matt Caruso / TraderLion ATR Extension above/below SMA 50.
    """
    n = len(df)
    if n < 20:
        return {
            "adr_pct_20d": None,
            "atr_14": None,
            "atr_pct_14": None,
            "atr_extension_sma50": None,
            "is_atr_overextended": False,
            "adr_tier": "INDISPONIVEL",
        }

    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    closes = df["close"].astype(float)
    price = float(closes.iloc[-1])

    # Qullamaggie ADR%: 20d average of (High - Low) / Close * 100
    daily_range_pct = ((highs - lows) / closes.replace(0, np.nan)) * 100.0
    adr_20 = float(daily_range_pct.iloc[-20:].mean())

    # Wilder / simple ATR(14)
    tr = pd.concat(
        [
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr_14 = float(tr.iloc[-14:].mean())
    atr_pct_14 = (atr_14 / price * 100.0) if price > 0 else 0.0

    atr_ext = None
    is_overext = False
    if n >= 50 and atr_14 > 0:
        sma50 = float(closes.rolling(50).mean().iloc[-1])
        atr_ext = round((price - sma50) / atr_14, 2)
        is_overext = atr_ext >= 4.5

    if adr_20 >= 5.0:
        tier = "EXPLOSIVO"
    elif adr_20 >= 3.0:
        tier = "IDEAL"
    else:
        tier = "LENTO"

    return {
        "adr_pct_20d": round(adr_20, 2),
        "atr_14": round(atr_14, 5),
        "atr_pct_14": round(atr_pct_14, 2),
        "atr_extension_sma50": atr_ext,
        "is_atr_overextended": is_overext,
        "adr_tier": tier,
    }


def detect_pocket_pivot(df: pd.DataFrame, stage: int) -> dict[str, Any]:
    """
    Gil Morales & Chris Kacher Pocket Pivot:
    - Up day closing in upper half of daily range
    - Volume > highest DOWN-day volume of the previous 10 sessions
    - Price interacting near EMA 10 or SMA 50 (not overextended, not Stage 4)
    """
    n = len(df)
    if n < 55 or stage == 4:
        return {"detected": False, "recent_dates": [], "vol_vs_max_down": None, "summary": "Sem Pocket Pivot."}

    closes = df["close"].astype(float)
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    vols = df["volume"].astype(float)
    dates = df["date"].astype(str)

    ema10 = closes.ewm(span=10, adjust=False).mean()
    sma50 = closes.rolling(50).mean()

    recent_dates: list[str] = []
    latest_hit = False
    latest_ratio = None

    # Scan last 25 bars for chart markers; check last 3 bars for active signal
    start_i = max(12, n - 25)
    for i in range(start_i, n):
        c = float(closes.iloc[i])
        prev_c = float(closes.iloc[i - 1])
        if c <= prev_c:
            continue
        hi = float(highs.iloc[i])
        lo = float(lows.iloc[i])
        bar_pos = ((c - lo) / (hi - lo)) if hi > lo else 0.5
        if bar_pos < 0.45:
            continue

        # Previous 10 sessions down-day max volume
        prev_slice = df.iloc[i - 10 : i]
        prev_closes = closes.iloc[i - 11 : i].values
        down_vols = [
            float(prev_slice["volume"].iloc[k])
            for k in range(len(prev_slice))
            if float(prev_slice["close"].iloc[k]) < float(prev_closes[k])
        ]
        max_down_vol = max(down_vols) if down_vols else float(vols.iloc[i - 10 : i].mean())
        if max_down_vol <= 0:
            continue

        cur_vol = float(vols.iloc[i])
        if cur_vol <= max_down_vol:
            continue

        # Must be near EMA 10 or SMA 50 (within -2% to +5.5% above)
        e10 = float(ema10.iloc[i])
        s50 = float(sma50.iloc[i]) if pd.notna(sma50.iloc[i]) else e10
        near_e10 = (lo <= e10 * 1.035) and (c >= e10 * 0.99) and (c <= e10 * 1.06)
        near_s50 = (lo <= s50 * 1.035) and (c >= s50 * 0.99) and (c <= s50 * 1.06)
        if not (near_e10 or near_s50):
            continue

        recent_dates.append(str(dates.iloc[i]))
        if i >= n - 3:
            latest_hit = True
            latest_ratio = round(cur_vol / max_down_vol, 2)

    return {
        "detected": latest_hit,
        "recent_dates": recent_dates[-5:],
        "vol_vs_max_down": latest_ratio,
        "summary": (
            f"Pocket Pivot ativo (volume {latest_ratio:.2f}x maior dia vendedor de 10d junto à EMA10/SMA50)."
            if latest_hit and latest_ratio
            else "Sem Pocket Pivot nas últimas 3 sessões."
        ),
    }


def detect_ttm_squeeze(df: pd.DataFrame) -> dict[str, Any]:
    """
    John Carter TTM Squeeze:
    - Bollinger Bands (20, 2.0) inside Keltner Channels (20, 1.5 * ATR20) => SQUEEZE ON
    - Squeeze turns OFF while momentum > 0 and rising => SQUEEZE FIRE LONG!
    """
    n = len(df)
    if n < 35:
        return {
            "squeeze_on": False,
            "squeeze_fire_long": False,
            "squeeze_bars": 0,
            "momentum": None,
            "state": "NEUTRO",
            "summary": "Histórico insuficiente para TTM Squeeze.",
        }

    closes = df["close"].astype(float)
    highs = df["high"].astype(float)
    lows = df["low"].astype(float)

    sma20 = closes.rolling(20).mean()
    std20 = closes.rolling(20).std(ddof=0)
    bb_upper = sma20 + 2.0 * std20
    bb_lower = sma20 - 2.0 * std20

    tr = pd.concat(
        [
            highs - lows,
            (highs - closes.shift(1)).abs(),
            (lows - closes.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr20 = tr.rolling(20).mean()
    kc_upper = sma20 + 1.5 * atr20
    kc_lower = sma20 - 1.5 * atr20

    sq_series = (bb_upper < kc_upper) & (bb_lower > kc_lower)

    # Momentum oscillator: close - midpoint(Donchian20, SMA20), smoothed by 5-bar mean
    donchian_mid = (highs.rolling(20).max() + lows.rolling(20).min()) / 2.0
    mom_raw = closes - ((donchian_mid + sma20) / 2.0)
    mom = mom_raw.rolling(5).mean()

    sq_on_now = bool(sq_series.iloc[-1])
    mom_now = _safe_float(mom.iloc[-1]) or 0.0
    mom_prev = _safe_float(mom.iloc[-2]) or 0.0
    mom_rising = mom_now > 0 and mom_now >= mom_prev

    # Count consecutive squeeze bars (ending today or ending right before fire)
    sq_bars = 0
    for val in reversed(sq_series.iloc[-25:].tolist()):
        if val:
            sq_bars += 1
        else:
            break

    # Check if squeeze fired within last 3 bars (was ON for >= 3 bars prior, now OFF, positive rising momentum)
    fire_long = False
    if not sq_on_now and mom_rising:
        recent_flags = sq_series.iloc[-10:-1].tolist()
        if sum(1 for x in recent_flags[-5:] if x) >= 2:
            fire_long = True

    if fire_long:
        state = "SQUEEZE_FIRE"
        summary = "TTM Squeeze DISPAROU a favor da alta (libertação de compressão com momentum positivo)."
    elif sq_on_now:
        state = "SQUEEZE_ON"
        summary = f"TTM Squeeze ATIVO há {sq_bars} sessões (Bollinger dentro de Keltner — energia comprimida)."
    else:
        state = "NEUTRO"
        summary = "Sem compressão TTM Squeeze ativa."

    return {
        "squeeze_on": sq_on_now,
        "squeeze_fire_long": fire_long,
        "squeeze_bars": sq_bars,
        "momentum": round(mom_now, 4),
        "momentum_rising": bool(mom_rising),
        "state": state,
        "summary": summary,
    }


def detect_episodic_pivot(df: pd.DataFrame, asset_type: str = "stock") -> dict[str, Any]:
    """
    Qullamaggie / Stockbee Episodic Pivot (EP):
    - Gap-up >= +8% (stocks) or strong catalyst surge >= +10% on volume >= 2.0x 50d average
    - Occurring within the last 5 trading sessions after a non-parabolic prior base
    """
    n = len(df)
    if n < 60:
        return {"detected": False, "gap_pct": None, "volume_ratio": None, "date": None}

    opens = df["open"].astype(float)
    closes = df["close"].astype(float)
    vols = df["volume"].astype(float)
    dates = df["date"].astype(str)
    vol_sma50 = vols.rolling(50).mean()

    gap_thresh = 8.0 if asset_type == "stock" else 10.0

    for i in range(n - 1, max(n - 6, 51), -1):
        prev_c = float(closes.iloc[i - 1])
        op = float(opens.iloc[i])
        cl = float(closes.iloc[i])
        v50 = float(vol_sma50.iloc[i - 1]) if pd.notna(vol_sma50.iloc[i - 1]) else 0.0
        if prev_c <= 0 or v50 <= 0:
            continue
        gap_pct = (op - prev_c) / prev_c * 100.0
        day_chg = (cl - prev_c) / prev_c * 100.0
        vol_ratio = float(vols.iloc[i]) / v50

        # Ensure prior 60 sessions weren't already a 150%+ parabola
        prior_base_start = max(0, i - 60)
        prior_low = float(closes.iloc[prior_base_start:i].min())
        prior_gain = ((prev_c - prior_low) / prior_low * 100.0) if prior_low > 0 else 0.0

        is_ep_bar = (
            (gap_pct >= gap_thresh or day_chg >= gap_thresh + 2.0)
            and cl >= op * 0.97
            and vol_ratio >= 2.0
            and prior_gain <= 120.0
        )
        if is_ep_bar:
            return {
                "detected": True,
                "gap_pct": round(max(gap_pct, day_chg), 2),
                "volume_ratio": round(vol_ratio, 2),
                "date": str(dates.iloc[i]),
            }

    return {"detected": False, "gap_pct": None, "volume_ratio": None, "date": None}


def detect_high_tight_flag(df: pd.DataFrame, asset_type: str = "stock") -> dict[str, Any]:
    """
    William O'Neil / Qullamaggie High Tight Flag (HTF):
    - Pole: rapid >= +80% (stocks) / >= +100% (crypto) rally in ~4-10 weeks
    - Flag: tight sideways consolidation <= 25% deep lasting 8 to 40 sessions near the highs
    """
    n = len(df)
    if n < 70:
        return {"detected": False, "pole_gain_pct": None, "flag_depth_pct": None}

    highs = df["high"].astype(float)
    lows = df["low"].astype(float)
    closes = df["close"].astype(float)

    # Look for recent flag high within last 8..40 sessions
    flag_slice = df.iloc[-35:]
    peak_pos_in_slice = int(flag_slice["high"].astype(float).values.argmax())
    peak_idx = (n - 35) + peak_pos_in_slice
    bars_since_peak = (n - 1) - peak_idx

    if not (5 <= bars_since_peak <= 34):
        return {"detected": False, "pole_gain_pct": None, "flag_depth_pct": None}

    peak_high = float(highs.iloc[peak_idx])
    pole_start = max(0, peak_idx - 50)
    pole_low = float(lows.iloc[pole_start:peak_idx].min()) if peak_idx > pole_start else peak_high
    pole_gain = ((peak_high - pole_low) / pole_low * 100.0) if pole_low > 0 else 0.0

    flag_low = float(lows.iloc[peak_idx:].min())
    flag_depth = ((peak_high - flag_low) / peak_high * 100.0) if peak_high > 0 else 100.0
    cur_price = float(closes.iloc[-1])

    min_pole = 75.0 if asset_type == "stock" else 95.0
    max_flag = 25.0 if asset_type == "stock" else 30.0

    detected = bool(
        pole_gain >= min_pole
        and flag_depth <= max_flag
        and cur_price >= peak_high * 0.80
    )
    return {
        "detected": detected,
        "pole_gain_pct": round(pole_gain, 1),
        "flag_depth_pct": round(flag_depth, 1),
    }


def detect_three_weeks_tight(df: pd.DataFrame, asset_type: str = "stock") -> dict[str, Any]:
    """
    William O'Neil 3 Weeks Tight (3WT):
    - 3 consecutive weekly closes within <= 1.8% (stocks) or <= 3.8% (crypto)
    """
    if len(df) < 30:
        return {"detected": False, "spread_pct": None}

    work = df.copy()
    work["dt"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["dt"]).set_index("dt")
    weekly_closes = work["close"].astype(float).resample("W-FRI").last().dropna()
    if len(weekly_closes) < 4:
        return {"detected": False, "spread_pct": None}

    last3 = weekly_closes.iloc[-3:].values
    max_c, min_c = float(np.max(last3)), float(np.min(last3))
    spread = ((max_c - min_c) / max_c * 100.0) if max_c > 0 else 100.0
    thresh = 1.8 if asset_type == "stock" else 3.8
    return {
        "detected": bool(spread <= thresh),
        "spread_pct": round(spread, 2),
    }


def compute_canslim_score(
    fundamentals: Optional[dict[str, Any]],
    rs_rating: int,
    stage: int,
    asset_type: str = "stock",
) -> dict[str, Any]:
    """William O'Neil CAN SLIM fundamental + leadership sub-score (0-100)."""
    if asset_type == "crypto" or not fundamentals or not fundamentals.get("available"):
        return {"score": None, "grade": "N/A", "highlights": []}

    pts = 0
    highlights: list[str] = []
    eg = _safe_float(fundamentals.get("earnings_growth"))
    rg = _safe_float(fundamentals.get("revenue_growth"))
    roe = _safe_float(fundamentals.get("return_on_equity"))
    pm = _safe_float(fundamentals.get("profit_margins"))

    # C / A: Earnings growth >= 25%
    if eg is not None:
        if eg >= 0.25:
            pts += 30
            highlights.append(f"C/A Lucros +{eg * 100:.0f}% (≥25%)")
        elif eg >= 0.10:
            pts += 15
            highlights.append(f"C/A Lucros +{eg * 100:.0f}%")

    # Sales growth >= 20-25%
    if rg is not None:
        if rg >= 0.20:
            pts += 25
            highlights.append(f"Receitas +{rg * 100:.0f}%")
        elif rg >= 0.10:
            pts += 12

    # ROE >= 17% (O'Neil hallmark)
    if roe is not None:
        if roe >= 0.17:
            pts += 20
            highlights.append(f"ROE {roe * 100:.0f}% (≥17%)")
        elif roe >= 0.10:
            pts += 10

    if pm is not None and pm > 0.10:
        pts += 5

    # L / N: Leadership (RS >= 80 & Stage 2)
    if rs_rating >= 80:
        pts += 12
    elif rs_rating >= 65:
        pts += 6
    if stage == 2:
        pts += 8

    score = min(pts, 100)
    grade = "A+" if score >= 85 else ("A" if score >= 70 else ("B" if score >= 50 else "C"))
    return {"score": score, "grade": grade, "highlights": highlights}


def compute_anchored_vwaps(df: pd.DataFrame) -> dict[str, Any]:
    """
    Brian Shannon Anchored VWAP (AVWAP):
    - Anchored to major Swing Low (lowest low of last ~120 sessions)
    - Anchored to Year-to-Date (first session of latest calendar year)
    Returns series ready for TradingView Lightweight Charts + current values.
    """
    n = len(df)
    if n < 20:
        return {"swing_low": [], "ytd": [], "above_avwap_swing": None, "above_avwap_ytd": None}

    def _calc_from_idx(start_idx: int) -> list[dict[str, Any]]:
        sub = df.iloc[start_idx:].copy()
        tp = (sub["high"].astype(float) + sub["low"].astype(float) + sub["close"].astype(float)) / 3.0
        vol = sub["volume"].astype(float).clip(lower=0.0)
        cum_pv = (tp * vol).cumsum()
        cum_v = vol.cumsum().replace(0, np.nan)
        avwap = cum_pv / cum_v
        out = []
        for dt, val in zip(sub["date"].astype(str), avwap):
            if pd.notna(val):
                out.append({"time": dt, "value": round(float(val), 5)})
        return out

    # 1. Swing Low anchor (within last 130 bars, excluding very last 3 bars)
    win = min(130, n - 3)
    search_start = max(0, n - 3 - win)
    lows = df["low"].astype(float).values[search_start : n - 3]
    swing_low_idx = search_start + int(np.argmin(lows)) if len(lows) > 0 else 0
    avwap_swing = _calc_from_idx(swing_low_idx)

    # 2. YTD anchor (first session of the latest year in the dataset)
    last_year = str(df["date"].iloc[-1])[:4]
    ytd_matches = df.index[df["date"].astype(str).str.startswith(last_year)].tolist()
    ytd_idx = int(ytd_matches[0]) if ytd_matches else max(0, n - 60)
    avwap_ytd = _calc_from_idx(ytd_idx)

    price = float(df["close"].iloc[-1])
    above_swing = bool(avwap_swing and price > avwap_swing[-1]["value"]) if avwap_swing else None
    above_ytd = bool(avwap_ytd and price > avwap_ytd[-1]["value"]) if avwap_ytd else None

    return {
        "swing_low": avwap_swing,
        "swing_low_anchor_date": str(df["date"].iloc[swing_low_idx]),
        "ytd": avwap_ytd,
        "ytd_anchor_date": str(df["date"].iloc[ytd_idx]),
        "above_avwap_swing": above_swing,
        "above_avwap_ytd": above_ytd,
    }


def evaluate_multi_strategy_signals(
    df: pd.DataFrame,
    benchmark_df: Optional[pd.DataFrame],
    asset_type: str = "stock",
    fundamentals: Optional[dict[str, Any]] = None,
    rs_rating: int = 50,
    stop_loss_pct: float = 6.0,
) -> dict[str, Any]:
    """Aggregates all complementary methodologies into one clean, structured dict."""
    weinstein = compute_weinstein_stage(df)
    mansfield_rs = compute_mansfield_rs(df, benchmark_df)
    vol_metrics = compute_adr_and_atr_extension(df)
    pocket = detect_pocket_pivot(df, stage=weinstein["stage"])
    squeeze = detect_ttm_squeeze(df)
    ep = detect_episodic_pivot(df, asset_type=asset_type)
    htf = detect_high_tight_flag(df, asset_type=asset_type)
    wt3 = detect_three_weeks_tight(df, asset_type=asset_type)
    canslim = compute_canslim_score(fundamentals, rs_rating=rs_rating, stage=weinstein["stage"], asset_type=asset_type)

    # Stop vs ADR check (Qullamaggie rule: stop shouldn't be tighter than ~0.7x ADR or noise will stop you out)
    adr = vol_metrics.get("adr_pct_20d")
    stop_in_adr = round(stop_loss_pct / adr, 2) if (adr and adr > 0) else None
    stop_too_tight_for_adr = bool(stop_in_adr is not None and stop_in_adr < 0.75)

    active_tags: list[str] = []
    if pocket["detected"]:
        active_tags.append("POCKET_PIVOT")
    if squeeze["squeeze_fire_long"]:
        active_tags.append("SQUEEZE_FIRE")
    elif squeeze["squeeze_on"]:
        active_tags.append("TTM_SQUEEZE")
    if ep["detected"]:
        active_tags.append("EPISODIC_PIVOT")
    if htf["detected"]:
        active_tags.append("HIGH_TIGHT_FLAG")
    if wt3["detected"]:
        active_tags.append("3_WEEKS_TIGHT")

    return {
        "weinstein": weinstein,
        "mansfield_rs": mansfield_rs,
        "adr_pct_20d": vol_metrics["adr_pct_20d"],
        "adr_tier": vol_metrics["adr_tier"],
        "atr_pct_14": vol_metrics["atr_pct_14"],
        "atr_extension_sma50": vol_metrics["atr_extension_sma50"],
        "is_atr_overextended": vol_metrics["is_atr_overextended"],
        "stop_in_adr_multiples": stop_in_adr,
        "stop_too_tight_for_adr": stop_too_tight_for_adr,
        "pocket_pivot": pocket,
        "ttm_squeeze": squeeze,
        "episodic_pivot": ep,
        "high_tight_flag": htf,
        "three_weeks_tight": wt3,
        "canslim": canslim,
        "active_tags": active_tags,
    }
