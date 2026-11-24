import base64
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.database import db
from app.models import VisionAnalyzeRequest
from app.services.ai_service import analyze_chart_screenshot
from app.services.market_data import normalize_ticker
from app.services.xray_service import get_asset_xray

router = APIRouter(prefix="/api/vision", tags=["Visão IA de Gráficos"])


def _fetch_optional_ticker_context(ticker: Optional[str]) -> tuple[Optional[str], Optional[dict]]:
    if not ticker or not ticker.strip():
        return None, None
    norm = normalize_ticker(ticker)
    try:
        xray = get_asset_xray(norm, force_refresh=False)
        return norm, {
            "sepa": xray["sepa"],
            "fundamentals": xray["fundamentals"],
            "news": xray["news"],
            "warnings": xray.get("warnings", []),
        }
    except Exception:
        return norm, None


@router.post("/analyze")
def analyze_chart_json(payload: VisionAnalyzeRequest):
    norm_ticker, context = _fetch_optional_ticker_context(payload.ticker)
    try:
        return analyze_chart_screenshot(
            image_b64=payload.image_base64,
            mime_type=payload.mime_type,
            ticker=norm_ticker,
            timeframe=payload.timeframe,
            user_notes=payload.notes,
            ticker_context=context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha na análise do gráfico: {exc}")


@router.post("/analyze-file")
async def analyze_chart_file(
    file: UploadFile = File(...),
    ticker: Optional[str] = Form(default=None),
    timeframe: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Ficheiro de imagem vazio.")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imagem excede o limite de 10MB.")

    b64 = base64.b64encode(content).decode("ascii")
    mime = file.content_type or "image/png"
    norm_ticker, context = _fetch_optional_ticker_context(ticker)
    try:
        return analyze_chart_screenshot(
            image_b64=b64,
            mime_type=mime,
            ticker=norm_ticker,
            timeframe=timeframe,
            user_notes=notes,
            ticker_context=context,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/history")
def get_vision_history(limit: int = 10):
    return {"items": db.list_vision_history(limit=min(max(limit, 1), 30))}
