import base64
import io

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["watchlist_counts"]["stocks"] >= 30
    assert data["watchlist_counts"]["crypto"] >= 20


def test_risk_calculator_endpoint_and_stop_cap():
    ok = client.post(
        "/api/risk/calculate",
        json={"capital_eur": 100.0, "entry_price": 25.0, "stop_loss_pct": 6.0},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["quantity"] == 4.0
    assert body["max_loss_eur"] == 6.0

    # Above 7.0% MUST be rejected by Pydantic validation (422)
    bad = client.post(
        "/api/risk/calculate",
        json={"capital_eur": 100.0, "entry_price": 25.0, "stop_loss_pct": 8.0},
    )
    assert bad.status_code == 422


def test_paper_trading_api_crud():
    create = client.post(
        "/api/paper/positions",
        json={
            "ticker": "AAPL",
            "asset_type": "stock",
            "entry_price": 200.0,
            "capital_eur": 100.0,
            "stop_loss_pct": 5.5,
            "notes": "API smoke test",
        },
    )
    assert create.status_code == 200
    pos_id = create.json()["position"]["id"]

    port = client.get("/api/paper/portfolio")
    assert port.status_code == 200
    assert any(p["id"] == pos_id for p in port.json()["positions"])

    close = client.post(f"/api/paper/positions/{pos_id}/close", json={"exit_price": 212.0})
    assert close.status_code == 200
    assert close.json()["position"]["status"] == "CLOSED_MANUAL"

    delete = client.delete(f"/api/paper/positions/{pos_id}")
    assert delete.status_code == 200


def test_watchlist_crud_endpoints():
    add = client.post("/api/scanner/watchlist", json={"ticker": "RKLB", "asset_type": "stock"})
    assert add.status_code == 200
    assert add.json()["ticker"] == "RKLB"

    wl = client.get("/api/scanner/watchlist")
    assert wl.status_code == 200
    assert any(x["ticker"] == "RKLB" for x in wl.json()["items"])

    rm = client.delete("/api/scanner/watchlist/RKLB")
    assert rm.status_code == 200


def test_vision_analyze_endpoint(monkeypatch):
    monkeypatch.setattr("app.services.ai_service.detect_active_ai_provider", lambda: "fallback")
    img = Image.new("RGB", (200, 120), color=(15, 23, 42))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    resp = client.post(
        "/api/vision/analyze",
        json={"image_base64": b64, "mime_type": "image/png"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["report"]["trade_plan"]["max_stop_pct"] <= 6.0


def test_xray_endpoint_smoke(monkeypatch):
    import pandas as pd

    dates = pd.date_range("2025-01-01", periods=260, freq="B")
    prices = [100.0 + i * 0.25 for i in range(260)]
    mock_df = pd.DataFrame(
        {
            "date": [d.strftime("%Y-%m-%d") for d in dates],
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [3_000_000.0] * 260,
        }
    )
    monkeypatch.setattr("app.services.xray_service.get_ohlcv", lambda *a, **kw: (mock_df, "yfinance", []))
    monkeypatch.setattr(
        "app.services.xray_service.get_fundamentals_and_earnings",
        lambda *a, **kw: ({"ticker": "XLP", "name": "Consumer Staples ETF", "available": True, "earnings_within_14d": False}, []),
    )
    monkeypatch.setattr(
        "app.services.xray_service.get_asset_news",
        lambda *a, **kw: (
            {
                "ticker": "XLP",
                "items": [],
                "sentiment_summary": {"overall": "Neutro", "average_score": 0.0, "positive": 0, "neutral": 0, "negative": 0, "total": 0},
                "warnings": [],
            }
        ),
    )
    monkeypatch.setattr("app.services.ai_service.detect_active_ai_provider", lambda: "fallback")

    resp = client.get("/api/xray/XLP")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticker"] == "XLP"
    assert len(body["chart"]["candles"]) == 260
    assert len(body["chart"]["weekly"]["candles"]) >= 50
    assert len(body["sepa"]["trend_template"]["rules"]) == 8
