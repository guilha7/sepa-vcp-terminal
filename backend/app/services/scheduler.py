import logging
import os
import sys
import threading
from apscheduler.schedulers.background import BackgroundScheduler

from app.config import settings
from app.database import db
from app.services.macro_rotation import compute_macro_and_rotation
from app.services.notifications import notification_service
from app.services.paper_trading import paper_trading_service
from app.services.scanner_service import run_sepa_vcp_scan

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_warmup_started = False


def _run_startup_warmup() -> None:
    """Silently pre-warms Macro & Scanner SQLite cache right after server boot (especially helpful on Render Free Tier)."""
    try:
        logger.info("[Warmup] A pré-carregar Macro & Scanner em background após arranque...")
        compute_macro_and_rotation(force_refresh=False)
        run_sepa_vcp_scan(asset_type=None, force_refresh=False)
        logger.info("[Warmup] Cache inicial Macro + Scanner pronta!")
    except Exception as exc:
        logger.warning("[Warmup] Pré-aquecimento inicial incompleto: %s", exc)


def _job_refresh_macro() -> None:
    try:
        logger.info("[Scheduler] A atualizar ambiente macro e rotação setorial...")
        compute_macro_and_rotation(force_refresh=True)
    except Exception as exc:
        logger.warning("[Scheduler] Falha na atualização macro: %s", exc)


def _job_refresh_paper_trading() -> None:
    try:
        logger.info("[Scheduler] A verificar P&L, Alvo 2R/Breakeven, Stop-Loss e Alertas de Preço...")
        paper_trading_service.update_open_positions_with_prices(force_refresh=True)
        notification_service.check_price_alerts(force_refresh=True)
    except Exception as exc:
        logger.warning("[Scheduler] Falha na atualização de Paper Trading/Alertas: %s", exc)


def _job_refresh_scanner() -> None:
    try:
        logger.info("[Scheduler] A executar scan automático SEPA/VCP...")
        run_sepa_vcp_scan(asset_type=None, force_refresh=True)
        db.cache_purge_expired()
    except Exception as exc:
        logger.warning("[Scheduler] Falha no scan automático SEPA/VCP: %s", exc)


def start_scheduler() -> None:
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("[Scheduler] Desativado via .env (SCHEDULER_ENABLED=false).")
        return
    if _scheduler is not None and _scheduler.running:
        return

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _job_refresh_macro,
        "interval",
        minutes=max(settings.scheduler_macro_minutes, 5),
        id="macro_refresh",
        replace_existing=True,
    )
    _scheduler.add_job(
        _job_refresh_paper_trading,
        "interval",
        minutes=max(settings.scheduler_paper_minutes, 2),
        id="paper_trading_monitor",
        replace_existing=True,
    )
    _scheduler.add_job(
        _job_refresh_scanner,
        "interval",
        hours=max(settings.scheduler_scan_hours, 1),
        id="sepa_vcp_scanner",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "[Scheduler] APScheduler iniciado (Macro: %sm | Paper Stop: %sm | Scanner: %sh).",
        settings.scheduler_macro_minutes,
        settings.scheduler_paper_minutes,
        settings.scheduler_scan_hours,
    )

    global _warmup_started
    is_test_env = bool(os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules)
    if not _warmup_started and not is_test_env:
        _warmup_started = True
        timer = threading.Timer(3.0, _run_startup_warmup)
        timer.daemon = True
        timer.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] APScheduler parado.")
    _scheduler = None


def restart_scheduler() -> None:
    stop_scheduler()
    start_scheduler()
