import time
from typing import Any, Optional

import pandas as pd

from app.services.advanced_analytics import (
    compute_asset_personality_backtest,
    compute_volume_quality,
    fetch_institutional_and_quarterly,
)
from app.services.ai_service import generate_trader_briefing
from app.services.crypto_derivatives import get_crypto_derivatives_for_ticker
from app.services.market_data import (
    get_fundamentals_and_earnings,
    get_ohlcv,
    is_crypto_ticker,
    normalize_ticker,
)
from app.services.minervini_vcp import analyze_sepa_vcp, compute_rs_line_series
from app.services.news_sentiment import get_asset_news
from app.services.quant_signals import compute_anchored_vwaps
from app.services.trader_edge import (
    compute_dcr_and_volume_runrate,
    compute_mtf_confluence,
    compute_sector_peer_rs,
    get_upcoming_macro_events,
)


def _build_single_tf_series(df: pd.DataFrame, ma_windows: tuple[int, int, int]) -> dict[str, list[dict[str, Any]]]:
    work = df.copy()
    w1, w2, w3 = ma_windows
    work["ma1"] = work["close"].rolling(w1).mean()
    work["ma2"] = work["close"].rolling(w2).mean()
    work["ma3"] = work["close"].rolling(w3).mean()

    candles = []
    volumes = []
    sma50_pts = []
    sma150_pts = []
    sma200_pts = []

    for _, row in work.iterrows():
        t = str(row["date"])
        o, h, l, c, v = (
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
            float(row["volume"]),
        )
        candles.append({"time": t, "open": o, "high": h, "low": l, "close": c})
        volumes.append(
            {
                "time": t,
                "value": v,
                "color": "rgba(16, 185, 129, 0.45)" if c >= o else "rgba(239, 68, 68, 0.45)",
            }
        )
        if pd.notna(row["ma1"]):
            sma50_pts.append({"time": t, "value": round(float(row["ma1"]), 5)})
        if pd.notna(row["ma2"]):
            sma150_pts.append({"time": t, "value": round(float(row["ma2"]), 5)})
        if pd.notna(row["ma3"]):
            sma200_pts.append({"time": t, "value": round(float(row["ma3"]), 5)})

    return {
        "candles": candles,
        "volumes": volumes,
        "sma50": sma50_pts,
        "sma150": sma150_pts,
        "sma200": sma200_pts,
    }


def _resample_weekly(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])
    work = df.copy()
    work["dt"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["dt"]).set_index("dt")
    weekly = work.resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    ).dropna(subset=["open", "high", "low", "close"])
    weekly["date"] = weekly.index.strftime("%Y-%m-%d")
    return weekly.reset_index(drop=True)[["date", "open", "high", "low", "close", "volume"]]


def build_chart_payload(
    df: pd.DataFrame,
    bench_df: Optional[pd.DataFrame],
    sepa: dict[str, Any],
) -> dict[str, Any]:
    """Builds Daily & Weekly chart datasets with SMAs, RS Line, VCP contraction legs, Pivot & -6% Stop."""
    daily_series = _build_single_tf_series(df, ma_windows=(50, 150, 200))
    rs_daily, rs_new_high, rs_new_high_before_price = compute_rs_line_series(df, bench_df)

    weekly_df = _resample_weekly(df)
    weekly_bench = _resample_weekly(bench_df) if bench_df is not None and not bench_df.empty else None
    weekly_series = _build_single_tf_series(weekly_df, ma_windows=(10, 30, 40))
    rs_weekly, _, _ = compute_rs_line_series(weekly_df, weekly_bench)

    price = sepa["price"]
    stop_6pct_line = round(price * 0.94, 5)
    avwaps = compute_anchored_vwaps(df)

    return {
        # Backwards-compatible top-level daily keys
        **daily_series,
        "rs_line": rs_daily,
        "avwap_swing_low": avwaps["swing_low"],
        "avwap_ytd": avwaps["ytd"],
        "avwap_meta": {
            "swing_low_anchor_date": avwaps.get("swing_low_anchor_date"),
            "ytd_anchor_date": avwaps.get("ytd_anchor_date"),
            "above_avwap_swing": avwaps.get("above_avwap_swing"),
            "above_avwap_ytd": avwaps.get("above_avwap_ytd"),
        },
        "pocket_pivot_dates": sepa.get("quant", {}).get("pocket_pivot", {}).get("recent_dates") or [],
        "ttm_squeeze_state": sepa.get("quant", {}).get("ttm_squeeze", {}).get("state", "NEUTRO"),
        "weekly": {
            **weekly_series,
            "rs_line": rs_weekly,
        },
        "vcp_legs": sepa.get("vcp", {}).get("contraction_legs") or [],
        "rs_new_high": rs_new_high,
        "rs_new_high_before_price": rs_new_high_before_price,
        "suggested_stop_6pct": stop_6pct_line,
        "technical_stop": sepa["trade_plan"]["stop_loss_price"],
        "pivot_price": sepa["vcp"]["pivot_price"],
    }


