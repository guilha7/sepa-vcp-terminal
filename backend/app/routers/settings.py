from typing import Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.database import db
from app.services.settings_service import (
    apply_universe_pack,
    get_settings_overview,
    test_ai_connection,
    update_user_settings,
)

router = APIRouter(prefix="/api/settings", tags=["Definições"])


class SettingsUpdateRequest(BaseModel):
    ai_provider: Optional[Literal["auto", "gemini", "ollama", "none"]] = None
    gemini_api_key: Optional[str] = None
    clear_gemini_key: bool = False
    gemini_model: Optional[str] = None
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    ollama_vision_model: Optional[str] = None
    default_capital_eur: Optional[float] = Field(default=None, gt=0)
    default_stop_loss_pct: Optional[float] = Field(default=None, ge=0.5, le=7.0)
    cache_ttl_prices: Optional[int] = Field(default=None, ge=60)
    cache_ttl_news: Optional[int] = Field(default=None, ge=60)
    cache_ttl_scan: Optional[int] = Field(default=None, ge=300)
    cache_ttl_fundamentals: Optional[int] = Field(default=None, ge=300)
    scheduler_enabled: Optional[bool] = None
    scheduler_macro_minutes: Optional[int] = Field(default=None, ge=5)
    scheduler_paper_minutes: Optional[int] = Field(default=None, ge=2)
    scheduler_scan_hours: Optional[int] = Field(default=None, ge=1)


class UniversePackRequest(BaseModel):
    pack_id: str
    mode: Literal["add", "replace_class"] = "add"


class CacheClearRequest(BaseModel):
    category: Literal["all", "prices", "news", "fundamentals", "macro", "ai", "scan"] = "all"


@router.get("")
def get_settings():
    return get_settings_overview()


@router.put("")
def save_settings(payload: SettingsUpdateRequest):
    try:
        return update_user_settings(payload.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/test-ai")
def test_ai():
    return test_ai_connection()


@router.post("/universe-pack")
def apply_pack(payload: UniversePackRequest):
    try:
        return apply_universe_pack(pack_id=payload.pack_id, mode=payload.mode)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/cache/clear")
def clear_cache(payload: CacheClearRequest):
    removed = db.cache_clear(category=payload.category)
    return {
        "status": "cleared",
        "category": payload.category,
        "removed_entries": removed,
        "storage": db.get_storage_stats(),
    }
