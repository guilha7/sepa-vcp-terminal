from fastapi import APIRouter, HTTPException, Query

from app.models import (
    PaperPositionClose,
    PaperPositionCreate,
    PaperPositionJournalUpdate,
    PositionCalcRequest,
)
from app.services.market_data import get_eurusd_rate
from app.services.paper_trading import calculate_position, paper_trading_service

router = APIRouter(prefix="/api", tags=["Gestão de Risco & Paper Trading"])


@router.get("/risk/fx")
def get_fx_rate(force_refresh: bool = Query(default=False)):
    rate, warnings = get_eurusd_rate(force_refresh=force_refresh)
    return {"pair": "EUR/USD", "rate": rate, "warnings": warnings}


@router.post("/risk/calculate")
def calc_position_size(payload: PositionCalcRequest):
    try:
        return calculate_position(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/paper/portfolio")
def get_paper_portfolio(refresh: bool = Query(default=False)):
    return paper_trading_service.get_portfolio_summary(refresh_prices=refresh)


@router.post("/paper/positions")
def create_paper_position(payload: PaperPositionCreate):
    try:
        pos = paper_trading_service.open_position(payload)
        return {"status": "opened", "position": pos}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/paper/positions/{position_id}/breakeven")
def move_paper_position_breakeven(position_id: int):
    try:
        pos = paper_trading_service.move_stop_to_breakeven(position_id)
        return {"status": "breakeven", "position": pos}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/paper/positions/{position_id}/journal")
def update_paper_position_journal(position_id: int, payload: PaperPositionJournalUpdate):
    try:
        pos = paper_trading_service.update_journal(position_id, payload)
        return {"status": "updated", "position": pos}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/paper/positions/{position_id}/close")
def close_paper_position(position_id: int, payload: PaperPositionClose):
    try:
        pos = paper_trading_service.close_position(
            position_id=position_id,
            exit_price=payload.exit_price,
            status=payload.reason or "CLOSED_MANUAL",
            journal_lesson=payload.journal_lesson,
        )
        return {"status": "closed", "position": pos}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/paper/positions/{position_id}")
def delete_paper_position(position_id: int):
    ok = paper_trading_service.delete_position(position_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Posição #{position_id} não encontrada.")
    return {"status": "deleted", "id": position_id}


@router.post("/paper/refresh")
def refresh_paper_positions():
    upd = paper_trading_service.update_open_positions_with_prices(force_refresh=True)
    summary = paper_trading_service.get_portfolio_summary(refresh_prices=False)
    summary["triggered_stops"] = upd["triggered_stops"]
    summary["triggered_partials"] = upd["triggered_partials"]
    summary["warnings"] = list(dict.fromkeys((summary.get("warnings") or []) + upd["warnings"]))
    return summary
