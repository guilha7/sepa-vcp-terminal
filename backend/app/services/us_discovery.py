import logging
import re
from typing import Any

import httpx

from app.config import DEFAULT_STOCK_UNIVERSE

logger = logging.getLogger(__name__)

TV_AMERICA_SCAN_URL = "https://scanner.tradingview.com/america/scan"

US_DISCOVERY_PRESETS: dict[str, dict[str, Any]] = {
    "sepa_leaders": {
        "id": "sepa_leaders",
        "name": "Líderes Stage 2 (Todos os EUA)",
        "description": "Pré-filtra ~7.000 ações NYSE/NASDAQ/AMEX em Stage 2 (Preço ≥ $5, Vol ≥ 300k, Preço ≥ SMA50 ≥ SMA200, +15% em 6M).",
        "sort_by": "Perf.6M",
        "filters": [
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
            {"left": "exchange", "operation": "in_range", "right": ["NYSE", "NASDAQ", "AMEX"]},
            {"left": "close", "operation": "greater", "right": 5},
            {"left": "average_volume_30d_calc", "operation": "greater", "right": 300000},
            {"left": "close", "operation": "egreater", "right": "SMA50"},
            {"left": "SMA50", "operation": "egreater", "right": "SMA200"},
            {"left": "Perf.6M", "operation": "greater", "right": 15},
        ],
    },
    "small_mid_growth": {
        "id": "small_mid_growth",
        "name": "Joias Small & Mid-Cap ($300M–$15B)",
        "description": "Caça empresas emergentes de médio/pequeno porte em tendência Stage 2 antes de entrarem no S&P 500.",
        "sort_by": "Perf.3M",
        "filters": [
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
            {"left": "exchange", "operation": "in_range", "right": ["NYSE", "NASDAQ", "AMEX"]},
            {"left": "market_cap_basic", "operation": "in_range", "right": [300_000_000, 15_000_000_000]},
            {"left": "close", "operation": "greater", "right": 5},
            {"left": "average_volume_30d_calc", "operation": "greater", "right": 250000},
            {"left": "close", "operation": "egreater", "right": "SMA50"},
            {"left": "SMA50", "operation": "egreater", "right": "SMA200"},
            {"left": "Perf.3M", "operation": "greater", "right": 10},
        ],
    },
    "volume_breakouts": {
        "id": "volume_breakouts",
        "name": "Explosão de Volume & Momentum Hoje",
        "description": "Descobre ações em todos os EUA com volume ≥ 1.5x acima da média e alta forte hoje (EP / Breakouts).",
        "sort_by": "relative_volume_10d_calc",
        "filters": [
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
            {"left": "exchange", "operation": "in_range", "right": ["NYSE", "NASDAQ", "AMEX"]},
            {"left": "close", "operation": "greater", "right": 5},
            {"left": "average_volume_30d_calc", "operation": "greater", "right": 300000},
            {"left": "relative_volume_10d_calc", "operation": "greater", "right": 1.5},
            {"left": "change", "operation": "greater", "right": 2.5},
            {"left": "close", "operation": "egreater", "right": "SMA50"},
        ],
    },
    "near_52w_high": {
        "id": "near_52w_high",
        "name": "Força Relativa 1 Ano (Top Performers)",
        "description": "Maiores vencedoras anuais em Stage 2 acima de $10 com elevada liquidez institucional.",
        "sort_by": "Perf.Y",
        "filters": [
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
            {"left": "exchange", "operation": "in_range", "right": ["NYSE", "NASDAQ", "AMEX"]},
            {"left": "close", "operation": "greater", "right": 10},
            {"left": "average_volume_30d_calc", "operation": "greater", "right": 300000},
            {"left": "close", "operation": "egreater", "right": "SMA50"},
            {"left": "SMA50", "operation": "egreater", "right": "SMA200"},
            {"left": "Perf.Y", "operation": "greater", "right": 25},
        ],
    },
}

_VALID_US_TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:-[A-Z])?$")


def _clean_yf_us_ticker(raw: str) -> str:
    """Normalizes NYSE/NASDAQ ticker symbols for yfinance (e.g. BRK.B -> BRK-B)."""
    tk = (raw or "").strip().upper().replace(".", "-")
    if not _VALID_US_TICKER_RE.match(tk):
        return ""
    return tk


