import numpy as np
import pandas as pd
import pytest

from app.database import Database
from app.models import PaperPositionCreate, PaperPositionJournalUpdate, PositionCalcRequest
from app.services.minervini_vcp import analyze_sepa_vcp, compute_rs_line_series
from app.services.notifications import NotificationService
from app.services.paper_trading import PaperTradingService, calculate_position
from app.services.xray_service import build_chart_payload


def test_real_swing_vcp_legs_rs_new_high_before_price_and_weekly_chart():
    n = 300
    dates = pd.date_range("2025-01-01", periods=n, freq="B")
    # Benchmark dips in the last 30 bars while stock holds tight right below its 52w high -> RS New High Before Price!
    bench_c = np.concatenate([np.linspace(400.0, 460.0, 260), np.linspace(460.0, 420.0, 40)])
    bench = pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": bench_c,
            "high": bench_c * 1.005,
            "low": bench_c * 0.995,
            "close": bench_c,
            "volume": [40_000_000.0] * n,
        }
    )

    closes = np.zeros(n)
    highs = np.zeros(n)
    lows = np.zeros(n)
    opens = np.zeros(n)
    vols = np.full(n, 2_000_000.0)

    for i in range(230):
        c = 50.0 + (100.0 * i / 229.0)
        closes[i] = c
        opens[i] = c * 0.995
        highs[i] = c * 1.01
        lows[i] = c * 0.99

    # Peak at 155 then 3 clean ZigZag contractions: 22% -> 11% -> 4% holding below 155 (at 151)
    seg = np.concatenate(
        [
            [155.0],
            np.linspace(154.0, 121.0, 15),   # T1 (~22%)
            np.linspace(123.0, 152.0, 14),
            np.linspace(151.0, 135.0, 12),   # T2 (~11%)
            np.linspace(136.0, 151.5, 11),
            np.linspace(151.0, 145.0, 8),    # T3 (~4%)
            np.linspace(146.0, 151.0, 9),
        ]
    )
    for k, val in enumerate(seg):
        idx = 230 + k
        closes[idx] = val
        opens[idx] = val * 0.998
        highs[idx] = val * 1.004
        lows[idx] = val * 0.996
        if idx >= 290:
            vols[idx] = 800_000.0

    df = pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": vols,
        }
    )

    sepa = analyze_sepa_vcp("LEAD", df, bench, asset_type="stock", benchmark_ticker="SPY")
    assert sepa["trend_template"]["passed"] is True
    assert sepa["vcp"]["detected"] is True
    assert sepa["vcp"]["detection_method"] == "zigzag_swings"
    legs = sepa["vcp"]["contraction_legs"]
    assert len(legs) >= 3
    assert all("start_date" in lg and "end_date" in lg and "depth_pct" in lg for lg in legs)
    assert legs[-3]["depth_pct"] > legs[-2]["depth_pct"] > legs[-1]["depth_pct"]

    # RS New High Before Price must fire!
    rs_pts, rs_nh, rs_nh_before_px = compute_rs_line_series(df, bench)
    assert len(rs_pts) == n
    assert rs_nh is True
    assert rs_nh_before_px is True
    assert sepa["trend_template"]["relative_strength"]["rs_new_high_before_price"] is True

    # Chart payload includes Daily + Weekly + RS line + VCP legs
    chart = build_chart_payload(df, bench, sepa)
    assert len(chart["candles"]) == n
    assert len(chart["rs_line"]) == n
    assert len(chart["weekly"]["candles"]) >= 50
    assert len(chart["weekly"]["rs_line"]) >= 50
    assert len(chart["vcp_legs"]) >= 3


