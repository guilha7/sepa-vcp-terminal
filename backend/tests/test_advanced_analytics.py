import numpy as np
import pandas as pd

from app.database import Database
from app.models import PaperPositionCreate
from app.services.advanced_analytics import (
    compute_asset_personality_backtest,
    compute_volume_quality,
    fetch_institutional_and_quarterly,
)
from app.services.minervini_vcp import check_liquidity
from app.services.paper_trading import PaperTradingService


def _make_ohlcv(closes: list[float], volumes: list[float]) -> pd.DataFrame:
    n = len(closes)
    dates = pd.date_range("2024-01-01", periods=n, freq="B").strftime("%Y-%m-%d").tolist()
    arr_c = np.array(closes, dtype=float)
    return pd.DataFrame(
        {
            "date": dates,
            "open": arr_c * 0.995,
            "high": arr_c * 1.012,
            "low": arr_c * 0.988,
            "close": arr_c,
            "volume": np.array(volumes, dtype=float),
        }
    )


def test_oneil_volume_quality_accumulation_vs_distribution():
    # Strong accumulation: big volume on up days, tiny volume on down days
    closes = [100.0]
    vols = [1_000_000.0]
    for i in range(60):
        if i % 3 == 0:
            closes.append(closes[-1] * 0.995)
            vols.append(400_000.0)
        else:
            closes.append(closes[-1] * 1.008)
            vols.append(2_200_000.0)

    acc = compute_volume_quality(_make_ohlcv(closes, vols))
    assert acc["available"] is True
    assert acc["up_down_volume_ratio_50d"] >= 1.5
    assert acc["acc_dist_grade"] == "A"

    # Strong distribution: heavy selling on red days
    closes_d = [100.0]
    vols_d = [1_000_000.0]
    for i in range(60):
        if i % 3 == 0:
            closes_d.append(closes_d[-1] * 1.004)
            vols_d.append(400_000.0)
        else:
            closes_d.append(closes_d[-1] * 0.992)
            vols_d.append(2_500_000.0)

    dist = compute_volume_quality(_make_ohlcv(closes_d, vols_d))
    assert dist["available"] is True
    assert dist["up_down_volume_ratio_50d"] < 0.7
    assert dist["acc_dist_grade"] == "E"


def test_asset_personality_backtest_detects_clean_breakouts():
    # Build 260-day uptrend with clean consolidations followed by +15% surges on volume
    closes = [50.0 + i * 0.15 for i in range(65)]
    vols = [1_000_000.0] * 65

    for wave in range(3):
        base = closes[-1]
        # 22-day flat base
        for _ in range(22):
            closes.append(base * 0.995)
            vols.append(700_000.0)
        # Breakout day on 2.2x volume
        closes.append(base * 1.03)
        vols.append(2_400_000.0)
        # Follow-through +16% over next 12 bars
        for k in range(1, 13):
            closes.append(base * (1.03 + k * 0.014))
            vols.append(1_300_000.0)

    # Trailing 20 bars
    for _ in range(20):
        closes.append(closes[-1] * 1.001)
        vols.append(1_000_000.0)

    bt = compute_asset_personality_backtest(_make_ohlcv(closes, vols))
    assert bt["available"] is True
    assert bt["breakout_signals"] >= 2
    assert bt["wins_2r"] >= 2
    assert bt["win_rate_pct"] >= 60.0
    assert bt["best_trailing_ma"] in ("SMA10", "SMA21", "SMA50")


def test_region_aware_liquidity_for_portugal_and_europe():
    # Portuguese blue-chip like EDP.LS at 3.80 EUR with 300k EUR/day passes
    pt_df = _make_ohlcv([3.80] * 55, [85_000.0] * 55)
    assert check_liquidity(pt_df, asset_type="stock", ticker="EDP.LS")["passed"] is True
    # Same low price/volume fails strict US rule
    assert check_liquidity(pt_df, asset_type="stock", ticker="PENNY")["passed"] is False

    # European stock at 3.50 EUR with 2M EUR/day passes
    eu_df = _make_ohlcv([3.50] * 55, [600_000.0] * 55)
    assert check_liquidity(eu_df, asset_type="stock", ticker="SAN.MC")["passed"] is True


def test_institutional_skips_crypto_and_etf_cleanly():
    res_c = fetch_institutional_and_quarterly("BTC-USD")
    assert res_c["available"] is False
    res_e = fetch_institutional_and_quarterly("SPY", quote_type="ETF")
    assert res_e["available"] is False


def test_portfolio_heat_and_breakeven_zero_risk(tmp_path):
    test_db = Database(tmp_path / "heat_test.db")
    test_db.init_schema()
    svc = PaperTradingService(database=test_db)

    # Open 2 crypto positions of 50 EUR each with 6% stop -> 3€ risk each = 6€ total (6% of 100€)
    p1 = svc.open_position(
        PaperPositionCreate(
            ticker="BTC-USD",
            asset_type="crypto",
            asset_currency="EUR",
            entry_price=50000.0,
            capital_eur=50.0,
            stop_loss_pct=6.0,
        ),
        owner_name="guilherme",
    )
    svc.open_position(
        PaperPositionCreate(
            ticker="ETH-USD",
            asset_type="crypto",
            asset_currency="EUR",
            entry_price=3000.0,
            capital_eur=50.0,
            stop_loss_pct=6.0,
        ),
        owner_name="guilherme",
    )

    summary = svc.get_portfolio_summary(refresh_prices=False, owner_name="guilherme", base_capital_eur=100.0)
    heat = summary["portfolio_heat"]
    assert heat["open_risk_eur"] == 6.0
    assert heat["open_risk_pct"] == 6.0
    assert heat["heat_level"] == "MODERADO"
    assert heat["breakeven_protected_count"] == 0
    assert heat["concentration_warning"] is not None  # 100% in Criptomoedas!

    # Move BTC-USD to Breakeven -> open risk drops in half to 3.0 EUR (SEGURO) & breakeven_protected_count == 1
    svc.move_stop_to_breakeven(p1["id"], owner_name="guilherme")
    summary_after = svc.get_portfolio_summary(refresh_prices=False, owner_name="guilherme", base_capital_eur=100.0)
    heat_after = summary_after["portfolio_heat"]
    assert heat_after["open_risk_eur"] == 3.0
    assert heat_after["open_risk_pct"] == 3.0
    assert heat_after["heat_level"] == "SEGURO"
    assert heat_after["breakeven_protected_count"] == 1