def get_fast_chart_preview(ticker: str) -> dict[str, Any]:
    """
    Lightweight chart endpoint for instant split-screen preview inside the Scanner.
    Uses cached OHLCV directly (no slow fundamentals/news/AI calls).
    """
    norm = normalize_ticker(ticker)
    asset_type = "crypto" if is_crypto_ticker(norm) else "stock"

    # Prefer 15mo (already cached by Scanner) so switching tickers is near-instant!
    df, source, warnings = get_ohlcv(norm, period="15mo", force_refresh=False)
    if df.empty:
        df, source, warnings = get_ohlcv(norm, period="2y", force_refresh=False)
    if df.empty:
        raise ValueError(f"Sem histórico disponível para {norm}.")

    bench_ticker = "SPY" if (asset_type == "stock" or norm == "BTC-USD") else "BTC-USD"
    bench_df, _, _ = get_ohlcv(bench_ticker, period="15mo", force_refresh=False)

    sepa = analyze_sepa_vcp(
        ticker=norm,
        df=df,
        benchmark_df=bench_df if not bench_df.empty else None,
        asset_type=asset_type,
        benchmark_ticker=bench_ticker,
        fundamentals=None,
        data_source=source,
    )
    chart = build_chart_payload(df, bench_df if not bench_df.empty else None, sepa)
    trader_edge = {
        "dcr": compute_dcr_and_volume_runrate(df, ticker=norm, asset_type=asset_type),
        "mtf": compute_mtf_confluence(df, asset_type=asset_type),
    }
    return {
        "ticker": norm,
        "asset_type": asset_type,
        "data_source": source,
        "sepa": sepa,
        "trader_edge": trader_edge,
        "chart": chart,
        "warnings": warnings,
    }


def get_asset_xray(ticker: str, force_refresh: bool = False) -> dict[str, Any]:
    """
    Module 3: Instant Asset X-Ray.
    Aggregates Daily + Weekly OHLCV + SMAs + RS Line + Swing VCP + Minervini 8-Point Checklist +
    Fundamentals + RSS News with VADER Sentiment + AI Trader Briefing.
    """
    norm = normalize_ticker(ticker)
    asset_type = "crypto" if is_crypto_ticker(norm) else "stock"
    warnings: list[str] = []

    df, source, p_warn = get_ohlcv(norm, period="2y", force_refresh=force_refresh)
    warnings.extend(p_warn)

    if df.empty:
        raise ValueError(f"Ticker '{norm}' não encontrado ou sem dados históricos disponíveis.")

    bench_ticker = "SPY" if (asset_type == "stock" or norm == "BTC-USD") else "BTC-USD"
    bench_df, _, b_warn = get_ohlcv(bench_ticker, period="2y", force_refresh=False)
    if b_warn:
        warnings.append(f"Benchmark {bench_ticker} indisponível para cálculo completo de RS.")

    fundamentals, f_warn = get_fundamentals_and_earnings(norm, force_refresh=force_refresh)
    warnings.extend(f_warn)

    sepa = analyze_sepa_vcp(
        ticker=norm,
        df=df,
        benchmark_df=bench_df if not bench_df.empty else None,
        asset_type=asset_type,
        benchmark_ticker=bench_ticker,
        fundamentals=fundamentals,
        data_source=source,
    )

    news = get_asset_news(
        ticker=norm,
        company_name=fundamentals.get("name"),
        limit=12,
        force_refresh=force_refresh,
    )
    warnings.extend(news.get("warnings") or [])

    briefing = generate_trader_briefing(
        ticker=norm,
        sepa_data=sepa,
        fundamentals=fundamentals,
        news_data=news,
        force_refresh=force_refresh,
    )

    chart = build_chart_payload(df, bench_df if not bench_df.empty else None, sepa)
    volume_quality = compute_volume_quality(df)
    personality_backtest = compute_asset_personality_backtest(df)
    institutional = fetch_institutional_and_quarterly(
        norm,
        quote_type=fundamentals.get("quote_type"),
        force_refresh=force_refresh,
    )
    trader_edge = {
        "dcr": compute_dcr_and_volume_runrate(df, ticker=norm, asset_type=asset_type),
        "mtf": compute_mtf_confluence(df, asset_type=asset_type),
        "sector_peer": compute_sector_peer_rs(
            ticker=norm,
            df=df,
            sector=fundamentals.get("sector"),
            asset_type=asset_type,
        ),
        "macro_events": get_upcoming_macro_events(),
    }
    derivatives = (
        get_crypto_derivatives_for_ticker(norm, price_change_24h=sepa.get("daily_change_pct"), force_refresh=force_refresh)
        if asset_type == "crypto"
        else None
    )

    return {
        "ticker": norm,
        "asset_type": asset_type,
        "data_source": source,
        "updated_at": time.time(),
        "sepa": sepa,
        "fundamentals": fundamentals,
        "trader_edge": trader_edge,
        "volume_quality": volume_quality,
        "personality_backtest": personality_backtest,
        "institutional": institutional,
        "derivatives": derivatives,
        "news": news,
        "briefing": briefing,
        "chart": chart,
        "warnings": list(dict.fromkeys(warnings)),
    }
