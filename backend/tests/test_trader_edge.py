from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from app.services.trader_edge import (
    compute_dcr_and_volume_runrate,
    compute_mtf_confluence,
    compute_sector_peer_rs,
    get_upcoming_macro_events,
)


def _make_df(closes: list[float], highs=None, lows=None, vols=None, start="2025-01-02") -> pd.DataFrame:
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    c = np.array(closes, dtype=float)
    h = np.array(highs, dtype=float) if highs is not None else c * 1.01
    l = np.array(lows, dtype=float) if lows is not None else c * 0.99
    v = np.array(vols, dtype=float) if vols is not None else np.full(n, 1_000_000.0)
    return pd.DataFrame({"date": dates, "open": c * 0.998, "high": h, "low": l, "close": c, "volume": v})


def test_dcr_and_intraday_projected_volume():
    # 1. Strong top close (DCR 90%) + mid-session US intraday projection (halfway through session -> 2x projected)
    closes = [100.0] * 50 + [109.0]
    highs = [101.0] * 50 + [110.0]
    lows = [99.0] * 50 + [100.0]
    vols = [1_000_000.0] * 50 + [1_000_000.0]
    df = _make_df(closes, highs=highs, lows=lows, vols=vols)
    last_dt = date.fromisoformat(df["date"].iloc[-1])

    # Mid-session NY (12:45 EST = 17:45 UTC in winter -> 195 min / 390 min = 0.50 elapsed!)
    # Force a weekday date in January for deterministic EST (UTC-5)
    df.loc[df.index[-1], "date"] = "2026-01-15"
    now_mid_ny = datetime(2026, 1, 15, 17, 45, tzinfo=timezone.utc)
    res = compute_dcr_and_volume_runrate(df, ticker="NVDA", asset_type="stock", now_utc=now_mid_ny)
    assert res["available"] is True
    assert res["dcr_pct"] == 90.0
    assert res["dcr_state"] == "FORTE"
    assert res["is_intraday_projected"] is True
    assert 1.9 <= res["projected_volume_ratio"] <= 2.1

    # 2. Weak close near lows (DCR 10%) after market close -> FRACO, not projected
    df.loc[df.index[-1], "close"] = 101.0
    now_after = datetime(2026, 1, 15, 22, 30, tzinfo=timezone.utc)
    res_weak = compute_dcr_and_volume_runrate(df, ticker="NVDA", asset_type="stock", now_utc=now_after)
    assert res_weak["dcr_pct"] == 10.0
    assert res_weak["dcr_state"] == "FRACO"
    assert res_weak["is_intraday_projected"] is False


def test_mtf_confluence_aligned_overextended_and_downtrend():
    # Steady healthy uptrend (+0.15% per bar over 220 bars) -> ALINHADO
    steady = [100.0 * (1.0015 ** i) for i in range(220)]
    r_al = compute_mtf_confluence(_make_df(steady), asset_type="stock")
    assert r_al["available"] is True
    assert r_al["state"] == "ALINHADO"

    # Parabolic vertical spike at the end (> 15% above 10w SMA) -> ESTICADO_SEMANAL
    spiked = steady[:-10] + [steady[-11] * (1.035 ** k) for k in range(1, 11)]
    r_ext = compute_mtf_confluence(_make_df(spiked), asset_type="stock")
    assert r_ext["state"] == "ESTICADO_SEMANAL"
    assert r_ext["weekly_overextended"] is True

    # Clear downtrend -> BAIXA
    down = [200.0 * (0.997 ** i) for i in range(220)]
    r_dn = compute_mtf_confluence(_make_df(down), asset_type="stock")
    assert r_dn["state"] == "BAIXA"


def test_sector_peer_rs_leader_vs_laggard(monkeypatch):
    # Sector ETF XLK up +5% over 3M
    etf_closes = [100.0 + (i / 120.0) * 10.0 for i in range(120)]
    etf_df = _make_df(etf_closes)

    monkeypatch.setattr(
        "app.services.trader_edge.get_ohlcv",
        lambda tk, period="15mo", force_refresh=False: (etf_df, "mock", []),
    )

    # Stock up ~25% over 3M -> LIDER_SETOR
    leader_closes = [100.0 + (i / 120.0) * 60.0 for i in range(120)]
    r_lead = compute_sector_peer_rs("NVDA", _make_df(leader_closes), sector="Technology", asset_type="stock")
    assert r_lead["available"] is True
    assert r_lead["sector_etf"] == "XLK"
    assert r_lead["status"] == "LIDER_SETOR"
    assert r_lead["outperformance_3m_pct"] > 5.0

    # Stock flat -> ATRASADO_SETOR
    lag_closes = [100.0 - (i / 120.0) * 10.0 for i in range(120)]
    r_lag = compute_sector_peer_rs("INTC", _make_df(lag_closes), sector="Technology", asset_type="stock")
    assert r_lag["status"] == "ATRASADO_SETOR"

    # Sector ETF itself or crypto -> skipped gracefully
    assert compute_sector_peer_rs("XLK", etf_df, sector="Technology", asset_type="stock")["available"] is False
    assert compute_sector_peer_rs("BTC-USD", etf_df, sector="Technology", asset_type="crypto")["available"] is False


def test_macro_calendar_imminent_48h_only():
    # Dec 8, 2026: FOMC is Dec 9 (1 day away), CPI is Dec 10 (2 days away)
    ev_busy = get_upcoming_macro_events(reference_date=date(2026, 12, 8), window_days=2)
    assert ev_busy["has_imminent_event"] is True
    codes = {e["code"] for e in ev_busy["upcoming_within_48h"]}
    assert "FOMC" in codes
    assert "CPI" in codes

    # Nov 23, 2026: quiet normal day (no FOMC/CPI/NFP within 48h) -> completely silent!
    ev_quiet = get_upcoming_macro_events(reference_date=date(2026, 11, 23), window_days=2)
    assert ev_quiet["has_imminent_event"] is False
    assert ev_quiet["upcoming_within_48h"] == []
