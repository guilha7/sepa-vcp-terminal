import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_schema()
    load_persisted_settings()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="SEPA/VCP Trading Terminal API",
    description="Terminal local 100% gratuito para análise Minervini SEPA/VCP, rotação de capital, notícias, visão IA e paper trading.",
    version="1.0.0",
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
        },
    )
