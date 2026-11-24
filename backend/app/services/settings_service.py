import json
import logging
import time
from typing import Any, Optional

import httpx

from app.config import (
    DEFAULT_CRYPTO_UNIVERSE,
    DEFAULT_STOCK_UNIVERSE,
    US_SECTOR_ETFS,
    settings,
)
from app.database import Database, db as default_db
from app.services.ai_service import _call_gemini, _call_ollama, detect_active_ai_provider
from app.services.notifications import notification_service
from app.services.scheduler import restart_scheduler

logger = logging.getLogger(__name__)

# Curated 1-click Scanner Universe Packs (100% free via yfinance & ccxt)
UNIVERSE_PACKS: dict[str, dict[str, Any]] = {
    "core_leaders": {
        "id": "core_leaders",
        "name": "S&P 500 & Nasdaq 100 Líderes",
        "description": "60 ações norte-americanas de elevada liquidez institucional e crescimento.",
        "asset_type": "stock",
        "tickers": DEFAULT_STOCK_UNIVERSE,
    },
    "semis_ai": {
        "id": "semis_ai",
        "name": "Semicondutores & Infraestrutura IA",
        "description": "Líderes globais de chips, data centers, redes e software de IA.",
        "asset_type": "stock",
        "tickers": [
            "NVDA", "AVGO", "AMD", "TSM", "ASML", "ARM", "MRVL", "KLAC",
            "LRCX", "AMAT", "MU", "QCOM", "ANET", "VRT", "SMCI", "PLTR",
            "SNPS", "CDNS",
        ],
    },
    "high_growth_sepa": {
        "id": "high_growth_sepa",
        "name": "High-Growth SEPA (Mid & Large Cap)",
        "description": "Empresas de alto beta e forte aceleração de receitas (estilo Minervini).",
        "asset_type": "stock",
        "tickers": [
            "APP", "PLTR", "HOOD", "HIMS", "RKLB", "ASTS", "AXON", "DUOL",
            "CAVA", "CELH", "CRWD", "NET", "DDOG", "SNOW", "SHOP", "MELI",
            "UBER", "SPOT", "COIN", "MSTR",
        ],
    },
    "us_sector_etfs": {
        "id": "us_sector_etfs",
        "name": "11 ETFs Setoriais EUA",
        "description": "Monitoriza os 11 grandes setores SPDR diretamente no Scanner SEPA/VCP.",
        "asset_type": "stock",
        "tickers": list(US_SECTOR_ETFS.keys()),
    },
    "top_30_crypto": {
        "id": "top_30_crypto",
        "name": "Top 30 Criptomoedas Líquidas",
        "description": "Principais criptomoedas (Layer 1, DeFi, IA, Layer 2, Pagamentos e High Beta).",
        "asset_type": "crypto",
        "tickers": DEFAULT_CRYPTO_UNIVERSE,
    },
}

PERSISTED_KEYS = {
    "ai_provider": str,
    "gemini_api_key": str,
    "gemini_model": str,
    "ollama_base_url": str,
    "ollama_model": str,
    "ollama_vision_model": str,
    "default_capital_eur": float,
    "default_stop_loss_pct": float,
    "cache_ttl_prices": int,
    "cache_ttl_news": int,
    "cache_ttl_scan": int,
    "cache_ttl_fundamentals": int,
    "scheduler_enabled": bool,
    "scheduler_macro_minutes": int,
    "scheduler_paper_minutes": int,
    "scheduler_scan_hours": int,
}


