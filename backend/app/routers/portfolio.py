from typing import Optional
from fastapi import APIRouter, Header, HTTPException, Query

from app.models import (
    PaperPositionClose,
    PaperPositionCreate,
    PaperPositionJournalUpdate,
    PositionCalcRequest,
)
from app.services.market_data import get_eurusd_rate
from app.services.paper_trading import calculate_position, paper_trading_service

router = APIRouter(prefix="/api", tags=["Gestão de Risco & Paper Trading"])


def _resolve_owner(x_user_name: Optional[str]) -> str:
    return (x_user_name or "").strip() or "default"


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
def get_paper_portfolio(
    refresh: bool = Query(default=False),
    base_capital: Optional[float] = Query(default=None, gt=0),
    x_user_name: Optional[str] = Header(default=None),
):
    owner = _resolve_owner(x_user_name)
    res = paper_trading_service.get_portfolio_summary(
        refresh_prices=refresh,
        owner_name=owner,
        base_capital_eur=base_capital,
    )
    res["owner_name"] = owner
    return res


@router.post("/paper/positions")
def create_paper_position(
    payload: PaperPositionCreate,
    x_user_name: Optional[str] = Header(default=None),
):
    try:
        pos = paper_trading_service.open_position(payload, owner_name=_resolve_owner(x_user_name))
        return {"status": "opened", "position": pos}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/paper/positions/{position_id}/breakeven")
def move_paper_position_breakeven(
    position_id: int,
    x_user_name: Optional[str] = Header(default=None),
):
    try:
        pos = paper_trading_service.move_stop_to_breakeven(position_id, owner_name=_resolve_owner(x_user_name))
        return {"status": "breakeven", "position": pos}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/paper/positions/{position_id}/journal")
def update_paper_position_journal(
    position_id: int,
    payload: PaperPositionJournalUpdate,
    x_user_name: Optional[str] = Header(default=None),
):
    try:
        pos = paper_trading_service.update_journal(position_id, payload, owner_name=_resolve_owner(x_user_name))
        return {"status": "updated", "position": pos}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/paper/positions/{position_id}/close")
def close_paper_position(
    position_id: int,
    payload: PaperPositionClose,
    x_user_name: Optional[str] = Header(default=None),
):
    try:
        pos = paper_trading_service.close_position(
            position_id=position_id,
            exit_price=payload.exit_price,
            status=payload.reason or "CLOSED_MANUAL",
            journal_lesson=payload.journal_lesson,
            owner_name=_resolve_owner(x_user_name),
        )
        return {"status": "closed", "position": pos}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/paper/positions/{position_id}")
def delete_paper_position(
    position_id: int,
    x_user_name: Optional[str] = Header(default=None),
):
    ok = paper_trading_service.delete_position(position_id, owner_name=_resolve_owner(x_user_name))
    if not ok:
        raise HTTPException(status_code=404, detail=f"Posição #{position_id} não encontrada.")
    return {"status": "deleted", "id": position_id}


@router.post("/paper/refresh")
def refresh_paper_positions(
    base_capital: Optional[float] = Query(default=None, gt=0),
    x_user_name: Optional[str] = Header(default=None),
):
    owner = _resolve_owner(x_user_name)
    upd = paper_trading_service.update_open_positions_with_prices(force_refresh=True)
    summary = paper_trading_service.get_portfolio_summary(
        refresh_prices=False,
        owner_name=owner,
        base_capital_eur=base_capital,
    )
    summary["owner_name"] = owner
    summary["triggered_stops"] = upd["triggered_stops"]
    summary["triggered_partials"] = upd["triggered_partials"]
    summary["warnings"] = list(dict.fromkeys((summary.get("warnings") or []) + upd["warnings"]))
    return summary
