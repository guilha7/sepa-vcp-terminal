from fastapi import APIRouter, HTTPException, Query

from app.services.news_sentiment import get_asset_news
from app.services.xray_service import get_asset_xray

router = APIRouter(prefix="/api/xray", tags=["Raio-X de Ativo"])


@router.get("/{ticker}")
def get_xray(ticker: str, force_refresh: bool = Query(default=False)):
    try:
        return get_asset_xray(ticker=ticker, force_refresh=force_refresh)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar Raio-X para {ticker}: {exc}")


@router.get("/{ticker}/news")
def get_xray_news(ticker: str, force_refresh: bool = Query(default=False)):
    return get_asset_news(ticker=ticker, force_refresh=force_refresh)
