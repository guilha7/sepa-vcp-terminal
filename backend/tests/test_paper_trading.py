import pytest
from pydantic import ValidationError

from app.database import Database
from app.models import PaperPositionCreate, PositionCalcRequest
from app.services.paper_trading import PaperTradingService, calculate_position


def test_position_calculator_default_6pct_stop():
    req = PositionCalcRequest(capital_eur=100.0, entry_price=50.0, stop_loss_pct=6.0)
    res = calculate_position(req)

    assert res["quantity"] == 2.0
    assert res["stop_loss_price"] == 47.0
    assert res["max_loss_eur"] == 6.0
    assert res["target_2r_price"] == 56.0
    assert res["target_2r_profit_eur"] == 12.0
    assert res["target_3r_price"] == 59.0
    assert res["target_3r_profit_eur"] == 18.0
    assert res["risk_warning"] is None


def test_position_calculator_warns_above_6_and_blocks_above_7():
    req_warn = PositionCalcRequest(capital_eur=100.0, entry_price=100.0, stop_loss_pct=6.8)
    res_warn = calculate_position(req_warn)
    assert res_warn["risk_warning"] is not None
    assert res_warn["max_loss_eur"] == 6.8

    with pytest.raises(ValidationError):
        PositionCalcRequest(capital_eur=100.0, entry_price=100.0, stop_loss_pct=7.5)


def test_paper_trading_auto_stop_loss_and_metrics(tmp_path):
    temp_db = Database(db_path=tmp_path / "test_paper.db")
    svc = PaperTradingService(database=temp_db)

    # Trade 1: Opens NVDA at 100 with 100 EUR capital and 6% stop (stop_price = 94.0)
    pos1 = svc.open_position(
        PaperPositionCreate(
            ticker="NVDA",
            asset_type="stock",
            entry_price=100.0,
            capital_eur=100.0,
            stop_loss_pct=6.0,
            notes="VCP breakout test",
        )
    )
    assert pos1["status"] == "OPEN"
    assert pos1["stop_loss_price"] == pytest.approx(94.0, rel=1e-4)

    # Price rallies to 112 -> unrealized +12 EUR (+12%)
    upd_up = svc.update_open_positions_with_prices(price_overrides={"NVDA": 112.0})
    assert len(upd_up["triggered_stops"]) == 0
    summary_up = svc.get_portfolio_summary(refresh_prices=False)
    assert summary_up["metrics"]["unrealized_pnl_eur"] == pytest.approx(12.0, abs=0.01)

    # Close Trade 1 manually for +12 EUR profit
    closed1 = svc.close_position(pos1["id"], exit_price=112.0)
    assert closed1["status"] == "CLOSED_MANUAL"
    assert closed1["pnl_eur"] == pytest.approx(12.0, abs=0.01)

    # Trade 2: Opens SOL-USD at 200 with 100 EUR capital and 6% stop (stop_price = 188.0)
    pos2 = svc.open_position(
        PaperPositionCreate(
            ticker="SOL-USD",
            asset_type="crypto",
            entry_price=200.0,
            capital_eur=100.0,
            stop_loss_pct=6.0,
        )
    )
    assert pos2["stop_loss_price"] == pytest.approx(188.0, rel=1e-4)

    # Price drops to 186.0 (below -6% stop) -> MUST auto-close as CLOSED_STOP & emit alert!
    upd_stop = svc.update_open_positions_with_prices(price_overrides={"SOL-USD": 186.0})
    assert len(upd_stop["triggered_stops"]) == 1
    assert upd_stop["triggered_stops"][0]["ticker"] == "SOL-USD"

    summary = svc.get_portfolio_summary(refresh_prices=False)
    m = summary["metrics"]
    assert m["closed_trades"] == 2
    assert m["open_trades"] == 0
    assert m["wins"] == 1
    assert m["losses"] == 1
    assert m["win_rate_pct"] == 50.0
    assert m["auto_stops_count"] == 1
    assert m["total_pnl_eur"] == pytest.approx(5.0, abs=0.05)  # +12.0 - 7.0 (filled at 186)
    assert m["max_drawdown_pct"] > 0.0
    assert len(summary["equity_curve"]) == 3
    assert any(a["category"] == "STOP_LOSS" for a in summary["alerts"])
