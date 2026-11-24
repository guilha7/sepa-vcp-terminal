import logging
import threading
import time
from typing import Any, Callable, Optional

from app.config import settings
from app.database import db
from app.services.market_data import (
    get_batch_ohlcv,
    get_fundamentals_and_earnings,
    is_crypto_ticker,
)
from app.services.minervini_vcp import analyze_sepa_vcp, assign_cross_sectional_rs_ratings
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

_SCAN_LOCK = threading.Lock()
_SCAN_IN_PROGRESS = False

ProgressFn = Callable[[int, int, str, str], None]


def is_scan_running() -> bool:
    return _SCAN_IN_PROGRESS


def run_sepa_vcp_scan(
    asset_type: Optional[str] = None,
    force_refresh: bool = False,
    progress_callback: Optional[ProgressFn] = None,
) -> dict[str, Any]:
    """
    Module 2 Scanner:
    - Supports real-time progress_callback(current, total, ticker, stage) for SSE streaming
    - Applies 8 Minervini Trend Template rules, Real-Swing VCP detector, RS New High Before Price, Liquidity filter
    - Fetches 24h-cached earnings/fundamentals for high-scoring equity candidates
    - Dispatches Telegram/Discord alerts for high-conviction VCP breakouts (>= 1.5x vol)
    """
    global _SCAN_IN_PROGRESS

    if not force_refresh:
        cached_items, latest_ts = db.load_scan_results(asset_type=asset_type)
        if cached_items and latest_ts and (time.time() - latest_ts) < settings.cache_ttl_scan:
            if progress_callback:
                progress_callback(len(cached_items), len(cached_items), "CACHE", "Resultados carregados da cache SQLite")
            return _format_scan_response(cached_items, latest_ts, warnings=[], from_cache=True)

    with _SCAN_LOCK:
        _SCAN_IN_PROGRESS = True
        try:
            watchlist = db.get_watchlist(asset_type=asset_type, only_enabled=True)
            tickers = [w["ticker"] for w in watchlist]
            type_map = {w["ticker"]: w["asset_type"] for w in watchlist}
            total = max(len(tickers), 1)

            if progress_callback:
                progress_callback(0, total, "SPY / BTC-USD", "A descarregar histórico OHLCV em lote...")

            bench_tickers = ["SPY", "BTC-USD"]
            fetch_list = list(dict.fromkeys(bench_tickers + tickers))
            dfs, sources, warnings = get_batch_ohlcv(fetch_list, period="15mo", force_refresh=force_refresh)
            spy_df = dfs.get("SPY")
            btc_df = dfs.get("BTC-USD")

            preliminary: list[dict[str, Any]] = []
            for idx, t in enumerate(tickers, start=1):
                if progress_callback and (idx == 1 or idx % 3 == 0 or idx == total):
                    progress_callback(idx, total, t, f"A avaliar SEPA & VCP ({idx}/{total})")

                df = dfs.get(t)
                if df is None or len(df) < 60:
                    continue
                atype = type_map.get(t, "crypto" if is_crypto_ticker(t) else "stock")
                if atype == "crypto":
                    bench_df = spy_df if t == "BTC-USD" else btc_df
                    bench_name = "SPY" if t == "BTC-USD" else "BTC-USD"
                else:
                    bench_df = spy_df
                    bench_name = "SPY"

                cached_fund = db.cache_get(f"fund:{t}")
                res = analyze_sepa_vcp(
                    ticker=t,
                    df=df,
                    benchmark_df=bench_df,
                    asset_type=atype,
                    benchmark_ticker=bench_name,
                    fundamentals=cached_fund,
                    data_source=sources.get(t, "yfinance"),
                )
                preliminary.append(res)

            preliminary = assign_cross_sectional_rs_ratings(preliminary)

            equity_candidates = sorted(
                [r for r in preliminary if r["asset_type"] == "stock" and r["liquidity"]["passed"]],
                key=lambda x: x["score"],
                reverse=True,
            )
            priority_equities = [
                r for r in equity_candidates
                if r["trend_template"]["passed"] or r["score"] >= 58.0
            ][:25]

            for e_idx, item in enumerate(priority_equities, start=1):
                t = item["ticker"]
                if progress_callback:
                    progress_callback(
                        total,
                        total,
                        t,
                        f"A verificar Earnings & Fundamentais ({e_idx}/{len(priority_equities)})",
                    )
                fund, f_warn = get_fundamentals_and_earnings(t, force_refresh=False)
                if f_warn:
                    warnings.extend(f_warn[:1])
                df = dfs.get(t)
                if df is not None:
                    updated = analyze_sepa_vcp(
                        ticker=t,
                        df=df,
                        benchmark_df=spy_df,
                        asset_type="stock",
                        benchmark_ticker="SPY",
                        fundamentals=fund,
                        data_source=sources.get(t, "yfinance"),
                    )
                    updated["trend_template"]["relative_strength"]["rs_rating"] = item["trend_template"]["relative_strength"]["rs_rating"]
                    item.update(updated)

            preliminary.sort(key=lambda x: x["score"], reverse=True)

            replace_scope = asset_type if asset_type in ("stock", "crypto") else "all"
            db.save_scan_results(preliminary, replace_asset_type=replace_scope)

            # Dispatch external + SQLite alerts for top Breakouts
            for top in preliminary[:5]:
                if top["status"] == "BREAKOUT" and top["liquidity"]["passed"]:
                    notification_service.dispatch(
                        title=f"Breakout VCP Detetado: {top['ticker']}",
                        message=(
                            f"Score {top['score']}/100 | Pivô {top['trade_plan']['entry_pivot']} | "
                            f"Stop -{top['trade_plan']['stop_loss_pct']}% ({top['trade_plan']['stop_loss_price']}) | "
                            f"Vol {top['vcp']['breakout_volume_ratio']}x"
                        ),
                        level="success",
                        category="BREAKOUT",
                        ticker=top["ticker"],
                        persist_alert=True,
                    )

            now_ts = time.time()
            return _format_scan_response(preliminary, now_ts, warnings=list(dict.fromkeys(warnings))[:6], from_cache=False)
        finally:
            _SCAN_IN_PROGRESS = False


