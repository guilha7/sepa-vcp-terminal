import numpy as np
import pandas as pd

from app.services.minervini_vcp import (
    analyze_sepa_vcp,
    check_liquidity,
    detect_vcp,
    evaluate_trend_template,
)


def _make_benchmark_df(n: int = 300, start: float = 400.0, daily_drift: float = 0.0004) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    closes = [start * ((1 + daily_drift) ** i) for i in range(n)]
    return pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": closes,
            "high": [c * 1.005 for c in closes],
            "low": [c * 0.995 for c in closes],
            "close": closes,
            "volume": [50_000_000.0] * n,
        }
    )


def _make_stage2_vcp_breakout_df(n: int = 300) -> pd.DataFrame:
    """
    Constructs a textbook Minervini Stage 2 uptrend ending in a 3-leg VCP contraction
    (T1 ~20%, T2 ~10%, T3 ~4%) + Volume Dry-Up + 2.4x Volume Breakout on the final bar.
    """
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    closes = np.zeros(n)
    highs = np.zeros(n)
    lows = np.zeros(n)
    opens = np.zeros(n)
    vols = np.full(n, 2_000_000.0)

    # First 240 sessions: steady Stage 2 uptrend from 50 -> 150
    for i in range(240):
        c = 50.0 + (100.0 * i / 239.0)
        closes[i] = c
        opens[i] = c * 0.995
        highs[i] = c * 1.015
        lows[i] = c * 0.985

    pivot = 150.0
    # Base segment 1 (240..266): 20% contraction (150 -> 120 -> 148)
    seg1 = np.concatenate([np.linspace(150.0, 120.0, 13), np.linspace(122.0, 148.0, 14)])
    for k, val in enumerate(seg1):
        idx = 240 + k
        closes[idx] = val
        opens[idx] = val
        highs[idx] = min(val * 1.01, pivot)
        lows[idx] = val * 0.99

    # Base segment 2 (267..285): 10% contraction (148 -> 134 -> 149)
    seg2 = np.concatenate([np.linspace(148.0, 134.0, 9), np.linspace(136.0, 149.0, 10)])
    for k, val in enumerate(seg2):
        idx = 267 + k
        closes[idx] = val
        opens[idx] = val
        highs[idx] = min(val * 1.006, pivot)
        lows[idx] = val * 0.994
        vols[idx] = 1_600_000.0

    # Base segment 3 (286..298): tight 3.5% contraction (149 -> 144 -> 149.2) with Volume Dry-Up!
    seg3 = np.concatenate([np.linspace(149.0, 144.5, 6), np.linspace(145.5, 149.2, 7)])
    for k, val in enumerate(seg3):
        idx = 286 + k
        closes[idx] = val
        opens[idx] = val * 0.998
        highs[idx] = min(val * 1.004, pivot)
        lows[idx] = val * 0.996
        vols[idx] = 850_000.0  # Strong Volume Dry-Up (< 0.5x avg)

    # Final bar (299): Valid Breakout above pivot 150 with 2.4x average volume
    opens[299] = 149.5
    lows[299] = 149.2
    closes[299] = 152.5
    highs[299] = 153.2
    vols[299] = 4_800_000.0

    return pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": vols,
        }
    )


def _make_stage4_downtrend_df(n: int = 300) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    closes = np.linspace(200.0, 75.0, n)
    return pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": closes * 1.01,
            "high": closes * 1.02,
            "low": closes * 0.98,
            "close": closes,
            "volume": np.full(n, 2_000_000.0),
        }
    )


def test_stage2_trend_template_and_vcp_breakout():
    df = _make_stage2_vcp_breakout_df()
    bench = _make_benchmark_df()

    result = analyze_sepa_vcp(
        ticker="TEST",
        df=df,
        benchmark_df=bench,
        asset_type="stock",
        benchmark_ticker="SPY",
    )

    assert result["liquidity"]["passed"] is True
    assert result["trend_template"]["passed"] is True
    assert result["trend_template"]["passed_count"] == 8
    assert result["vcp"]["detected"] is True
    c1, c2, c3 = result["vcp"]["contractions_pct"]
    assert c1 > c2 > c3
    assert result["vcp"]["volume_dry_up"] is True
    assert result["vcp"]["breakout_signal"] is True
    assert result["status"] == "BREAKOUT"
    assert result["score"] >= 85.0
    assert result["trade_plan"]["stop_loss_pct"] <= 6.0
    assert result["trade_plan"]["target_2r"] > result["trade_plan"]["entry_pivot"]
    assert result["trade_plan"]["target_3r"] > result["trade_plan"]["target_2r"]
    assert len(result["why_opportunity"]) >= 4


def test_stage4_downtrend_fails_minervini():
    df = _make_stage4_downtrend_df()
    bench = _make_benchmark_df()

    tt = evaluate_trend_template(df, bench, ticker="BEAR", asset_type="stock")
    assert tt["passed"] is False
    assert tt["passed_count"] <= 2

    res = analyze_sepa_vcp("BEAR", df, bench, asset_type="stock")
    assert res["status"] == "FORA_STAGE2"
    assert res["score"] < 40.0


def test_anti_error_liquidity_and_earnings_alert():
    df = _make_stage2_vcp_breakout_df()
    bench = _make_benchmark_df()

    # Penny stock rejected
    penny = df.copy()
    penny[["open", "high", "low", "close"]] = penny[["open", "high", "low", "close"]] / 50.0
    liq = check_liquidity(penny, asset_type="stock")
    assert liq["passed"] is False

    # Earnings within 14 days triggers red alert & penalty
    no_earn = analyze_sepa_vcp("NVDA", df, bench, fundamentals={"earnings_within_14d": False})
    with_earn = analyze_sepa_vcp(
        "NVDA",
        df,
        bench,
        fundamentals={
            "earnings_within_14d": True,
            "next_earnings_date": "2026-12-01",
            "days_to_earnings": 5,
        },
    )
    assert with_earn["earnings_within_14d"] is True
    assert with_earn["score"] < no_earn["score"]
    assert any("EARNINGS" in w["topic"] for w in with_earn["why_opportunity"])
