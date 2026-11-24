import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.database import Database
from app.models import PaperPositionCreate
from app.services.paper_trading import PaperTradingService
from cloud_monitor import build_morning_briefing_message, build_weekly_summary_message


def test_van_tharp_expectancy_and_sqn_metrics(tmp_path):
    temp_db = Database(db_path=tmp_path / "test_sqn.db")
    svc = PaperTradingService(database=temp_db)

    # Create 10 closed trades with strong asymmetric R-multiples -> SQN >= 2.0
    outcomes = [112.0, 118.0, 94.0, 115.0, 95.2, 112.0, 114.0, 116.0, 94.5, 113.0]
    for idx, exit_px in enumerate(outcomes):
        p = svc.open_position(
            PaperPositionCreate(
                ticker=f"TST{idx}",
                asset_type="stock",
                asset_currency="EUR",
                entry_price=100.0,
                capital_eur=100.0,
                stop_loss_pct=6.0,
                setup_tag="VCP",
            )
        )
        svc.close_position(p["id"], exit_price=exit_px)

    summary = svc.get_portfolio_summary(refresh_prices=False)
    m = summary["metrics"]
    assert m["closed_trades"] == 10
    assert m["expectancy_r"] > 0.8
    assert m["sqn"] is not None and m["sqn"] >= 2.0
    assert m["avg_win_r"] >= 2.0
    assert m["avg_loss_r"] <= 1.1
    assert "Bom" in m["sqn_grade"] or "Excelente" in m["sqn_grade"]


def test_morning_and_weekly_briefing_formatters():
    mock_macro = {
        "macro_traffic_light": {"regime": "RISK_ON", "label": "Risk-On", "score": 82.0},
        "ibd_timing": {
            "spy": {"distribution_days": 2},
            "qqq": {"distribution_days": 1},
            "any_ftd": True,
        },
        "market_breadth": {"pct_above_sma50": 68.5, "up_4pct_5d": 24, "down_4pct_5d": 7},
        "us_rotation": {
            "leaders": [{"ticker": "XLK", "rs_1m": 4.2}, {"ticker": "XLI", "rs_1m": 2.5}],
            "laggards": [{"ticker": "XLU", "rs_1m": -3.1}],
        },
        "crypto_derivatives": {
            "altseason": {"regime": "ALTSEASON", "altseason_index": 72.0},
            "assets": [{"ticker": "BTC-USD", "funding_rate_pct": 0.012}],
        },
    }
    mock_scan = {
        "opportunities": [
            {
                "ticker": "NVDA",
                "score": 88.5,
                "liquidity": {"passed": True},
                "earnings_within_14d": False,
                "trend_template": {"passed": True},
                "trade_plan": {"entry_pivot": 145.0, "stop_loss_pct": 5.5},
                "quant": {
                    "adr_pct_20d": 4.4,
                    "active_tags": ["POCKET_PIVOT", "TTM_SQUEEZE"],
                    "three_weeks_tight": {"detected": True},
                },
            }
        ]
    }

    title_m, body_m, lvl_m = build_morning_briefing_message(mock_macro, mock_scan)
    assert "Briefing Matinal" in title_m
    assert "NVDA" in body_m and "FOLLOW-THROUGH DAY" in body_m
    assert lvl_m == "success"

    title_w, body_w, _ = build_weekly_summary_message(mock_macro, mock_scan)
    assert "Resumo Semanal" in title_w
    assert "NVDA" in body_w and "3 Weeks Tight" in body_w
