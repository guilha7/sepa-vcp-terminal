import numpy as np
import pandas as pd

from app.services.quant_signals import (
    compute_adr_and_atr_extension,
    compute_anchored_vwaps,
    compute_canslim_score,
    compute_mansfield_rs,
    compute_weinstein_stage,
    detect_episodic_pivot,
    detect_high_tight_flag,
    detect_pocket_pivot,
    detect_three_weeks_tight,
    detect_ttm_squeeze,
)


def _df_from_closes(closes, vols=None, spread=0.012, opens=None):
    n = len(closes)
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    c = np.asarray(closes, dtype=float)
    o = np.asarray(opens, dtype=float) if opens is not None else c * 0.997
    h = np.maximum(c, o) * (1.0 + spread)
    l = np.minimum(c, o) * (1.0 - spread)
    v = np.asarray(vols, dtype=float) if vols is not None else np.full(n, 2_000_000.0)
    return pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": o,
            "high": h,
            "low": l,
            "close": c,
            "volume": v,
        }
    )


def test_weinstein_stage2_and_stage4_and_mansfield_rs():
    up_df = _df_from_closes(np.linspace(50.0, 150.0, 260))
    down_df = _df_from_closes(np.linspace(150.0, 50.0, 260))
    bench_df = _df_from_closes(np.linspace(100.0, 115.0, 260))

    s_up = compute_weinstein_stage(up_df)
    s_down = compute_weinstein_stage(down_df)
    assert s_up["stage"] == 2
    assert s_down["stage"] == 4

    mrs_up = compute_mansfield_rs(up_df, bench_df)
    mrs_down = compute_mansfield_rs(down_df, bench_df)
    assert mrs_up is not None and mrs_up > 10.0
    assert mrs_down is not None and mrs_down < -10.0


def test_qullamaggie_adr_and_atr_extension():
    # High volatility 5% daily range stock
    df = _df_from_closes(np.linspace(80.0, 120.0, 80), spread=0.03)
    res = compute_adr_and_atr_extension(df)
    assert res["adr_pct_20d"] >= 5.0
    assert res["adr_tier"] == "EXPLOSIVO"
    assert res["atr_extension_sma50"] is not None


def test_morales_pocket_pivot():
    # Uptrend pulling gently to EMA10, then strong up day eclipsing max down-day volume of prior 10 bars
    n = 100
    closes = np.linspace(80.0, 100.0, n)
    vols = np.full(n, 1_500_000.0)
    # Create a few down days in prior 10 bars with max vol 1.8M
    closes[93] = closes[92] * 0.99
    vols[93] = 1_800_000.0
    closes[96] = closes[95] * 0.992
    vols[96] = 1_600_000.0
    # Final bar: up day near EMA10 with 3.2M volume!
    closes[99] = closes[98] * 1.022
    vols[99] = 3_200_000.0

    df = _df_from_closes(closes, vols=vols, spread=0.008)
    pp = detect_pocket_pivot(df, stage=2)
    assert pp["detected"] is True
    assert pp["vol_vs_max_down"] >= 1.5
    assert len(pp["recent_dates"]) >= 1


def test_ttm_squeeze_on():
    # First 50 bars volatile, last 25 bars ultra-tight -> Bollinger inside Keltner (SQUEEZE ON)
    rng = np.random.default_rng(42)
    part1 = 100.0 + np.cumsum(rng.normal(0.0, 3.0, 50))
    part2 = np.full(25, part1[-1]) + rng.normal(0.0, 0.08, 25)
    closes = np.concatenate([part1, part2])
    df = _df_from_closes(closes, spread=0.004)
    # Give wide true range in part2 highs/lows vs tight closes so KC > BB
    df.loc[50:, "high"] = df.loc[50:, "close"] * 1.018
    df.loc[50:, "low"] = df.loc[50:, "close"] * 0.982
    sq = detect_ttm_squeeze(df)
    assert sq["squeeze_on"] is True
    assert sq["squeeze_bars"] >= 5


def test_episodic_pivot_high_tight_flag_3wt_canslim_and_avwap():
    # 1. Episodic Pivot: flat base then +14% gap-up with 3.5x volume
    closes = np.full(80, 50.0)
    opens = np.full(80, 50.0)
    vols = np.full(80, 1_000_000.0)
    opens[79] = 57.0  # +14% gap
    closes[79] = 59.0
    vols[79] = 3_500_000.0
    ep_df = _df_from_closes(closes, vols=vols, opens=opens, spread=0.008)
    ep = detect_episodic_pivot(ep_df, asset_type="stock")
    assert ep["detected"] is True
    assert ep["gap_pct"] >= 12.0

    # 2. High Tight Flag: +110% pole in 30 bars, then tight 10% flag for 15 bars
    pole = np.linspace(40.0, 88.0, 45)
    flag = np.linspace(87.0, 81.0, 8).tolist() + np.linspace(82.0, 86.5, 10).tolist()
    htf_df = _df_from_closes(np.concatenate([np.full(30, 40.0), pole, flag]), spread=0.01)
    htf = detect_high_tight_flag(htf_df, asset_type="stock")
    assert htf["detected"] is True
    assert htf["pole_gain_pct"] >= 100.0
    assert htf["flag_depth_pct"] <= 20.0

    # 3. 3 Weeks Tight
    wt_df = _df_from_closes(np.concatenate([np.linspace(80.0, 100.0, 30), np.full(20, 100.2)]), spread=0.005)
    wt = detect_three_weeks_tight(wt_df, asset_type="stock")
    assert wt["detected"] is True

    # 4. CAN SLIM Score
    cs = compute_canslim_score(
        {"available": True, "earnings_growth": 0.45, "revenue_growth": 0.32, "return_on_equity": 0.28, "profit_margins": 0.22},
        rs_rating=92,
        stage=2,
    )
    assert cs["score"] >= 85
    assert cs["grade"] == "A+"

    # 5. Anchored VWAP (Swing Low & YTD)
    av = compute_anchored_vwaps(htf_df)
    assert len(av["swing_low"]) >= 10
    assert len(av["ytd"]) >= 10
    assert av["above_avwap_swing"] is True
