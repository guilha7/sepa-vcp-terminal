from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_optional_password_gate_and_health_bypass():
    client = TestClient(app)
    orig = settings.app_access_password
    orig_admin = settings.admin_password
    try:
        settings.app_access_password = ""
        settings.admin_password = ""
        st_open = client.get("/api/auth/status")
        assert st_open.status_code == 200
        assert st_open.json()["password_required"] is False
        assert st_open.json()["authenticated"] is True
        assert st_open.json()["admin_password_required"] is False
        assert st_open.json()["is_admin"] is True

        # Optional global password gate
        settings.app_access_password = "MinhaPasswordSuperForte2026"
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/paper/portfolio").status_code == 401
        assert client.post("/api/auth/login", json={"password": "errada"}).status_code == 401
        token = client.post("/api/auth/login", json={"password": "MinhaPasswordSuperForte2026"}).json()["token"]
        assert client.get("/api/paper/portfolio", headers={"X-Access-Token": token}).status_code == 200
    finally:
        settings.app_access_password = orig
        settings.admin_password = orig_admin


def test_friends_mode_admin_lock_and_isolated_paper_trading():
    client = TestClient(app)
    orig_access = settings.app_access_password
    orig_admin = settings.admin_password
    p_joao = None
    p_diogo = None
    try:
        # Open for friends (no APP_ACCESS_PASSWORD), protected for Admin (ADMIN_PASSWORD set)
        settings.app_access_password = ""
        settings.admin_password = "SoParaOMeuAdmin99"

        # 1. Friends CANNOT read/edit Settings, touch Telegram channels, or create/delete Price Alerts (403 Forbidden)
        assert client.get("/api/settings").status_code == 403
        assert client.put("/api/settings", json={"default_capital_eur": 9999}).status_code == 403
        assert client.post("/api/alerts/channels", json={"telegram_chat_id": "123"}).status_code == 403
        assert client.post(
            "/api/alerts/price",
            json={"ticker": "NVDA", "condition": "ABOVE", "target_price": 150.0, "notes": "Amigo"},
        ).status_code == 403
        assert client.post("/api/alerts/price/check").status_code == 403
        assert client.delete("/api/alerts/price/99999").status_code == 403

        # 2. Admin login unlocks Settings and Price Alerts
        assert client.post("/api/auth/admin-login", json={"password": "errada"}).status_code == 403
        adm = client.post("/api/auth/admin-login", json={"password": "SoParaOMeuAdmin99"})
        assert adm.status_code == 200
        adm_token = adm.json()["admin_token"]
        assert client.get("/api/settings", headers={"X-Admin-Token": adm_token}).status_code == 200

        pa = client.post(
            "/api/alerts/price",
            headers={"X-Admin-Token": adm_token},
            json={"ticker": "NVDA", "condition": "ABOVE", "target_price": 9999.0, "notes": "Admin test"},
        )
        assert pa.status_code == 200
        pa_id = pa.json()["alert"]["id"]
        assert client.delete(f"/api/alerts/price/{pa_id}", headers={"X-Admin-Token": adm_token}).status_code == 200

        # 3. Friends freely use Paper Trading with completely isolated positions + personal base_capital per X-User-Name!
        r_j = client.post(
            "/api/paper/positions",
            headers={"X-User-Name": "Joao"},
            json={"ticker": "NVDA", "asset_type": "stock", "entry_price": 140.0, "capital_eur": 100.0, "stop_loss_pct": 6.0},
        )
        assert r_j.status_code == 200
        p_joao = r_j.json()["position"]["id"]

        r_d = client.post(
            "/api/paper/positions",
            headers={"X-User-Name": "Diogo"},
            json={"ticker": "AAPL", "asset_type": "stock", "entry_price": 220.0, "capital_eur": 100.0, "stop_loss_pct": 5.0},
        )
        assert r_d.status_code == 200
        p_diogo = r_d.json()["position"]["id"]

        port_j = client.get("/api/paper/portfolio?base_capital=500", headers={"X-User-Name": "Joao"}).json()
        port_d = client.get("/api/paper/portfolio?base_capital=250", headers={"X-User-Name": "Diogo"}).json()

        assert port_j["metrics"]["base_capital_eur"] == 500.0
        assert port_d["metrics"]["base_capital_eur"] == 250.0
        assert any(p["id"] == p_joao for p in port_j["positions"])
        assert not any(p["id"] == p_diogo for p in port_j["positions"])
        assert any(p["id"] == p_diogo for p in port_d["positions"])
        assert not any(p["id"] == p_joao for p in port_d["positions"])

        # Joao CANNOT delete Diogo's position!
        assert client.delete(f"/api/paper/positions/{p_diogo}", headers={"X-User-Name": "Joao"}).status_code == 404
    finally:
        if p_joao:
            client.delete(f"/api/paper/positions/{p_joao}", headers={"X-User-Name": "Joao"})
        if p_diogo:
            client.delete(f"/api/paper/positions/{p_diogo}", headers={"X-User-Name": "Diogo"})
        settings.app_access_password = orig_access
        settings.admin_password = orig_admin
