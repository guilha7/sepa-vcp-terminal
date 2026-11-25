import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import PROJECT_ROOT, settings
from app.database import db
from app.models import HealthResponse
from app.routers import alerts, macro, portfolio, scanner, settings as settings_router, vision, xray
from app.services.ai_service import detect_active_ai_provider
from app.services.notifications import notification_service
from app.services.scheduler import start_scheduler, stop_scheduler
from app.services.settings_service import load_persisted_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def _expected_access_token() -> str:
    pwd = (settings.app_access_password or "").strip()
    if not pwd:
        return ""
    return hmac.new(pwd.encode("utf-8"), b"sepa-vcp-terminal-session-v1", hashlib.sha256).hexdigest()


def _expected_admin_token() -> str:
    pwd = (settings.admin_password or "").strip()
    if not pwd:
        return ""
    return hmac.new(pwd.encode("utf-8"), b"sepa-vcp-terminal-admin-v1", hashlib.sha256).hexdigest()


def _is_request_authorized(request: Request) -> bool:
    expected = _expected_access_token()
    if not expected:
        return True
    token = (
        request.headers.get("x-access-token")
        or request.query_params.get("access_token")
        or ""
    ).strip()
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    return bool(token and hmac.compare_digest(token, expected))


def _is_admin_authorized(request: Request) -> bool:
    expected = _expected_admin_token()
    if not expected:
        return True
    token = (request.headers.get("x-admin-token") or "").strip()
    return bool(token and hmac.compare_digest(token, expected))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_schema()
    load_persisted_settings()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="SEPA/VCP Trading Terminal API",
    description="Terminal 100% gratuito para análise Minervini SEPA/VCP, multi-estratégia, rotação de capital, derivados cripto, visão IA e paper trading.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


ADMIN_PROTECTED_EXACT = {
    ("GET", "/api/settings"),
    ("PUT", "/api/settings"),
    ("POST", "/api/settings/test-ai"),
    ("POST", "/api/settings/universe-pack"),
    ("POST", "/api/settings/cache/clear"),
    ("POST", "/api/alerts/channels"),
    ("POST", "/api/alerts/test"),
    ("POST", "/api/alerts/send-morning-briefing"),
    ("POST", "/api/alerts/export-cloud"),
    ("POST", "/api/scanner/watchlist"),
}


@app.middleware("http")
async def optional_password_gate(request: Request, call_next):
    """Enforces optional APP_ACCESS_PASSWORD and ADMIN_PASSWORD (protecting Settings & Telegram channels from friends)."""
    path = request.url.path
    method = request.method.upper()

    if (
        path.startswith("/api/")
        and path not in ("/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/admin-login")
        and method != "OPTIONS"
    ):
        if not _is_request_authorized(request):
            return JSONResponse(
                status_code=401,
                content={"detail": "Acesso protegido por password. Faz login para continuar."},
            )

        is_admin_route = (method, path) in ADMIN_PROTECTED_EXACT or (
            method == "DELETE" and path.startswith("/api/scanner/watchlist/")
        )
        if is_admin_route and not _is_admin_authorized(request):
            return JSONResponse(
                status_code=403,
                content={"detail": "Área reservada ao Administrador. Insere a ADMIN_PASSWORD para alterar definições ou canais de alerta."},
            )

    return await call_next(request)


class LoginRequest(BaseModel):
    password: str


@app.get("/api/auth/status")
def auth_status(request: Request):
    required = bool((settings.app_access_password or "").strip())
    admin_required = bool((settings.admin_password or "").strip())
    return {
        "password_required": required,
        "authenticated": _is_request_authorized(request),
        "admin_password_required": admin_required,
        "is_admin": _is_admin_authorized(request),
    }


@app.post("/api/auth/login")
def auth_login(payload: LoginRequest):
    pwd = (settings.app_access_password or "").strip()
    if not pwd:
        return {"status": "ok", "token": ""}
    if not hmac.compare_digest(payload.password.strip(), pwd):
        raise HTTPException(status_code=401, detail="Password incorreta.")
    return {"status": "ok", "token": _expected_access_token()}


@app.post("/api/auth/admin-login")
def auth_admin_login(payload: LoginRequest):
    pwd = (settings.admin_password or "").strip()
    if not pwd:
        return {"status": "ok", "admin_token": ""}
    if not hmac.compare_digest(payload.password.strip(), pwd):
        raise HTTPException(status_code=403, detail="Password de Administrador incorreta.")
    return {"status": "ok", "admin_token": _expected_admin_token()}


app.include_router(macro.router)
app.include_router(scanner.router)
app.include_router(xray.router)
app.include_router(vision.router)
app.include_router(portfolio.router)
app.include_router(alerts.router)
app.include_router(settings_router.router)


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    stocks = db.get_watchlist(asset_type="stock", only_enabled=True)
    cryptos = db.get_watchlist(asset_type="crypto", only_enabled=True)
    ch = notification_service.get_channel_status()
    return HealthResponse(
        status="ok",
        ai_provider_active=detect_active_ai_provider(),
        gemini_configured=bool(settings.gemini_api_key.strip()),
        ollama_url=settings.ollama_base_url,
        scheduler_enabled=settings.scheduler_enabled,
        watchlist_counts={"stocks": len(stocks), "crypto": len(cryptos)},
        timestamp=time.time(),
        extra={
            "default_capital_eur": settings.default_capital_eur,
            "default_stop_loss_pct": settings.default_stop_loss_pct,
            "max_stop_loss_pct": settings.max_stop_loss_pct,
            "unread_alerts": db.count_unread_alerts(),
            "telegram_configured": ch["telegram_configured"],
            "discord_configured": ch["discord_configured"],
            "password_protected": bool((settings.app_access_password or "").strip()),
        },
    )


# --- Production SPA Static Serving (used on Render / Docker deploy) ---
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="frontend-assets")


@app.get("/favicon.svg", include_in_schema=False)
def serve_favicon_svg():
    fav = FRONTEND_DIST / "favicon.svg"
    if fav.is_file():
        return FileResponse(str(fav), media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend_spa(full_path: str):
    if full_path.startswith("api/") or full_path in ("docs", "redoc", "openapi.json"):
        raise HTTPException(status_code=404, detail="Not found")
    index_html = FRONTEND_DIST / "index.html"
    if index_html.is_file():
        return FileResponse(str(index_html), media_type="text/html")
    return JSONResponse(
        {
            "message": "SEPA/VCP API online. Corre 'npm run build' em /frontend para servir a interface neste endereço ou abre http://127.0.0.1:5173 em modo desenvolvimento."
        }
    )
