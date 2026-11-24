"""
Free Binance Public USDS-M Futures Derivatives Engine (https://fapi.binance.com — 0€, NO API KEY).
Computes institutional crypto flow metrics:
- Funding Rate (detects overheated euphoria / long squeeze risk vs short squeeze fuel)
- Open Interest (OI) & 24h OI Change % crossed with 24h price change
- Top Traders Long/Short Position Ratio (whale positioning)
- Altseason Gauge (ETH/BTC trend + % of altcoins outperforming BTC over 30 days)
"""

import logging
import time
from typing import Any, Optional

import httpx
import pandas as pd

from app.config import settings
from app.database import db
from app.services.market_data import normalize_ticker

logger = logging.getLogger(__name__)

FAPI_BASE = "https://fapi.binance.com"
_FAPI_BLOCKED_UNTIL = 0.0

TOP_PERP_TICKERS = [
    "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD",
    "XRP-USD", "DOGE-USD", "AVAX-USD", "LINK-USD",
]


def _to_fapi_symbol(ticker: str) -> Optional[str]:
    norm = normalize_ticker(ticker)
    if not norm.endswith("-USD"):
        return None
    base = norm[:-4]
    # Handle 1000-prefixed Binance perps
    if base in ("PEPE", "SHIB", "BONK", "FLOKI"):
        return f"1000{base}USDT"
    return f"{base}USDT"


def classify_funding_signal(funding_rate_pct: Optional[float]) -> dict[str, str]:
    if funding_rate_pct is None:
        return {"code": "INDISPONIVEL", "label": "N/D", "detail": "Funding indisponível."}
    if funding_rate_pct >= 0.05:
        return {
            "code": "EUFORIA",
            "label": "Euforia (Risco Long Squeeze)",
            "detail": f"Funding muito positivo ({funding_rate_pct:+.4f}%): excesso de longs alavancados.",
        }
    if funding_rate_pct <= -0.02:
        return {
            "code": "SHORT_SQUEEZE",
            "label": "Potencial Short Squeeze",
            "detail": f"Funding negativo ({funding_rate_pct:+.4f}%): shorts a pagar longs — combustível de alta.",
        }
    return {
        "code": "SAUDAVEL",
        "label": "Equilibrado",
        "detail": f"Funding saudável ({funding_rate_pct:+.4f}%): sem excesso extremo de alavancagem.",
    }


def classify_oi_price_flow(
    price_change_24h: Optional[float],
    oi_change_24h: Optional[float],
) -> dict[str, str]:
    if price_change_24h is None or oi_change_24h is None:
        return {"code": "NEUTRO", "label": "Fluxo Neutro"}
    if price_change_24h >= 0.5 and oi_change_24h >= 2.0:
        return {"code": "DINHEIRO_NOVO_BULL", "label": "Dinheiro Novo (Bullish)"}
    if price_change_24h >= 0.5 and oi_change_24h <= -2.0:
        return {"code": "SHORT_COVERING", "label": "Short Covering (Frágil)"}
    if price_change_24h <= -0.5 and oi_change_24h >= 2.0:
        return {"code": "SHORTING_AGRESSIVO", "label": "Shorts Agressivos (Bearish)"}
    if price_change_24h <= -0.5 and oi_change_24h <= -2.0:
        return {"code": "LIQUIDACAO_LONGS", "label": "Liquidação de Longs"}
    return {"code": "NEUTRO", "label": "Equilibrado"}