def _mask_secret(secret: str) -> str:
    s = (secret or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "•" * len(s)
    return f"{s[:4]}••••{s[-4:]}"


def _list_ollama_models() -> tuple[bool, list[str]]:
    try:
        url = settings.ollama_base_url.rstrip("/") + "/api/tags"
        with httpx.Client(timeout=0.45) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return False, []
            data = resp.json()
            names = [m.get("name", "") for m in (data.get("models") or []) if m.get("name")]
            return True, names
    except Exception:
        return False, []


def load_persisted_settings(database: Database = default_db) -> None:
    """Loads persisted user overrides from SQLite app_state onto global settings at startup."""
    raw = database.get_state("user_settings_json")
    if not raw:
        return
    try:
        saved = json.loads(raw)
        if not isinstance(saved, dict):
            return
        for k, caster in PERSISTED_KEYS.items():
            if k in saved and saved[k] is not None:
                val = saved[k]
                if caster is bool:
                    val = bool(val)
                else:
                    val = caster(val)
                setattr(settings, k, val)
    except Exception as exc:
        logger.warning("Não foi possível carregar definições gravadas em SQLite: %s", exc)


def _persist_current_settings(database: Database = default_db) -> None:
    snapshot = {k: getattr(settings, k) for k in PERSISTED_KEYS}
    database.set_state("user_settings_json", json.dumps(snapshot))


def get_settings_overview(database: Database = default_db) -> dict[str, Any]:
    ollama_online, ollama_models = _list_ollama_models()
    wl = {w["ticker"] for w in database.get_watchlist(only_enabled=True)}

    packs = []
    for p in UNIVERSE_PACKS.values():
        present = sum(1 for tk in p["tickers"] if tk in wl)
        packs.append(
            {
                "id": p["id"],
                "name": p["name"],
                "description": p["description"],
                "asset_type": p["asset_type"],
                "total_tickers": len(p["tickers"]),
                "in_watchlist": present,
                "sample_tickers": p["tickers"][:8],
            }
        )

    return {
        "ai": {
            "ai_provider": settings.ai_provider,
            "ai_provider_active": detect_active_ai_provider(),
            "gemini_configured": bool(settings.gemini_api_key.strip()),
            "gemini_api_key_masked": _mask_secret(settings.gemini_api_key),
            "gemini_model": settings.gemini_model,
            "ollama_base_url": settings.ollama_base_url,
            "ollama_model": settings.ollama_model,
            "ollama_vision_model": settings.ollama_vision_model,
            "ollama_online": ollama_online,
            "ollama_installed_models": ollama_models,
        },
        "risk": {
            "default_capital_eur": settings.default_capital_eur,
            "default_stop_loss_pct": settings.default_stop_loss_pct,
            "max_stop_loss_pct": settings.max_stop_loss_pct,
        },
        "cache": {
            "cache_ttl_prices": settings.cache_ttl_prices,
            "cache_ttl_news": settings.cache_ttl_news,
            "cache_ttl_scan": settings.cache_ttl_scan,
            "cache_ttl_fundamentals": settings.cache_ttl_fundamentals,
            "storage": database.get_storage_stats(),
        },
        "scheduler": {
            "scheduler_enabled": settings.scheduler_enabled,
            "scheduler_macro_minutes": settings.scheduler_macro_minutes,
            "scheduler_paper_minutes": settings.scheduler_paper_minutes,
            "scheduler_scan_hours": settings.scheduler_scan_hours,
        },
        "notifications": notification_service.get_channel_status(),
        "universe_packs": packs,
    }


def update_user_settings(
    payload: dict[str, Any],
    database: Database = default_db,
    apply_scheduler: bool = True,
) -> dict[str, Any]:
    scheduler_changed = False

    if payload.get("clear_gemini_key"):
        settings.gemini_api_key = ""

    if "ai_provider" in payload and payload["ai_provider"] in ("auto", "gemini", "ollama", "none"):
        settings.ai_provider = payload["ai_provider"]

    if payload.get("gemini_api_key") is not None and str(payload["gemini_api_key"]).strip():
        settings.gemini_api_key = str(payload["gemini_api_key"]).strip()

    if payload.get("gemini_model"):
        settings.gemini_model = str(payload["gemini_model"]).strip()

    if payload.get("ollama_base_url"):
        settings.ollama_base_url = str(payload["ollama_base_url"]).strip().rstrip("/")

    if payload.get("ollama_model"):
        settings.ollama_model = str(payload["ollama_model"]).strip()

    if payload.get("ollama_vision_model"):
        settings.ollama_vision_model = str(payload["ollama_vision_model"]).strip()

    if payload.get("default_capital_eur") is not None:
        cap = float(payload["default_capital_eur"])
        if cap <= 0:
            raise ValueError("Capital padrão deve ser superior a 0€.")
        settings.default_capital_eur = round(cap, 2)

    if payload.get("default_stop_loss_pct") is not None:
        stp = float(payload["default_stop_loss_pct"])
        if not (0.5 <= stp <= 7.0):
            raise ValueError("Stop-Loss padrão deve estar entre 0.5% e 7.0% (recomendado <= 6.0%).")
        settings.default_stop_loss_pct = round(stp, 2)

    for ttl_key in ("cache_ttl_prices", "cache_ttl_news", "cache_ttl_scan", "cache_ttl_fundamentals"):
        if payload.get(ttl_key) is not None:
            v = int(payload[ttl_key])
            if v < 60:
                raise ValueError(f"{ttl_key} deve ser >= 60 segundos.")
            setattr(settings, ttl_key, v)

    if payload.get("scheduler_enabled") is not None:
        new_en = bool(payload["scheduler_enabled"])
        if new_en != settings.scheduler_enabled:
            settings.scheduler_enabled = new_en
            scheduler_changed = True

    for sch_key, min_val in (
        ("scheduler_macro_minutes", 5),
        ("scheduler_paper_minutes", 2),
        ("scheduler_scan_hours", 1),
    ):
        if payload.get(sch_key) is not None:
            v = max(int(payload[sch_key]), min_val)
            if v != getattr(settings, sch_key):
                setattr(settings, sch_key, v)
                scheduler_changed = True

    _persist_current_settings(database=database)

    if scheduler_changed and apply_scheduler:
        restart_scheduler()

    return get_settings_overview(database=database)


def test_ai_connection() -> dict[str, Any]:
    """Tests active AI provider (Gemini Free Tier or local Ollama) with a tiny JSON ping."""
    active = detect_active_ai_provider()
    t0 = time.monotonic()

    if active == "fallback":
        return {
            "ok": True,
            "provider": "fallback",
            "latency_ms": round((time.monotonic() - t0) * 1000, 1),
            "message": (
                "Modo Fallback Algorítmico Local ativo (sem chave Gemini nem Ollama local detetado). "
                "Tudo funciona a 0€; adiciona GEMINI_API_KEY ou corre o Ollama para briefings e visão por LLM."
            ),
        }

    ping_prompt = 'Responde APENAS com este JSON: {"status": "ok", "engine": "ready"}'
    raw = _call_gemini(ping_prompt) if active == "gemini" else _call_ollama(ping_prompt)
    elapsed_ms = round((time.monotonic() - t0) * 1000, 1)

    if raw:
        model_name = settings.gemini_model if active == "gemini" else settings.ollama_model
        return {
            "ok": True,
            "provider": active,
            "model": model_name,
            "latency_ms": elapsed_ms,
            "message": f"Ligação bem-sucedida a {active.upper()} ({model_name}) em {elapsed_ms:.0f} ms!",
        }

    return {
        "ok": False,
        "provider": active,
        "latency_ms": elapsed_ms,
        "message": (
            f"Falha ao contactar {active.upper()}. Verifica se a chave API está correta / se o modelo "
            f"'{settings.gemini_model if active == 'gemini' else settings.ollama_model}' está disponível."
        ),
    }


def apply_universe_pack(
    pack_id: str,
    mode: str = "add",
    database: Database = default_db,
) -> dict[str, Any]:
    """Adds or replaces watchlist tickers for a given curated pack in 1 click."""
    pack = UNIVERSE_PACKS.get(pack_id)
    if not pack:
        raise ValueError(f"Pacote '{pack_id}' não encontrado.")

    asset_type = pack["asset_type"]
    tickers = pack["tickers"]

    if mode == "replace_class":
        existing = database.get_watchlist(asset_type=asset_type, only_enabled=False)
        for item in existing:
            database.delete_watchlist_ticker(item["ticker"])

    added = 0
    for tk in tickers:
        database.upsert_watchlist_ticker(tk, asset_type=asset_type, enabled=True)
        added += 1

    return {
        "status": "ok",
        "pack_id": pack_id,
        "pack_name": pack["name"],
        "mode": mode,
        "applied_count": added,
        "overview": get_settings_overview(database=database),
    }
