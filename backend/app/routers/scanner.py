import json
import queue
import threading
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.database import db
from app.models import WatchlistItemCreate
from app.services.market_data import is_crypto_ticker, normalize_ticker
from app.services.scanner_service import is_scan_running, run_sepa_vcp_scan, run_us_discovery_scan
from app.services.us_discovery import list_us_discovery_presets
from app.services.xray_service import get_fast_chart_preview

router = APIRouter(prefix="/api/scanner", tags=["Scanner SEPA & VCP"])


@router.get("/results")
def get_scanner_results(
    asset_type: Optional[str] = Query(default=None, pattern="^(stock|crypto)$"),
    force_refresh: bool = Query(default=False),
):
    return run_sepa_vcp_scan(asset_type=asset_type, force_refresh=force_refresh)


@router.post("/run")
def trigger_scanner_run(
    asset_type: Optional[str] = Query(default=None, pattern="^(stock|crypto)$"),
):
    return run_sepa_vcp_scan(asset_type=asset_type, force_refresh=True)


@router.get("/stream")
def stream_scanner_run(
    asset_type: Optional[str] = Query(default=None, pattern="^(stock|crypto)$"),
    force_refresh: bool = Query(default=True),
):
    """Server-Sent Events (SSE) live progress stream while running full SEPA/VCP scan."""
    q: queue.Queue = queue.Queue()

    def on_progress(current: int, total: int, ticker: str, stage: str):
        pct = int(round((current / max(total, 1)) * 100))
        q.put(
            {
                "type": "progress",
                "current": current,
                "total": total,
                "ticker": ticker,
                "stage": stage,
                "pct": min(max(pct, 0), 100),
            }
        )

    def worker():
        try:
            result = run_sepa_vcp_scan(
                asset_type=asset_type,
                force_refresh=force_refresh,
                progress_callback=on_progress,
            )
            q.put({"type": "complete", "result": result})
        except Exception as exc:
            q.put({"type": "error", "message": str(exc)})

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    def event_gen():
        while True:
            try:
                evt = q.get(timeout=25.0)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(evt, default=str)}\n\n"
            if evt.get("type") in ("complete", "error"):
                break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/us-discovery/presets")
def get_us_discovery_presets():
    return {"presets": list_us_discovery_presets()}


@router.get("/us-discovery")
def get_us_discovery_results(
    preset: str = Query(default="sepa_leaders"),
    limit: int = Query(default=70, ge=20, le=100),
    force_refresh: bool = Query(default=False),
):
    return run_us_discovery_scan(preset=preset, limit=limit, force_refresh=force_refresh)


@router.get("/us-discovery/stream")
def stream_us_discovery_scan(
    preset: str = Query(default="sepa_leaders"),
    limit: int = Query(default=70, ge=20, le=100),
    force_refresh: bool = Query(default=False),
):
    """SSE live progress stream for 2-Stage All-US (~7,000 stocks) Discovery Scanner."""
    q: queue.Queue = queue.Queue()

    def on_progress(current: int, total: int, ticker: str, stage: str):
        pct = int(round((current / max(total, 1)) * 100))
        q.put(
            {
                "type": "progress",
                "current": current,
                "total": total,
                "ticker": ticker,
                "stage": stage,
                "pct": min(max(pct, 0), 100),
            }
        )

    def worker():
        try:
            result = run_us_discovery_scan(
                preset=preset,
                limit=limit,
                force_refresh=force_refresh,
                progress_callback=on_progress,
            )
            q.put({"type": "complete", "result": result})
        except Exception as exc:
            q.put({"type": "error", "message": str(exc)})

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    def event_gen():
        while True:
            try:
                evt = q.get(timeout=25.0)
            except queue.Empty:
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(evt, default=str)}\n\n"
            if evt.get("type") in ("complete", "error"):
                break

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chart/{ticker}")
def get_scanner_quick_chart(ticker: str):
    """Fast cached candlestick + SMA + RS line + VCP swings for Scanner split-screen preview."""
    try:
        return get_fast_chart_preview(ticker)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar gráfico rápido de {ticker}: {exc}")


@router.get("/status")
def get_scanner_status():
    items, latest = db.load_scan_results()
    return {
        "scan_in_progress": is_scan_running(),
        "cached_items": len(items),
        "last_scanned_at": latest,
    }


@router.get("/watchlist")
def get_watchlist(asset_type: Optional[str] = Query(default=None, pattern="^(stock|crypto)$")):
    return {"items": db.get_watchlist(asset_type=asset_type, only_enabled=False)}


@router.post("/watchlist")
def add_watchlist_item(payload: WatchlistItemCreate):
    norm = normalize_ticker(payload.ticker)
    atype = "crypto" if (payload.asset_type == "crypto" or is_crypto_ticker(norm)) else "stock"
    db.upsert_watchlist_ticker(norm, atype, enabled=True)
    return {"status": "ok", "ticker": norm, "asset_type": atype}


@router.delete("/watchlist/{ticker}")
def remove_watchlist_item(ticker: str):
    norm = normalize_ticker(ticker)
    deleted = db.delete_watchlist_ticker(norm)
    if not deleted:
        deleted = db.delete_watchlist_ticker(ticker.strip().upper())
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} não encontrado na watchlist.")
    return {"status": "deleted", "ticker": norm}
