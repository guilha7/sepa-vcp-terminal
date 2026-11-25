import logging
import math
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

import ccxt
import numpy as np
import pandas as pd
import yfinance as yf

from app.config import settings
from app.database import db

logger = logging.getLogger(__name__)

_RATE_LOCK = threading.Lock()
_LAST_REQ_TS = 0.0
_MIN_SPACING_SEC = 0.12

# Circuit breaker for Binance public endpoints (some regions return HTTP 451 / timeout)
_BINANCE_CLIENT: Optional[ccxt.binance] = None
_BINANCE_BLOCKED_UNTIL: float = 0.0

KNOWN_CRYPTO_BASES = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "TRX", "AVAX", "LINK",
    "SUI", "TON", "SHIB", "DOT", "BCH", "LTC", "NEAR", "UNI", "APT", "ICP",
    "PEPE", "RENDER", "TAO", "FET", "AAVE", "ARB", "OP", "INJ", "ATOM", "HBAR",
    "MATIC", "POL", "FIL", "SEI", "TIA", "WIF", "BONK", "RUNE", "STX", "IMX",
}


def _rate_limit_wait() -> None:
    global _LAST_REQ_TS
    with _RATE_LOCK:
        now = time.monotonic()
        elapsed = now - _LAST_REQ_TS
        if elapsed < _MIN_SPACING_SEC:
            time.sleep(_MIN_SPACING_SEC - elapsed)
        _LAST_REQ_TS = time.monotonic()


def normalize_ticker(raw: str) -> str:
    t = raw.strip().upper().replace(" ", "")
    if "/" in t:
        base, quote = t.split("/", 1)
        if quote in ("USDT", "USD", "USDC", "BUSD"):
            return f"{base}-USD"
        return f"{base}-{quote}"
    if t.endswith("USDT") and len(t) > 4:
        return f"{t[:-4]}-USD"
    if t in KNOWN_CRYPTO_BASES:
        return f"{t}-USD"
    return t


def is_crypto_ticker(ticker: str) -> bool:
    t = ticker.strip().upper()
    if t.endswith("-USD") or t.endswith("-USDT") or "/" in t:
        base = t.split("-")[0].split("/")[0]
        if base in KNOWN_CRYPTO_BASES or t.endswith("-USD"):
            return True
    return t in KNOWN_CRYPTO_BASES


def to_binance_symbol(ticker: str) -> Optional[str]:
    t = normalize_ticker(ticker)
    if not t.endswith("-USD"):
        return None
    base = t[:-4]
    return f"{base}/USDT"


def _get_binance_client() -> Optional[ccxt.binance]:
    global _BINANCE_CLIENT, _BINANCE_BLOCKED_UNTIL
    if time.time() < _BINANCE_BLOCKED_UNTIL:
        return None
    if _BINANCE_CLIENT is None:
        _BINANCE_CLIENT = ccxt.binance(
            {
                "enableRateLimit": True,
                "timeout": 5000,
                "options": {"defaultType": "spot"},
            }
        )
    return _BINANCE_CLIENT