def list_us_discovery_presets() -> list[dict[str, Any]]:
    return [
        {"id": p["id"], "name": p["name"], "description": p["description"]}
        for p in US_DISCOVERY_PRESETS.values()
    ]


def screen_all_us_candidates(
    preset: str = "sepa_leaders",
    limit: int = 75,
) -> dict[str, Any]:
    """
    Stage 1 Funnel (0€ / No API key / ~0.5–1.5s):
    Pre-screens ALL ~7,000 NYSE/NASDAQ/AMEX stocks via TradingView public America scanner
    to extract the top Stage-2/momentum candidates across the entire US stock market.
    Falls back cleanly to yfinance built-in screener + core leaders if TradingView is unavailable.
    """
    cfg = US_DISCOVERY_PRESETS.get(preset) or US_DISCOVERY_PRESETS["sepa_leaders"]
    capped_limit = max(20, min(int(limit), 120))
    fetch_count = min(capped_limit + 25, 160)

    payload = {
        "filter": cfg["filters"],
        "options": {"lang": "en"},
        "markets": ["america"],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": [
            "name",
            "description",
            "close",
            "change",
            "volume",
            "relative_volume_10d_calc",
            "Perf.3M",
            "Perf.6M",
            "Perf.Y",
            "market_cap_basic",
            "sector",
        ],
        "sort": {"sortBy": cfg["sort_by"], "sortOrder": "desc"},
        "range": [0, fetch_count],
    }

    try:
        with httpx.Client(
            timeout=12.0,
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        ) as client:
            resp = client.post(TV_AMERICA_SCAN_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()

        total_matched = int(data.get("totalCount") or 0)
        rows = data.get("data") or []
        tickers: list[str] = []
        meta_by_ticker: dict[str, dict[str, Any]] = {}

        for row in rows:
            vals = row.get("d") or []
            if not vals:
                continue
            tk = _clean_yf_us_ticker(str(vals[0]))
            if not tk or tk in meta_by_ticker:
                continue
            tickers.append(tk)
            meta_by_ticker[tk] = {
                "name": vals[1] if len(vals) > 1 and vals[1] else tk,
                "sector": vals[10] if len(vals) > 10 and vals[10] else None,
                "market_cap": vals[9] if len(vals) > 9 else None,
                "perf_6m": round(float(vals[7]), 2) if len(vals) > 7 and vals[7] is not None else None,
            }
            if len(tickers) >= capped_limit:
                break

        if tickers:
            return {
                "source": "tradingview_us_all",
                "preset": cfg["id"],
                "preset_name": cfg["name"],
                "us_universe_scanned": "~7.000 ações (NYSE + NASDAQ + AMEX)",
                "total_matched_stage1": total_matched,
                "selected_count": len(tickers),
                "tickers": tickers,
                "meta": meta_by_ticker,
                "warnings": [],
            }
    except Exception as exc:
        logger.warning("Pré-filtro TradingView EUA falhou (%s); a tentar fallback yfinance screener...", exc)

    # Fallback: yfinance built-in screener + core leaders
    fallback_tickers: list[str] = []
    warnings: list[str] = [
        "Screener TradingView EUA temporariamente indisponível; usado fallback Yahoo Screener + Líderes EUA."
    ]
    try:
        import yfinance as yf

        if hasattr(yf, "screen"):
            for scr_name in ("day_gainers", "growth_technology_stocks", "most_actives"):
                try:
                    res = yf.screen(scr_name)
                    for q in (res.get("quotes") or []):
                        tk = _clean_yf_us_ticker(q.get("symbol", ""))
                        if tk and tk not in fallback_tickers:
                            fallback_tickers.append(tk)
                except Exception:
                    continue
    except Exception:
        pass

    for tk in DEFAULT_STOCK_UNIVERSE:
        if tk not in fallback_tickers:
            fallback_tickers.append(tk)

    final = fallback_tickers[:capped_limit]
    return {
        "source": "yfinance_screener_fallback",
        "preset": cfg["id"],
        "preset_name": cfg["name"],
        "us_universe_scanned": "Fallback Yahoo Screener + Líderes EUA",
        "total_matched_stage1": len(final),
        "selected_count": len(final),
        "tickers": final,
        "meta": {},
        "warnings": warnings,
    }
