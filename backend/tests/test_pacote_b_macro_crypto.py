import numpy as np
import pandas as pd

from app.services.crypto_derivatives import (
    classify_funding_signal,
    classify_oi_price_flow,
    compute_altseason_gauge,
)
from app.services.macro_rotation import compute_ibd_market_timing, compute_stockbee_breadth


def _make_index_df(closes, vols):
    n = len(closes)
    dates = pd.date_range("2026-01-01", periods=n, freq="B")
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": c,
            "high": c * 1.005,
            "low": c * 0.995,
            "close": c,
            "volume": np.asarray(vols, dtype=float),
        }
    )


def test_ibd_distribution_days_and_5pct_expiry():
    # Uptrend with 5 distribution days in last 20 bars
    n = 80
    closes = np.linspace(500.0, 560.0, n)
    vols = np.full(n, 50_000_000.0)
    for idx in (60, 64, 68, 72, 76):
        closes[idx] = closes[idx - 1] * 0.992  # -0.8% down day
        vols[idx] = 75_000_000.0  # higher volume than prev day

    df = _make_index_df(closes, vols)
    res = compute_ibd_market_timing(df, "SPY")
    assert res["distribution_days"] >= 5
    assert res["status"] in ("UPTREND_UNDER_PRESSURE", "MARKET_IN_CORRECTION")

    # Now rally +7% on final day -> all prior distribution days should expire!
    closes_rally = closes.copy()
    closes_rally[-1] = np.max(closes) * 1.07
    df_rally = _make_index_df(closes_rally, vols)
    res_rally = compute_ibd_market_timing(df_rally, "SPY")
    assert res_rally["distribution_days"] == 0
    assert res_rally["status"] == "UPTREND_CONFIRMED"


def test_ibd_follow_through_day_detection():
    n = 70
    closes = np.concatenate([np.linspace(550.0, 480.0, 60), np.linspace(481.0, 488.0, 5), [498.5], np.linspace(499.0, 504.0, 4)])
    vols = np.full(n, 50_000_000.0)
    # Day 65 (offset 5 after local low at index 59) surges +2.15% on expanding volume -> FTD!
    vols[65] = 85_000_000.0
    df = _make_index_df(closes, vols)
    res = compute_ibd_market_timing(df, "QQQ")
    assert res["follow_through_day"] is True
    assert res["ftd_date"] is not None


def test_stockbee_breadth_4pct_counts():
    # Build 10 synthetic stocks: 7 strongly above SMA50 with +5% surge on final bar, 3 weak
    extra = {}
    for i in range(7):
        c = np.linspace(50.0, 70.0, 70)
        c[-1] = c[-2] * 1.055  # +5.5% breakout
        v = np.full(70, 2_000_000.0)
        v[-1] = 3_500_000.0
        extra[f"BULL{i}"] = _make_index_df(c, v)
    # Note: compute_stockbee_breadth inspects watchlist + sector ETFs; pass sector ETF keys directly
    etf_keys = ["XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"]
    etf_dfs = {}
    for idx, k in enumerate(etf_keys):
        c = np.linspace(50.0, 75.0, 70)
        v = np.full(70, 5_000_000.0)
        if idx < 8:
            c[-1] = c[-2] * 1.05
            v[-1] = 9_000_000.0
        etf_dfs[k] = _make_index_df(c, v)

    b = compute_stockbee_breadth(etf_dfs)
    assert b["universe_size"] >= 11
    assert b["up_4pct_today"] >= 8


def test_crypto_derivatives_signals_and_altseason():
    assert classify_funding_signal(0.08)["code"] == "EUFORIA"
    assert classify_funding_signal(-0.03)["code"] == "SHORT_SQUEEZE"
    assert classify_funding_signal(0.01)["code"] == "SAUDAVEL"

    assert classify_oi_price_flow(3.5, 6.0)["code"] == "DINHEIRO_NOVO_BULL"
    assert classify_oi_price_flow(2.5, -4.0)["code"] == "SHORT_COVERING"
    assert classify_oi_price_flow(-3.0, 5.0)["code"] == "SHORTING_AGRESSIVO"
    assert classify_oi_price_flow(-4.0, -5.0)["code"] == "LIQUIDACAO_LONGS"

    # Altseason: ETH and alts strongly outperforming BTC over 30d
    btc = _make_index_df(np.linspace(60000, 62000, 70), np.full(70, 1e9))
    eth = _make_index_df(np.linspace(2500, 3500, 70), np.full(70, 5e8))
    sol = _make_index_df(np.linspace(120, 210, 70), np.full(70, 3e8))
    avax = _make_index_df(np.linspace(25, 42, 70), np.full(70, 1e8))
    gauge = compute_altseason_gauge({"BTC-USD": btc, "ETH-USD": eth, "SOL-USD": sol, "AVAX-USD": avax})
    assert gauge["regime"] == "ALTSEASON"
    assert gauge["eth_btc_above_sma50"] is True
    assert gauge["alts_beating_btc_pct"] == 100.0
