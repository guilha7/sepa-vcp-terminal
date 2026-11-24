import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app
from cloud_monitor import run_cloud_monitor


def test_cloud_monitor_price_alert_deduplication_and_macro_shift(tmp_path, monkeypatch):
    cfg_path = tmp_path / "alertas_cloud.json"
    state_path = tmp_path / "cloud_state.json"

    cfg_path.write_text(
        json.dumps(
            {
                "check_macro_shift": True,
                "check_vcp_breakouts": False,
                "price_alerts": [
                    {
                        "id": "spot-1",
                        "ticker": "SPOT",
                        "condition": "ABOVE",
                        "target_price": 500.0,
                        "notes": "Pivô VCP",
                        "enabled": True,
                    },
                    {
                        "id": "disabled-1",
                        "ticker": "AAPL",
                        "condition": "ABOVE",
                        "target_price": 1.0,
                        "enabled": False,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    # First run: macro baseline is RISK_OFF, SPOT hits 505 -> 1 alert dispatched
    monkeypatch.setattr(
        "cloud_monitor.compute_macro_and_rotation",
        lambda force_refresh=True: {
            "macro_traffic_light": {
                "regime": "RISK_OFF",
                "label": "Risk-Off",
                "score": 25.0,
                "guidance": "Defensivo",
            }
        },
    )
    sent_calls = []
    monkeypatch.setattr(
        "cloud_monitor.notification_service.dispatch",
        lambda **kw: sent_calls.append(kw) or {"telegram": True, "discord": False, "errors": []},
    )

    res1 = run_cloud_monitor(
        mode="alerts",
        config_path=cfg_path,
        state_path=state_path,
        price_overrides={"SPOT": 505.0},
        dry_run=False,
    )
    assert res1["dispatched_count"] == 1
    assert sent_calls[0]["category"] == "PRICE_ALERT"
    assert sent_calls[0]["ticker"] == "SPOT"

    # Second run with same price & macro -> MUST NOT spam duplicate price alert!
    res2 = run_cloud_monitor(
        mode="alerts",
        config_path=cfg_path,
        state_path=state_path,
        price_overrides={"SPOT": 510.0},
        dry_run=False,
    )
    assert res2["dispatched_count"] == 0

    # Third run: macro shifts from RISK_OFF -> RISK_ON -> MUST alert macro shift!
    monkeypatch.setattr(
        "cloud_monitor.compute_macro_and_rotation",
        lambda force_refresh=True: {
            "macro_traffic_light": {
                "regime": "RISK_ON",
                "label": "Risk-On",
                "score": 78.0,
                "guidance": "Favorável",
            }
        },
    )
    res3 = run_cloud_monitor(
        mode="alerts",
        config_path=cfg_path,
        state_path=state_path,
        price_overrides={"SPOT": 510.0},
        dry_run=False,
    )
    assert res3["dispatched_count"] == 1
    assert sent_calls[-1]["category"] == "MACRO_SHIFT"


def test_export_cloud_endpoint_roundtrip(tmp_path, monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr("app.routers.alerts.PROJECT_ROOT", tmp_path)

    cr = client.post(
        "/api/alerts/price",
        json={"ticker": "MSFT", "condition": "ABOVE", "target_price": 480.0, "notes": "Cloud sync test"},
    )
    assert cr.status_code == 200
    aid = cr.json()["alert"]["id"]
    try:
        exp = client.post("/api/alerts/export-cloud")
        assert exp.status_code == 200
        assert exp.json()["exported_count"] >= 1
        exported_file = tmp_path / "alertas_cloud.json"
        assert exported_file.exists()
        data = json.loads(exported_file.read_text(encoding="utf-8"))
        assert any(a["ticker"] == "MSFT" and a["target_price"] == 480.0 for a in data["price_alerts"])
    finally:
        client.delete(f"/api/alerts/price/{aid}")