def _records_to_df(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    df = pd.DataFrame(records)
    for col in ("open", "high", "low", "close", "volume"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    df["volume"] = df["volume"].fillna(0.0)
    return df


def _df_to_records(df: pd.DataFrame) -> list[dict]:
    records: list[dict] = []
    if df is None or df.empty:
        return records
    work = df.copy()
    if isinstance(work.columns, pd.MultiIndex):
        work.columns = work.columns.get_level_values(0)
    work = work.rename(columns={c: str(c).lower() for c in work.columns})
    required = {"open", "high", "low", "close"}
    if not required.issubset(set(work.columns)):
        return records
    if "volume" not in work.columns:
        work["volume"] = 0.0

    for idx, row in work.iterrows():
        try:
            o = float(row["open"])
            h = float(row["high"])
            l = float(row["low"])
            c = float(row["close"])
            v = float(row["volume"]) if pd.notna(row["volume"]) else 0.0
            if any(math.isnan(x) or math.isinf(x) for x in (o, h, l, c)):
                continue
            if isinstance(idx, (pd.Timestamp, datetime)):
                dt_str = idx.strftime("%Y-%m-%d")
            else:
                dt_str = str(idx)[:10]
            records.append(
                {
                    "date": dt_str,
                    "open": round(o, 6),
                    "high": round(h, 6),
                    "low": round(l, 6),
                    "close": round(c, 6),
                    "volume": round(max(v, 0.0), 4),
                }
            )
        except Exception:
            continue

    # Deduplicate by date keeping last
    dedup: dict[str, dict] = {}
    for rec in records:
        dedup[rec["date"]] = rec
    return [dedup[k] for k in sorted(dedup.keys())]


def _fetch_crypto_ccxt(ticker: str, limit: int = 420) -> Optional[list[dict]]:
    global _BINANCE_BLOCKED_UNTIL
    client = _get_binance_client()
    symbol = to_binance_symbol(ticker)
    if client is None or not symbol:
        return None
    try:
        _rate_limit_wait()
        ohlcv = client.fetch_ohlcv(symbol, timeframe="1d", limit=limit)
        if not ohlcv or len(ohlcv) < 30:
            return None
        records = []
        for candle in ohlcv:
            ts_ms, o, h, l, c, v = candle[:6]
            dt_str = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
            if None in (o, h, l, c):
                continue
            records.append(
                {
                    "date": dt_str,
                    "open": round(float(o), 6),
                    "high": round(float(h), 6),
                    "low": round(float(l), 6),
                    "close": round(float(c), 6),
                    "volume": round(float(v or 0.0), 4),
                }
            )
        return records if len(records) >= 30 else None
    except Exception as exc:
        msg = str(exc).lower()
        # Geo-restriction (451) or network unreachable -> pause Binance attempts for 15 minutes
        if "451" in msg or "restricted" in msg or "timed out" in msg or "connection" in msg:
            _BINANCE_BLOCKED_UNTIL = time.time() + 900
            logger.warning("Binance public API indisponível (%s). A usar fallback yfinance.", exc)
        else:
            logger.debug("Binance fetch falhou para %s: %s", ticker, exc)
        return None


def _fetch_yfinance_single(ticker: str, period: str = "15mo") -> Optional[list[dict]]:
    try:
        _rate_limit_wait()
        tk = yf.Ticker(ticker)
        hist = tk.history(period=period, interval="1d", auto_adjust=True)
        records = _df_to_records(hist)
        return records if records else None
    except Exception as exc:
        logger.warning("yfinance single fetch falhou para %s: %s", ticker, exc)
        return None


def get_ohlcv(
    ticker: str,
    period: str = "15mo",
    force_refresh: bool = False,
) -> tuple[pd.DataFrame, str, list[str]]:
    """
    Fetch daily OHLCV DataFrame with SQLite TTL caching.
    Returns (DataFrame, data_source, warnings).
    """
    norm = normalize_ticker(ticker)
    cache_key = f"ohlcv:{norm}:{period}"
    warnings: list[str] = []

    if not force_refresh:
        cached = db.cache_get(cache_key)
        if cached and isinstance(cached, dict) and cached.get("records"):
            return _records_to_df(cached["records"]), cached.get("source", "cache"), warnings

    records: Optional[list[dict]] = None
    source = "yfinance"

    if is_crypto_ticker(norm):
        limit = 450 if period in ("15mo", "18mo", "2y") else 365
        records = _fetch_crypto_ccxt(norm, limit=limit)
        if records:
            source = "ccxt:binance"
        else:
            records = _fetch_yfinance_single(norm, period=period)
            source = "yfinance:fallback"
    else:
        records = _fetch_yfinance_single(norm, period=period)
        source = "yfinance"

    if records:
        db.cache_set(
            cache_key,
            "prices",
            {"records": records, "source": source},
            settings.cache_ttl_prices,
        )
        return _records_to_df(records), source, warnings

    # Fallback to stale cache if available
    stale = db.cache_get(cache_key, allow_stale=True)
    if stale and isinstance(stale, dict) and stale.get("records"):
        warnings.append(f"A usar dados em cache (desatualizados) para {norm} devido a falha temporária na fonte.")
        return _records_to_df(stale["records"]), f"{stale.get('source', 'cache')}:stale", warnings

    warnings.append(f"Não foi possível obter histórico de preços para {norm}.")
    return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"]), "none", warnings


def get_batch_ohlcv(
    tickers: list[str],
    period: str = "15mo",
    force_refresh: bool = False,
    progress_callback=None,
) -> tuple[dict[str, pd.DataFrame], dict[str, str], list[str]]:
    """
    Fetch OHLCV for many tickers efficiently using SQLite cache + chunked yf.download + ccxt for crypto.
    Uses cloud-safe concurrency (chunk=15, threads=4, timeout=15s) and optional progress_callback(done, total, label).
    Returns (dataframes_by_ticker, sources_by_ticker, warnings).
    """
    result: dict[str, pd.DataFrame] = {}
    sources: dict[str, str] = {}
    warnings: list[str] = []
    missing_stocks: list[str] = []
    missing_crypto: list[str] = []

    unique_tickers = list(dict.fromkeys(normalize_ticker(t) for t in tickers if t and t.strip()))

    for t in unique_tickers:
        cache_key = f"ohlcv:{t}:{period}"
        if not force_refresh:
            cached = db.cache_get(cache_key)
            if cached and isinstance(cached, dict) and cached.get("records"):
                result[t] = _records_to_df(cached["records"])
                sources[t] = cached.get("source", "cache")
                continue
        if is_crypto_ticker(t):
            missing_crypto.append(t)
        else:
            missing_stocks.append(t)

    # 1. Crypto: try Binance public API first, gather any failures for yfinance batch fallback
    crypto_yf_fallback: list[str] = []
    for ct in missing_crypto:
        recs = _fetch_crypto_ccxt(ct, limit=450)
        if recs:
            db.cache_set(f"ohlcv:{ct}:{period}", "prices", {"records": recs, "source": "ccxt:binance"}, settings.cache_ttl_prices)
            result[ct] = _records_to_df(recs)
            sources[ct] = "ccxt:binance"
        else:
            crypto_yf_fallback.append(ct)

    # 2. Batch download stocks + crypto fallbacks via yf.download in cloud-safe chunks of 15 (4 threads, 15s timeout)
    yf_queue = missing_stocks + crypto_yf_fallback
    chunk_size = 15
    total_chunks = max(1, (len(yf_queue) + chunk_size - 1) // chunk_size)
    for chunk_idx, i in enumerate(range(0, len(yf_queue), chunk_size), start=1):
        chunk = yf_queue[i : i + chunk_size]
        if progress_callback:
            try:
                progress_callback(
                    chunk_idx - 1,
                    total_chunks,
                    f"Lote {chunk_idx}/{total_chunks} ({chunk[0]}…{chunk[-1]})",
                )
            except Exception:
                pass
        if i > 0:
            time.sleep(0.35)  # Polite pacing between Yahoo Finance chunks
        try:
            _rate_limit_wait()
            raw = yf.download(
                tickers=chunk if len(chunk) > 1 else chunk[0],
                period=period,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=4,
                timeout=15,
                progress=False,
            )
            if raw is None or raw.empty:
                continue

            for t in chunk:
                try:
                    if len(chunk) == 1:
                        sub_df = raw
                    else:
                        if isinstance(raw.columns, pd.MultiIndex) and t in raw.columns.get_level_values(0):
                            sub_df = raw[t]
                        else:
                            sub_df = None
                    if sub_df is None or sub_df.empty:
                        continue
                    recs = _df_to_records(sub_df)
                    if recs:
                        src = "yfinance:fallback" if t in crypto_yf_fallback else "yfinance"
                        db.cache_set(f"ohlcv:{t}:{period}", "prices", {"records": recs, "source": src}, settings.cache_ttl_prices)
                        result[t] = _records_to_df(recs)
                        sources[t] = src
                except Exception as inner_exc:
                    logger.debug("Erro ao processar %s do batch yfinance: %s", t, inner_exc)
        except Exception as exc:
            warnings.append(f"Falha parcial no download em lote ({chunk[0]}..{chunk[-1]}): {exc}")
            logger.warning("yf.download batch falhou: %s", exc)
        if progress_callback:
            try:
                progress_callback(chunk_idx, total_chunks, f"Lote {chunk_idx}/{total_chunks} concluído")
            except Exception:
                pass

    # 3. Stale cache fallback for any still-missing ticker
    for t in unique_tickers:
        if t not in result or result[t].empty:
            stale = db.cache_get(f"ohlcv:{t}:{period}", allow_stale=True)
            if stale and isinstance(stale, dict) and stale.get("records"):
                result[t] = _records_to_df(stale["records"])
                sources[t] = f"{stale.get('source', 'cache')}:stale"
                warnings.append(f"Usada cache anterior para {t}.")

    return result, sources, warnings


def get_latest_price(ticker: str, force_refresh: bool = False) -> tuple[Optional[float], list[str]]:
    df, _, warnings = get_ohlcv(ticker, period="1mo", force_refresh=force_refresh)
    if df.empty:
        # Try 15mo cache if already stored
        df2, _, w2 = get_ohlcv(ticker, period="15mo", force_refresh=False)
        if not df2.empty:
            return float(df2["close"].iloc[-1]), warnings
        return None, warnings + w2
    return float(df["close"].iloc[-1]), warnings


def get_eurusd_rate(force_refresh: bool = False) -> tuple[float, list[str]]:
    """
    Fetches live EUR/USD exchange rate (EURUSD=X via yfinance, 100% free) with 15-min SQLite cache.
    Returns (rate_usd_per_1_eur, warnings). Example: 1.08 means 1 EUR = 1.08 USD.
    """
    cache_key = "fx:EURUSD=X"
    if not force_refresh:
        cached = db.cache_get(cache_key)
        if isinstance(cached, dict) and cached.get("rate"):
            return float(cached["rate"]), []

    warnings: list[str] = []
    try:
        df, _, w = get_ohlcv("EURUSD=X", period="1mo", force_refresh=force_refresh)
        if not df.empty:
            rate = round(float(df["close"].iloc[-1]), 5)
            if 0.5 < rate < 2.5:
                db.cache_set(cache_key, "prices", {"rate": rate}, max(settings.cache_ttl_prices, 900))
                return rate, warnings
        warnings.extend(w)
    except Exception as exc:
        logger.debug("Falha ao obter câmbio EURUSD=X: %s", exc)

    stale = db.cache_get(cache_key, allow_stale=True)
    if isinstance(stale, dict) and stale.get("rate"):
        warnings.append("Taxa EUR/USD carregada da cache anterior.")
        return float(stale["rate"]), warnings

    warnings.append("Taxa EUR/USD indisponível; usada estimativa de segurança 1.08.")
    return 1.08, warnings


def _safe_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _extract_next_earnings_date(tk: yf.Ticker, info: dict) -> Optional[str]:
    today = datetime.now(timezone.utc).date()
    candidates: list[datetime.date] = []

    # Method 1: calendar dict/DataFrame
    try:
        cal = tk.calendar
        if isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if isinstance(ed, list):
                for item in ed:
                    if hasattr(item, "date"):
                        candidates.append(item.date())
                    elif isinstance(item, datetime):
                        candidates.append(item.date())
                    elif hasattr(item, "year"):
                        candidates.append(item)
            elif hasattr(ed, "year"):
                candidates.append(ed.date() if isinstance(ed, datetime) else ed)
        elif isinstance(cal, pd.DataFrame) and not cal.empty:
            for col in cal.columns:
                val = cal[col].iloc[0]
                if isinstance(val, (pd.Timestamp, datetime)):
                    candidates.append(val.date())
    except Exception:
        pass

    # Method 2: info timestamps
    for key in ("earningsTimestamp", "earningsTimestampStart", "earningsTimestampEnd"):
        ts = info.get(key)
        if isinstance(ts, (int, float)) and ts > 0:
            try:
                d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
                candidates.append(d)
            except Exception:
                pass

    future = sorted(d for d in candidates if d >= today)
    if future:
        return future[0].isoformat()
    return None


def get_fundamentals_and_earnings(
    ticker: str,
    force_refresh: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """
    Fetch stock fundamentals & upcoming earnings date with 24h SQLite TTL cache.
    Gracefully handles crypto and Yahoo Finance partial failures.
    """
    norm = normalize_ticker(ticker)
    cache_key = f"fund:{norm}"
    warnings: list[str] = []

    if not force_refresh:
        cached = db.cache_get(cache_key)
        if cached and isinstance(cached, dict):
            return cached, warnings

    is_crypto = is_crypto_ticker(norm)
    base_data: dict[str, Any] = {
        "ticker": norm,
        "asset_type": "crypto" if is_crypto else "stock",
        "name": norm,
        "sector": "Criptomoedas" if is_crypto else None,
        "industry": "Ativo Digital" if is_crypto else None,
        "currency": "USD",
        "market_cap": None,
        "trailing_pe": None,
        "forward_pe": None,
        "revenue_growth": None,
        "earnings_growth": None,
        "profit_margins": None,
        "return_on_equity": None,
        "beta": None,
        "next_earnings_date": None,
        "days_to_earnings": None,
        "earnings_within_14d": False,
        "available": False,
    }

    try:
        _rate_limit_wait()
        tk = yf.Ticker(norm)
        info = tk.info or {}
        if info:
            base_data["name"] = info.get("shortName") or info.get("longName") or norm
            base_data["currency"] = info.get("currency") or "USD"
            base_data["market_cap"] = _safe_float(info.get("marketCap"))
            base_data["available"] = True

            if not is_crypto:
                quote_type = str(info.get("quoteType") or "").upper()
                base_data["quote_type"] = quote_type
                base_data["sector"] = info.get("sector") or ("ETF Setorial / Índice" if quote_type == "ETF" else None)
                base_data["industry"] = info.get("industry") or (info.get("category") if quote_type == "ETF" else None)
                base_data["trailing_pe"] = _safe_float(info.get("trailingPE"))
                base_data["forward_pe"] = _safe_float(info.get("forwardPE"))
                base_data["revenue_growth"] = _safe_float(info.get("revenueGrowth"))
                base_data["earnings_growth"] = _safe_float(info.get("earningsGrowth"))
                base_data["profit_margins"] = _safe_float(info.get("profitMargins"))
                base_data["return_on_equity"] = _safe_float(info.get("returnOnEquity"))
                base_data["beta"] = _safe_float(info.get("beta"))

                if quote_type != "ETF":
                    next_ed = _extract_next_earnings_date(tk, info)
                    if next_ed:
                        base_data["next_earnings_date"] = next_ed
                        days = (datetime.fromisoformat(next_ed).date() - datetime.now(timezone.utc).date()).days
                        base_data["days_to_earnings"] = days
                        base_data["earnings_within_14d"] = 0 <= days <= 14

        db.cache_set(cache_key, "fundamentals", base_data, settings.cache_ttl_fundamentals)
        return base_data, warnings
    except Exception as exc:
        logger.warning("Falha ao obter fundamentais para %s: %s", norm, exc)
        stale = db.cache_get(cache_key, allow_stale=True)
        if stale and isinstance(stale, dict):
            warnings.append(f"Fundamentais de {norm} carregados de cache anterior.")
            return stale, warnings
        warnings.append(f"Métricas fundamentais temporariamente indisponíveis para {norm}.")
        return base_data, warnings
