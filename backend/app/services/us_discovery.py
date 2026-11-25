import logging
import re
from typing import Any

import httpx

from app.config import DEFAULT_STOCK_UNIVERSE

logger = logging.getLogger(__name__)

TV_AMERICA_SCAN_URL = "https://scanner.tradingview.com/america/scan"

# Curated fallback lists for Europe & Portugal PSI in case TradingView endpoints time out
PORTUGAL_PSI_CORE: list[str] = [
    "EDP.LS", "GALP.LS", "JMT.LS", "SON.LS", "NOS.LS", "BCP.LS", "NVG.LS",
    "EGL.LS", "RENE.LS", "ALTR.LS", "CTT.LS", "SEM.LS", "COR.LS", "EDPR.LS",
    "IBS.LS", "PHR.LS",
]

EUROPE_EUROZONE_CORE: list[str] = [
    "SAP.DE", "SIE.DE", "RHM.DE", "ALV.DE", "DTE.DE", "IFX.DE", "AIR.PA",
    "MC.PA", "SAF.PA", "SU.PA", "TTE.PA", "ASML.AS", "ADYEN.AS", "INGA.AS",
    "WKL.AS", "ITX.MC", "SAN.MC", "BBVA.MC", "IBE.MC", "AMS.MC", "UCG.MI",
    "ISP.MI", "RACE.MI", "LDO.MI", "ENEL.MI", "EDP.LS", "GALP.LS", "JMT.LS",
]

# Primary liquid Eurozone exchanges mapped cleanly 1-to-1 to Yahoo Finance suffixes
EU_MARKETS_CONFIG: list[dict[str, Any]] = [
    {"market": "germany", "exchange": "XETR", "suffix": ".DE", "min_vol": 150_000, "min_mcap": 1_000_000_000},
    {"market": "france", "exchange": "EURONEXT", "suffix": ".PA", "min_vol": 150_000, "min_mcap": 1_000_000_000},
    {"market": "netherlands", "exchange": "EURONEXT", "suffix": ".AS", "min_vol": 100_000, "min_mcap": 1_000_000_000},
    {"market": "spain", "exchange": "BME", "suffix": ".MC", "min_vol": 150_000, "min_mcap": 1_000_000_000},
    {"market": "italy", "exchange": "MIL", "suffix": ".MI", "min_vol": 150_000, "min_mcap": 1_000_000_000},
    {"market": "portugal", "exchange": "EURONEXT", "suffix": ".LS", "min_vol": 15_000, "min_mcap": 150_000_000},
]