def test_fx_conversion_and_auto_2r_breakeven_trailing_journal(tmp_path):
    # FX test: 100 EUR at EUR/USD = 1.10 buys $110 worth of a $55 USD stock -> 2.0 shares!
    calc = calculate_position(
        PositionCalcRequest(
            capital_eur=100.0,
            entry_price=55.0,
            asset_currency="USD",
            fx_rate_override=1.10,
            stop_loss_pct=6.0,
        )
    )
    assert calc["quantity"] == pytest.approx(2.0, abs=1e-4)
    assert calc["position_value_eur"] == pytest.approx(100.0, abs=0.05)
    assert calc["max_loss_eur"] == pytest.approx(6.0, abs=0.05)
    assert calc["target_2r_profit_eur"] == pytest.approx(12.0, abs=0.05)

    # Paper Trading Auto 2R Partial + Breakeven + SMA Trailing + Journal Analytics
    temp_db = Database(db_path=tmp_path / "test_upgrades.db")
    svc = PaperTradingService(database=temp_db)

    pos = svc.open_position(
        PaperPositionCreate(
            ticker="NVDA",
            asset_type="stock",
            asset_currency="USD",
            fx_rate_override=1.0,
            entry_price=100.0,
            capital_eur=100.0,
            stop_loss_pct=6.0,
            auto_manage_2r=True,
            trailing_stop_mode="SMA10",
            setup_tag="VCP",
            journal_emotion="DISCIPLINADO",
        )
    )
    assert pos["target_2r"] == pytest.approx(112.0, abs=0.01)

    # Price rallies to 112.0 (2R) -> sells 50% (0.5 share, +6.0 EUR banked) & moves stop to Breakeven (100.0)!
    upd_2r = svc.update_open_positions_with_prices(
        price_overrides={"NVDA": 112.0},
        sma_overrides={"NVDA": 106.0},
    )
    assert len(upd_2r["triggered_partials"]) == 1
    assert upd_2r["triggered_partials"][0]["booked_eur"] == pytest.approx(6.0, abs=0.05)

    # Because trailing_stop_mode=SMA10 and SMA10=106 > breakeven 100 and < live 112, stop ratchets up to 106!
    pos_after = svc.list_positions()[0]
    assert pos_after["partial_2r_taken"] == 1
    assert pos_after["breakeven_moved"] == 1
    assert pos_after["quantity"] == pytest.approx(0.5, abs=1e-4)
    assert pos_after["stop_loss_price"] == pytest.approx(106.0, abs=0.01)

    # Price pulls back to 105.5 <= trailing stop 106 -> closes remaining 0.5 share as CLOSED_BE with +6.0 + 2.75 = +8.75 EUR profit!
    upd_close = svc.update_open_positions_with_prices(price_overrides={"NVDA": 105.5}, sma_overrides={"NVDA": 106.0})
    assert len(upd_close["triggered_stops"]) == 1
    assert upd_close["triggered_stops"][0]["status"] == "CLOSED_BE"

    # Update journal lesson
    updated_j = svc.update_journal(
        pos["id"],
        PaperPositionJournalUpdate(journal_lesson="Parcial em 2R + trailing SMA10 protegeu o lucro."),
    )
    assert "SMA10" in updated_j["journal_lesson"]

    summary = svc.get_portfolio_summary(refresh_prices=False)
    assert summary["metrics"]["total_pnl_eur"] > 8.0
    assert summary["metrics"]["partial_2r_count"] == 1
    assert len(summary["journal_stats"]["by_setup"]) == 1
    assert summary["journal_stats"]["by_setup"][0]["tag"] == "VCP"
    assert summary["journal_stats"]["by_setup"][0]["win_rate_pct"] == 100.0


def test_price_alerts_and_macro_regime_shift(tmp_path):
    temp_db = Database(db_path=tmp_path / "test_alerts.db")
    notif = NotificationService(database=temp_db)

    # First macro observation stores baseline (no shift alert)
    assert notif.check_macro_regime_shift("RISK_OFF", "Risk-Off", 22.0) is False
    # Regime shifts to RISK_ON -> fires alert!
    assert notif.check_macro_regime_shift("RISK_ON", "Risk-On", 75.0) is True
    assert any(a["category"] == "MACRO_SHIFT" for a in temp_db.list_alerts())

    # Custom Price Alert ABOVE 150
    pa = notif.create_price_alert("SPOT", "ABOVE", 150.0, notes="Pivô VCP")
    res_no = notif.check_price_alerts(price_overrides={"SPOT": 148.0})
    assert len(res_no["triggered"]) == 0

    res_hit = notif.check_price_alerts(price_overrides={"SPOT": 151.5})
    assert len(res_hit["triggered"]) == 1
    assert res_hit["triggered"][0]["id"] == pa["id"]
    assert res_hit["triggered"][0]["triggered"] == 1
    assert any(a["category"] == "PRICE_ALERT" for a in temp_db.list_alerts())
