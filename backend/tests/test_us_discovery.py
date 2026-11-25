from fastapi.testclient import TestClient

from app.main import app
from app.services.us_discovery import (
    _clean_yf_us_ticker,
    list_us_discovery_presets,
    screen_all_us_candidates,
)


def test_us_discovery_ticker_sanitization_and_presets():
    assert _clean_yf_us_ticker("nvda") == "NVDA"
    assert _clean_yf_us_ticker("BRK.B") == "BRK-B"
    assert _clean_yf_us_ticker("BF.B") == "BF-B"
    assert _clean_yf_us_ticker("BAD/TICKER") == ""
    assert _clean_yf_us_ticker("TOOLONGTICKER") == ""

    presets = list_us_discovery_presets()
    ids = {p["id"] for p in presets}
    assert {"sepa_leaders", "small_mid_growth", "volume_breakouts", "near_52w_high"} <= ids


def test_us_discovery_stage1_tradingview_parse_and_fallback(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "totalCount": 420,
                "data": [
                    {"d": ["PLTR", "Palantir Technologies", 75.2, 4.1, 50_000_000, 1.8, 35.0, 95.0, 210.0, 160_000_000_000, "Technology"]},
                    {"d": ["BRK.B", "Berkshire Hathaway", 460.0, 0.8, 3_000_000, 1.1, 10.0, 18.0, 28.0, 990_000_000_000, "Finance"]},
                    {"d": ["INVALID/1", "Junk", 10.0]},
                ],
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return FakeResp()

    monkeypatch.setattr("app.services.us_discovery.httpx.Client", FakeClient)
    res = screen_all_us_candidates(preset="sepa_leaders", limit=30)
    assert res["source"] == "tradingview_us_all"
    assert res["total_matched_stage1"] == 420
    assert res["tickers"] == ["PLTR", "BRK-B"]
    assert res["meta"]["PLTR"]["sector"] == "Technology"

    # Now verify clean fallback if TradingView raises an error
    class FailingClient(FakeClient):
        def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr("app.services.us_discovery.httpx.Client", FailingClient)
    fb = screen_all_us_candidates(preset="small_mid_growth", limit=25)
    assert fb["source"] == "yfinance_screener_fallback"
    assert len(fb["tickers"]) == 25
    assert len(fb["warnings"]) >= 1


def test_us_discovery_presets_endpoint():
    client = TestClient(app)
    r = client.get("/api/scanner/us-discovery/presets")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()["presets"]}
    assert {"sepa_leaders", "small_mid_growth", "volume_breakouts", "near_52w_high", "eu_leaders", "portugal_psi"} <= ids
