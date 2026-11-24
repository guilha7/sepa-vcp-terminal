from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def test_optional_password_gate_and_health_bypass():
    client = TestClient(app)
    orig = settings.app_access_password
    try:
        # 1. Default (empty password) -> unrestricted localhost access
        settings.app_access_password = ""
        st_open = client.get("/api/auth/status")
        assert st_open.status_code == 200
        assert st_open.json()["password_required"] is False
        assert st_open.json()["authenticated"] is True

        # 2. Password enabled -> /api/health remains open (for UptimeRobot), private endpoints require token
        settings.app_access_password = "MinhaPasswordSuperForte2026"
        assert client.get("/api/health").status_code == 200

        st_locked = client.get("/api/auth/status").json()
        assert st_locked["password_required"] is True
        assert st_locked["authenticated"] is False

        assert client.get("/api/settings").status_code == 401
        assert client.get("/api/paper/portfolio").status_code == 401

        # 3. Wrong password rejected
        bad_login = client.post("/api/auth/login", json={"password": "errada"})
        assert bad_login.status_code == 401

        # 4. Correct password issues session token unlocking protected endpoints
        ok_login = client.post("/api/auth/login", json={"password": "MinhaPasswordSuperForte2026"})
        assert ok_login.status_code == 200
        token = ok_login.json()["token"]
        assert len(token) >= 32

        assert client.get("/api/settings", headers={"X-Access-Token": token}).status_code == 200
        assert client.get(f"/api/paper/portfolio?access_token={token}").status_code == 200
    finally:
        settings.app_access_password = orig