def get_crypto_derivatives_for_ticker(
    ticker: str,
    price_change_24h: Optional[float] = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Fetches free Binance Futures Funding Rate, Open Interest 24h & Top Traders L/S Ratio."""
    global _FAPI_BLOCKED_UNTIL
    norm = normalize_ticker(ticker)
    cache_key = f"crypto_deriv:{norm}"

    if not force_refresh:
        cached = db.cache_get(cache_key)
        if isinstance(cached, dict):
            return cached

    sym = _to_fapi_symbol(norm)
    empty = {
        "ticker": norm,
        "symbol": sym,
        "available": False,
        "funding_rate_pct": None,
        "funding_annualized_pct": None,
        "funding_signal": classify_funding_signal(None),
        "open_interest_usd": None,
        "oi_change_24h_pct": None,
        "oi_flow": classify_oi_price_flow(None, None),
        "top_traders_ls_ratio": None,
        "top_long_pct": None,
        "top_short_pct": None,
    }

    if not sym or time.time() < _FAPI_BLOCKED_UNTIL:
        return empty

    try:
        with httpx.Client(timeout=4.5) as client:
            # 1. Funding Rate & Mark Price
            r_prem = client.get(f"{FAPI_BASE}/fapi/v1/premiumIndex", params={"symbol": sym})
            if r_prem.status_code == 451:
                _FAPI_BLOCKED_UNTIL = time.time() + 900
                return empty
            if r_prem.status_code != 200:
                return empty
            prem = r_prem.json()
            raw_funding = float(prem.get("lastFundingRate", 0.0))
            funding_pct = round(raw_funding * 100.0, 4)
            funding_ann = round(funding_pct * 3.0 * 365.0, 1)  # 3x 8h intervals/day

            # 2. Open Interest History (24h change)
            oi_usd = None
            oi_chg_24h = None
            try:
                r_oi = client.get(
                    f"{FAPI_BASE}/futures/data/openInterestHist",
                    params={"symbol": sym, "period": "1h", "limit": 25},
                )
                if r_oi.status_code == 200:
                    hist = r_oi.json()
                    if isinstance(hist, list) and len(hist) >= 2:
                        first_val = float(hist[0].get("sumOpenInterestValue", 0.0))
                        last_val = float(hist[-1].get("sumOpenInterestValue", 0.0))
                        oi_usd = round(last_val, 0)
                        if first_val > 0:
                            oi_chg_24h = round((last_val - first_val) / first_val * 100.0, 2)
            except Exception:
                pass

            # 3. Top Traders Long/Short Position Ratio
            ls_ratio = None
            long_pct = None
            short_pct = None
            try:
                r_ls = client.get(
                    f"{FAPI_BASE}/futures/data/topLongShortPositionRatio",
                    params={"symbol": sym, "period": "1h", "limit": 1},
                )
                if r_ls.status_code == 200:
                    ls_list = r_ls.json()
                    if isinstance(ls_list, list) and ls_list:
                        ls_ratio = round(float(ls_list[-1].get("longShortRatio", 1.0)), 2)
                        long_pct = round(float(ls_list[-1].get("longAccount", 0.5)) * 100.0, 1)
                        short_pct = round(float(ls_list[-1].get("shortAccount", 0.5)) * 100.0, 1)
            except Exception:
                pass

        result = {
            "ticker": norm,
            "symbol": sym,
            "available": True,
            "funding_rate_pct": funding_pct,
            "funding_annualized_pct": funding_ann,
            "funding_signal": classify_funding_signal(funding_pct),
            "open_interest_usd": oi_usd,
            "oi_change_24h_pct": oi_chg_24h,
            "oi_flow": classify_oi_price_flow(price_change_24h, oi_chg_24h),
            "top_traders_ls_ratio": ls_ratio,
            "top_long_pct": long_pct,
            "top_short_pct": short_pct,
        }
        db.cache_set(cache_key, "prices", result, settings.cache_ttl_prices)
        return result
    except Exception as exc:
        msg = str(exc).lower()
        if "451" in msg or "timeout" in msg or "connect" in msg:
            _FAPI_BLOCKED_UNTIL = time.time() + 600
        logger.debug("Binance Futures API indisponível para %s: %s", norm, exc)
        return empty


def compute_altseason_gauge(dfs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """
    Computes Crypto Altseason Gauge using ETH/BTC trend vs SMA 50 +
    percentage of liquid altcoins outperforming BTC-USD over the last 30 days.
    """
    btc_df = dfs.get("BTC-USD")
    eth_df = dfs.get("ETH-USD")
    if btc_df is None or btc_df.empty or len(btc_df) < 35:
        return {
            "regime": "INDISPONIVEL",
            "label": "Indisponível",
            "altseason_index": 50,
            "eth_btc_ratio": None,
            "eth_btc_above_sma50": None,
            "alts_beating_btc_pct": None,
        }

    btc_c = btc_df["close"].astype(float)
    btc_30d = (float(btc_c.iloc[-1]) - float(btc_c.iloc[-31])) / float(btc_c.iloc[-31]) * 100.0

    eth_btc_ratio = None
    eth_btc_above_50 = None
    if eth_df is not None and len(eth_df) >= 55:
        m = pd.merge(
            eth_df[["date", "close"]].rename(columns={"close": "eth"}),
            btc_df[["date", "close"]].rename(columns={"close": "btc"}),
            on="date",
            how="inner",
        )
        if len(m) >= 50:
            ratio_s = m["eth"].astype(float) / m["btc"].astype(float).replace(0, pd.NA)
            ratio_s = ratio_s.dropna()
            if len(ratio_s) >= 50:
                eth_btc_ratio = round(float(ratio_s.iloc[-1]), 5)
                eth_btc_above_50 = bool(float(ratio_s.iloc[-1]) > float(ratio_s.rolling(50).mean().iloc[-1]))

    beating = 0
    total_alts = 0
    for tk, df in dfs.items():
        if not tk.endswith("-USD") or tk == "BTC-USD" or df is None or len(df) < 32:
            continue
        c = df["close"].astype(float)
        prev = float(c.iloc[-31])
        if prev <= 0:
            continue
        ret_30d = (float(c.iloc[-1]) - prev) / prev * 100.0
        total_alts += 1
        if ret_30d > btc_30d:
            beating += 1

    alts_pct = round((beating / total_alts) * 100.0, 1) if total_alts > 0 else 50.0
    # Composite index 0..100
    idx = alts_pct
    if eth_btc_above_50 is True:
        idx = min(100.0, idx + 8.0)
    elif eth_btc_above_50 is False:
        idx = max(0.0, idx - 8.0)
    idx = round(idx, 1)

    if idx >= 65.0:
        regime, label = "ALTSEASON", "Altseason (Capital a rodar para Altcoins)"
    elif idx >= 40.0:
        regime, label = "TRANSICAO", "Transição (Seletividade em Altcoins líderes)"
    else:
        regime, label = "BITCOIN_SEASON", "Bitcoin Season (Dominância BTC)"

    return {
        "regime": regime,
        "label": label,
        "altseason_index": idx,
        "eth_btc_ratio": eth_btc_ratio,
        "eth_btc_above_sma50": eth_btc_above_50,
        "alts_beating_btc_pct": alts_pct,
        "alts_evaluated": total_alts,
    }


def get_crypto_derivatives_radar(
    dfs: dict[str, pd.DataFrame],
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Aggregates free Binance Futures derivatives across top liquid perps + Altseason Gauge."""
    items: list[dict[str, Any]] = []
    extreme_alerts: list[dict[str, Any]] = []

    for tk in TOP_PERP_TICKERS:
        df = dfs.get(tk)
        chg_24h = None
        if df is not None and len(df) >= 2:
            c1, c2 = float(df["close"].iloc[-2]), float(df["close"].iloc[-1])
            if c1 > 0:
                chg_24h = round((c2 - c1) / c1 * 100.0, 2)

        d = get_crypto_derivatives_for_ticker(tk, price_change_24h=chg_24h, force_refresh=force_refresh)
        if d["available"]:
            d["price_change_24h"] = chg_24h
            items.append(d)
            if d["funding_signal"]["code"] in ("EUFORIA", "SHORT_SQUEEZE"):
                extreme_alerts.append(
                    {
                        "ticker": tk,
                        "code": d["funding_signal"]["code"],
                        "funding_rate_pct": d["funding_rate_pct"],
                        "detail": d["funding_signal"]["detail"],
                    }
                )

    avg_funding = (
        round(sum(x["funding_rate_pct"] for x in items if x["funding_rate_pct"] is not None) / len(items), 4)
        if items
        else None
    )

    return {
        "available": len(items) > 0,
        "source": "Binance Public Futures API (0€)",
        "avg_funding_rate_pct": avg_funding,
        "assets": items,
        "extreme_funding_alerts": extreme_alerts,
        "altseason": compute_altseason_gauge(dfs),
    }
