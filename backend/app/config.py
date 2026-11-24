from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    sqlite_db_path: str = "backend/data/trading_terminal.db"

    # AI configuration (zero-cost options: Gemini Free Tier / local Ollama / deterministic fallback)
    ai_provider: str = "auto"  # auto | gemini | ollama | none
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    # Ollama Local
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    ollama_vision_model: str = "qwen2.5-vl"

    # Free external notifications (Telegram Bot / Discord Webhook)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""

    # Cache TTLs (seconds)
    cache_ttl_prices: int = 600        # 10 min
    cache_ttl_news: int = 900          # 15 min
    cache_ttl_scan: int = 21600        # 6 hours
    cache_ttl_fundamentals: int = 86400  # 24 hours
    cache_ttl_ai: int = 21600          # 6 hours

    # Background scheduler
    scheduler_enabled: bool = True
    scheduler_macro_minutes: int = 15
    scheduler_paper_minutes: int = 10
    scheduler_scan_hours: int = 6

    # Risk limits
    default_capital_eur: float = 100.0
    default_stop_loss_pct: float = 6.0
    max_stop_loss_pct: float = 7.0

    @property
    def resolved_db_path(self) -> Path:
        p = Path(self.sqlite_db_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

# Curated liquid universe: Top S&P 500 / Nasdaq 100 growth & liquid leaders
DEFAULT_STOCK_UNIVERSE: list[str] = [
    "NVDA", "AAPL", "MSFT", "AMZN", "META", "GOOGL", "TSLA", "AVGO", "NFLX", "AMD",
    "PLTR", "CRWD", "PANW", "NOW", "ANET", "APP", "SPOT", "UBER", "SHOP", "MELI",
    "LLY", "ISRG", "VRT", "GE", "GEV", "ETN", "COST", "WMT", "JPM", "GS",
    "AXP", "V", "MA", "BKNG", "HWM", "AXON", "DECK", "CAVA", "CELH", "DUOL",
    "COIN", "HOOD", "MSTR", "ARM", "TSM", "ASML", "KLAC", "LRCX", "MRVL", "SMCI",
    "ORCL", "CRM", "ADBE", "INTU", "FTNT", "NET", "DDOG", "SNOW", "MDB", "TTD",
]

# Top 30 Liquid Cryptocurrencies (Yahoo Finance / Binance mapping supported)
DEFAULT_CRYPTO_UNIVERSE: list[str] = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD",
    "ADA-USD", "DOGE-USD", "TRX-USD", "AVAX-USD", "LINK-USD",
    "SUI-USD", "TON-USD", "SHIB-USD", "DOT-USD", "BCH-USD",
    "LTC-USD", "NEAR-USD", "UNI-USD", "APT-USD", "ICP-USD",
    "PEPE-USD", "RENDER-USD", "TAO-USD", "FET-USD", "AAVE-USD",
    "ARB-USD", "OP-USD", "INJ-USD", "ATOM-USD", "HBAR-USD",
]

US_SECTOR_ETFS: dict[str, str] = {
    "XLK": "Tecnologia",
    "XLF": "Financeiro",
    "XLV": "Saúde",
    "XLE": "Energia",
    "XLY": "Consumo Discricionário",
    "XLP": "Consumo Básico",
    "XLI": "Indústria",
    "XLB": "Materiais",
    "XLU": "Utilities",
    "XLRE": "Imobiliário",
    "XLC": "Comunicações",
}

CRYPTO_SECTORS: dict[str, dict] = {
    "LAYER1": {
        "name": "Layer 1 (Smart Contracts)",
        "tickers": ["BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "SUI-USD", "ADA-USD"],
    },
    "DEFI": {
        "name": "DeFi & Oracles",
        "tickers": ["LINK-USD", "UNI-USD", "AAVE-USD", "INJ-USD"],
    },
    "AI_COMPUTE": {
        "name": "IA & Compute",
        "tickers": ["TAO-USD", "RENDER-USD", "NEAR-USD", "FET-USD"],
    },
    "LAYER2_INFRA": {
        "name": "Layer 2 & Infra",
        "tickers": ["ARB-USD", "OP-USD", "DOT-USD", "ATOM-USD"],
    },
    "PAYMENTS": {
        "name": "Pagamentos & Exchange",
        "tickers": ["BNB-USD", "XRP-USD", "LTC-USD", "TRX-USD"],
    },
    "MEME_BETA": {
        "name": "Meme / High Beta",
        "tickers": ["DOGE-USD", "SHIB-USD", "PEPE-USD"],
    },
}