US_DISCOVERY_PRESETS: dict[str, dict[str, Any]] = {
    "sepa_leaders": {
        "id": "sepa_leaders",
        "region": "US",
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
        "region": "US",
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
        "region": "US",
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
        "region": "US",
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
    "eu_leaders": {
        "id": "eu_leaders",
        "region": "EU",
        "name": "Europa Líderes Stage 2 (Euros)",
        "description": "Varre bolsas principais da Zona Euro (DAX Alemanha, CAC França, AEX Holanda, IBEX Espanha, Itália e Lisboa) em EUR.",
        "sort_by": "Perf.6M",
        "filters": [],
    },
    "portugal_psi": {
        "id": "portugal_psi",
        "region": "PT",
        "name": "Portugal — Euronext Lisboa (PSI)",
        "description": "Analisa as principais ações portuguesas (EDP, Galp, Jerónimo Martins, Sonae, NOS, BCP, Navigator, Mota-Engil...) em EUR.",
        "sort_by": "Perf.6M",
        "filters": [],
    },
}

_VALID_US_TICKER_RE = re.compile(r"^[A-Z]{1,5}(?:-[A-Z])?$")
_VALID_EU_BASE_RE = re.compile(r"^[A-Z0-9]{1,7}$")


def _clean_yf_us_ticker(raw: str) -> str:
    """Normalizes NYSE/NASDAQ ticker symbols for yfinance (e.g. BRK.B -> BRK-B)."""
    tk = (raw or "").strip().upper().replace(".", "-")
    if not _VALID_US_TICKER_RE.match(tk):
        return ""
    return tk


def _clean_yf_eu_ticker(raw: str, suffix: str) -> str:
    base = (raw or "").strip().upper()
    if not _VALID_EU_BASE_RE.match(base):
        return ""
    return f"{base}{suffix}"


def list_us_discovery_presets() -> list[dict[str, Any]]:
    return [
        {"id": p["id"], "region": p.get("region", "US"), "name": p["name"], "description": p["description"]}
        for p in US_DISCOVERY_PRESETS.values()
    ]


def _screen_portugal_psi(limit: int = 30) -> dict[str, Any]:
    """Screens Euronext Lisbon (Portugal PSI) stocks cleanly with .LS Yahoo suffixes."""
    url = "https://scanner.tradingview.com/portugal/scan"
    payload = {
        "filter": [
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
            {"left": "exchange", "operation": "equal", "right": "EURONEXT"},
            {"left": "close", "operation": "greater", "right": 0.2},
            {"left": "average_volume_30d_calc", "operation": "greater", "right": 5000},
        ],
        "options": {"lang": "en"},
        "markets": ["portugal"],
        "columns": ["name", "description", "close", "Perf.6M", "sector"],
        "sort": {"sortBy": "Perf.6M", "sortOrder": "desc"},
        "range": [0, 35],
    }
    tickers: list[str] = []
    meta: dict[str, dict[str, Any]] = {}
    total_matched = 0
    try:
        with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        total_matched = int(data.get("totalCount") or 0)
        for row in data.get("data") or []:
            vals = row.get("d") or []
            if not vals:
                continue
            tk = _clean_yf_eu_ticker(str(vals[0]), ".LS")
            if tk and tk not in meta:
                tickers.append(tk)
                meta[tk] = {
                    "name": vals[1] if len(vals) > 1 and vals[1] else tk,
                    "sector": vals[4] if len(vals) > 4 and vals[4] else None,
                    "perf_6m": round(float(vals[3]), 2) if len(vals) > 3 and vals[3] is not None else None,
                }
    except Exception as exc:
        logger.warning("Screener TradingView Portugal falhou (%s); a usar lista PSI base.", exc)

    # Guarantee major PSI blue-chips are always represented
    for core_tk in PORTUGAL_PSI_CORE:
        if core_tk not in tickers:
            tickers.append(core_tk)

    final = tickers[: max(16, min(limit, 40))]
    return {
        "source": "tradingview_portugal_psi" if total_matched > 0 else "portugal_psi_core",
        "preset": "portugal_psi",
        "preset_name": US_DISCOVERY_PRESETS["portugal_psi"]["name"],
        "us_universe_scanned": "Euronext Lisboa (Portugal PSI — EUR)",
        "total_matched_stage1": max(total_matched, len(final)),
        "selected_count": len(final),
        "tickers": final,
        "meta": meta,
        "warnings": [],
    }


def _screen_europe_leaders(limit: int = 70) -> dict[str, Any]:
    """Screens primary Eurozone exchanges (XETR, EURONEXT PA/AS/LS, BME, MIL) for Stage 2 EUR leaders."""
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    total_matched = 0
    seen: set[str] = set()

    with httpx.Client(timeout=10.0, headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}) as client:
        for cfg in EU_MARKETS_CONFIG:
            url = f"https://scanner.tradingview.com/{cfg['market']}/scan"
            payload = {
                "filter": [
                    {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
                    {"left": "exchange", "operation": "equal", "right": cfg["exchange"]},
                    {"left": "close", "operation": "greater", "right": 1.5},
                    {"left": "average_volume_30d_calc", "operation": "greater", "right": cfg["min_vol"]},
                    {"left": "market_cap_basic", "operation": "greater", "right": cfg["min_mcap"]},
                    {"left": "close", "operation": "egreater", "right": "SMA50"},
                    {"left": "SMA50", "operation": "egreater", "right": "SMA200"},
                    {"left": "Perf.6M", "operation": "greater", "right": 5},
                ],
                "options": {"lang": "en"},
                "markets": [cfg["market"]],
                "columns": ["name", "description", "close", "Perf.6M", "sector"],
                "sort": {"sortBy": "Perf.6M", "sortOrder": "desc"},
                "range": [0, 18],
            }
            try:
                resp = client.post(url, json=payload)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                total_matched += int(data.get("totalCount") or 0)
                for row in data.get("data") or []:
                    vals = row.get("d") or []
                    if not vals:
                        continue
                    tk = _clean_yf_eu_ticker(str(vals[0]), cfg["suffix"])
                    if not tk or tk in seen:
                        continue
                    seen.add(tk)
                    perf6 = float(vals[3]) if len(vals) > 3 and vals[3] is not None else 0.0
                    candidates.append(
                        (
                            perf6,
                            tk,
                            {
                                "name": vals[1] if len(vals) > 1 and vals[1] else tk,
                                "sector": vals[4] if len(vals) > 4 and vals[4] else None,
                                "perf_6m": round(perf6, 2),
                            },
                        )
                    )
            except Exception as exc:
                logger.debug("Screener Europa (%s) falhou: %s", cfg["market"], exc)

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        capped = candidates[: max(20, min(limit, 80))]
        return {
            "source": "tradingview_europe_all",
            "preset": "eu_leaders",
            "preset_name": US_DISCOVERY_PRESETS["eu_leaders"]["name"],
            "us_universe_scanned": "Zona Euro (DE/FR/NL/ES/IT/PT — EUR)",
            "total_matched_stage1": total_matched,
            "selected_count": len(capped),
            "tickers": [c[1] for c in capped],
            "meta": {c[1]: c[2] for c in capped},
            "warnings": [],
        }

    final = EUROPE_EUROZONE_CORE[: max(20, min(limit, len(EUROPE_EUROZONE_CORE)))]
    return {
        "source": "europe_core_fallback",
        "preset": "eu_leaders",
        "preset_name": US_DISCOVERY_PRESETS["eu_leaders"]["name"],
        "us_universe_scanned": "Líderes Zona Euro (Fallback)",
        "total_matched_stage1": len(final),
        "selected_count": len(final),
        "tickers": final,
        "meta": {},
        "warnings": ["Screener TradingView Europa temporariamente indisponível; usada lista base Eurozona."],
    }


def screen_all_us_candidates(
    preset: str = "sepa_leaders",
    limit: int = 75,
) -> dict[str, Any]:
    """
    Stage 1 Funnel (0€ / No API key / ~0.5–1.5s):
    Pre-screens ALL ~7,000 NYSE/NASDAQ/AMEX stocks (or Eurozone / Portugal PSI markets)
    to extract top Stage-2 / momentum candidates for Stage 2 deep SEPA/VCP/Quant analysis.
    """
    if preset == "portugal_psi":
        return _screen_portugal_psi(limit=limit)
    if preset == "eu_leaders":
        return _screen_europe_leaders(limit=limit)

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
