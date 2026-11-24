from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class PositionCalcRequest(BaseModel):
    capital_eur: float = Field(default=100.0, gt=0, description="Capital em EUR")
    entry_price: float = Field(..., gt=0, description="Preço de entrada (na moeda do ativo)")
    asset_currency: Literal["USD", "EUR"] = Field(default="EUR", description="Moeda em que o ativo cota (USD converte via EURUSD=X)")
    fx_rate_override: Optional[float] = Field(default=None, gt=0, description="Opcional: taxa EUR/USD manual")
    stop_loss_pct: float = Field(default=6.0, gt=0.1, le=7.0, description="Stop-loss (%) - máx absoluto 7%")
    sizing_mode: Literal["capital_allocation", "account_risk"] = Field(
        default="capital_allocation",
        description="capital_allocation usa capital_eur diretamente na posição; account_risk limita risco total à percentagem risk_pct_of_account",
    )
    risk_pct_of_account: float = Field(default=2.0, gt=0.1, le=7.0)
    custom_target_price: Optional[float] = Field(default=None, gt=0)
    allow_fractional: bool = Field(default=True)

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_cap(cls, v: float) -> float:
        if v > 7.0:
            raise ValueError("O Stop-Loss máximo absoluto permitido é 7.0% (recomendado <= 6.0%).")
        return round(v, 2)


class PaperPositionCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=24)
    asset_type: Literal["stock", "crypto"] = "stock"
    asset_currency: Literal["USD", "EUR"] = "EUR"
    fx_rate_override: Optional[float] = Field(default=None, gt=0)
    entry_price: float = Field(..., gt=0)
    capital_eur: float = Field(default=100.0, gt=0)
    stop_loss_pct: float = Field(default=6.0, gt=0.1, le=7.0)
    quantity: Optional[float] = Field(default=None, gt=0)
    auto_manage_2r: bool = Field(default=True, description="Vender 50% em 2R e mover stop para Breakeven")
    trailing_stop_mode: Literal["NONE", "SMA10", "SMA21"] = Field(default="NONE")
    setup_tag: str = Field(default="VCP", max_length=32)
    journal_emotion: str = Field(default="DISCIPLINADO", max_length=32)
    journal_lesson: str = Field(default="", max_length=500)
    notes: str = ""

    @field_validator("stop_loss_pct")
    @classmethod
    def validate_stop_cap(cls, v: float) -> float:
        if v > 7.0:
            raise ValueError("Stop-Loss excede o teto máximo absoluto de 7.0%.")
        return round(v, 2)


class PaperPositionClose(BaseModel):
    exit_price: Optional[float] = Field(default=None, gt=0)
    reason: str = "CLOSED_MANUAL"
    journal_lesson: Optional[str] = None


class PaperPositionJournalUpdate(BaseModel):
    setup_tag: Optional[str] = Field(default=None, max_length=32)
    journal_emotion: Optional[str] = Field(default=None, max_length=32)
    journal_lesson: Optional[str] = Field(default=None, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=500)
    auto_manage_2r: Optional[bool] = None
    trailing_stop_mode: Optional[Literal["NONE", "SMA10", "SMA21"]] = None


class PriceAlertCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=24)
    condition: Literal["ABOVE", "BELOW"] = "ABOVE"
    target_price: float = Field(..., gt=0)
    notes: str = ""


class AlertChannelsUpdate(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=24)
    asset_type: Literal["stock", "crypto"] = "stock"


class VisionAnalyzeRequest(BaseModel):
    image_base64: str = Field(..., min_length=20)
    mime_type: str = Field(default="image/png")
    ticker: Optional[str] = None
    timeframe: Optional[str] = None
    notes: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    ai_provider_active: str
    gemini_configured: bool
    ollama_url: str
    scheduler_enabled: bool
    watchlist_counts: dict[str, int]
    timestamp: float
    extra: dict[str, Any] = {}
