from fastapi import APIRouter, Query
from app.services.macro_rotation import compute_macro_and_rotation

router = APIRouter(prefix="/api/macro", tags=["Macro & Rotação"])


@router.get("/overview")
def get_macro_overview(force_refresh: bool = Query(default=False)):
    return compute_macro_and_rotation(force_refresh=force_refresh)