def _format_scan_response(
    items: list[dict[str, Any]],
    scanned_at: Optional[float],
    warnings: list[str],
    from_cache: bool,
) -> dict[str, Any]:
    liquid_items = [i for i in items if i.get("liquidity", {}).get("passed", True)]
    illiquid_count = len(items) - len(liquid_items)
    stage2_count = sum(1 for i in liquid_items if i.get("trend_template", {}).get("passed"))
    vcp_count = sum(1 for i in liquid_items if i.get("vcp", {}).get("detected"))
    breakout_count = sum(1 for i in liquid_items if i.get("status") == "BREAKOUT")
    rs_nh_count = sum(
        1 for i in liquid_items if i.get("trend_template", {}).get("relative_strength", {}).get("rs_new_high_before_price")
    )
    earnings_warn_count = sum(1 for i in liquid_items if i.get("earnings_within_14d"))

    return {
        "scanned_at": scanned_at,
        "from_cache": from_cache,
        "scan_in_progress": _SCAN_IN_PROGRESS,
        "summary": {
            "total_scanned": len(items),
            "liquid_count": len(liquid_items),
            "illiquid_filtered": illiquid_count,
            "stage2_count": stage2_count,
            "vcp_count": vcp_count,
            "breakout_count": breakout_count,
            "rs_new_high_count": rs_nh_count,
            "earnings_warning_count": earnings_warn_count,
        },
        "opportunities": liquid_items,
        "filtered_illiquid": [i for i in items if not i.get("liquidity", {}).get("passed", True)],
        "warnings": warnings,
    }
