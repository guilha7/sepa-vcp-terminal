from concurrent.futures import ThreadPoolExecutor, as_completed
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
from app.services.us_discovery import screen_all_us_candidates

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
    cache_only: bool = False,
) -> dict[str, Any]:
    """
    Module 2 Scanner:
    - Supports real-time progress_callback(current, total, ticker, stage) for SSE streaming
    - Supports cache_only=True for instant (<50ms) initial UI paint before SSE streaming on cold Render boots
    - Parallelized Earnings/Fundamentals enrichment (4 workers) for ~5x faster scans
    """
    global _SCAN_IN_PROGRESS

    if not force_refresh:
        cached_items, latest_ts = db.load_scan_results(asset_type=asset_type)
        if cached_items and latest_ts and (cache_only or (time.time() - latest_ts) < settings.cache_ttl_scan):
            if progress_callback:
                progress_callback(len(cached_items), len(cached_items), "CACHE", "Resultados carregados da cache SQLite")
            return _format_scan_response(cached_items, latest_ts, warnings=[], from_cache=True)
        if cache_only:
            resp = _format_scan_response([], None, warnings=[], from_cache=True)
            resp["cache_empty"] = True
            return resp

    with _SCAN_LOCK:
        # Re-check cache after acquiring lock (e.g. if background startup warm-up just finished!)
        if not force_refresh:
            cached_items, latest_ts = db.load_scan_results(asset_type=asset_type)
            if cached_items and latest_ts and (time.time() - latest_ts) < settings.cache_ttl_scan:
                if progress_callback:
                    progress_callback(len(cached_items), len(cached_items), "CACHE", "Resultados prontos da cache SQLite")
                return _format_scan_response(cached_items, latest_ts, warnings=[], from_cache=True)

        _SCAN_IN_PROGRESS = True
        try:
            watchlist = db.get_watchlist(asset_type=asset_type, only_enabled=True)
            tickers = [w["ticker"] for w in watchlist]
            type_map = {w["ticker"]: w["asset_type"] for w in watchlist}
            total = max(len(tickers), 1)

            if progress_callback:
                progress_callback(0, total, "SPY / BTC-USD", "A descarregar histórico OHLCV em lote...")

            def _on_wl_batch(done_chunks: int, total_chunks: int, label: str):
                if progress_callback:
                    pct_done = int(round((done_chunks / max(total_chunks, 1)) * (total * 0.4)))
                    progress_callback(pct_done, total, label, f"A descarregar OHLCV ({done_chunks}/{total_chunks} lotes)")

            bench_tickers = ["SPY", "BTC-USD"]
            fetch_list = list(dict.fromkeys(bench_tickers + tickers))
            dfs, sources, warnings = get_batch_ohlcv(
                fetch_list,
                period="15mo",
                force_refresh=force_refresh,
                progress_callback=_on_wl_batch,
            )
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
            ][:12]

            if priority_equities:
                if progress_callback:
                    progress_callback(
                        total,
                        total,
                        priority_equities[0]["ticker"],
                        f"A verificar Earnings & Fundamentais ({len(priority_equities)} líderes em paralelo)...",
                    )
                with ThreadPoolExecutor(max_workers=4) as pool:
                    fut_map = {
                        pool.submit(get_fundamentals_and_earnings, item["ticker"], False): item
                        for item in priority_equities
                    }
                    done_e = 0
                    for fut in as_completed(fut_map):
                        item = fut_map[fut]
                        t = item["ticker"]
                        done_e += 1
                        try:
                            fund, f_warn = fut.result()
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
                        except Exception:
                            pass
                        if progress_callback and (done_e % 3 == 0 or done_e == len(priority_equities)):
                            progress_callback(
                                total,
                                total,
                                t,
                                f"Earnings & Fundamentais ({done_e}/{len(priority_equities)})",
                            )

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


def run_us_discovery_scan(
    preset: str = "sepa_leaders",
    limit: int = 45,
    force_refresh: bool = False,
    progress_callback: Optional[ProgressFn] = None,
) -> dict[str, Any]:
    """
    2-Stage All-US / Europe / Portugal Discovery Scanner:
    Stage 1 (~1s): Pre-screen entire market (~7,000 US or Eurozone/PSI stocks) for Stage-2/momentum leaders.
    Stage 2 (~8-18s): Deep SEPA/VCP + Multi-Strategy Quant + Earnings check on the top discovered stocks.
    Results are cached 30 min per preset in SQLite without altering the admin's global watchlist.
    """
    capped_limit = max(20, min(int(limit), 100))
    cache_key = f"scan:us_discovery:{preset}:{capped_limit}"
    if not force_refresh:
        cached = db.cache_get(cache_key)
        if cached and isinstance(cached, dict):
            if progress_callback:
                progress_callback(100, 100, "CACHE", "Descoberta carregada da cache SQLite")
            cached["from_cache"] = True
            return cached

    if progress_callback:
        progress_callback(3, 100, "Fase 1", "A pré-filtrar todo o mercado selecionado...")

    stage1 = screen_all_us_candidates(preset=preset, limit=capped_limit)
    tickers = stage1["tickers"]
    meta_map = stage1.get("meta") or {}
    warnings: list[str] = list(stage1.get("warnings") or [])
    total = max(len(tickers), 1)

    if progress_callback:
        progress_callback(
            12,
            100,
            f"{stage1['total_matched_stage1']} candidatas",
            f"Fase 1 OK ({stage1['total_matched_stage1']} ações) → A descarregar Top {len(tickers)}...",
        )

    def _on_batch_progress(done_chunks: int, total_chunks: int, label: str):
        if progress_callback:
            pct = 12 + int(round((done_chunks / max(total_chunks, 1)) * 43))
            progress_callback(pct, 100, label, f"A descarregar histórico OHLCV ({done_chunks}/{total_chunks} lotes)")

    fetch_list = list(dict.fromkeys(["SPY"] + tickers))
    dfs, sources, batch_warnings = get_batch_ohlcv(
        fetch_list,
        period="15mo",
        force_refresh=False,
        progress_callback=_on_batch_progress,
    )
    warnings.extend(batch_warnings)
    spy_df = dfs.get("SPY")

    watchlist_set = {w["ticker"] for w in db.get_watchlist(only_enabled=False)}
    preliminary: list[dict[str, Any]] = []

    for idx, t in enumerate(tickers, start=1):
        if progress_callback and (idx == 1 or idx % 3 == 0 or idx == total):
            pct = 56 + int(round((idx / total) * 28))
            progress_callback(pct, 100, t, f"Fase 2: Análise SEPA/VCP/Quant ({idx}/{total})")

        df = dfs.get(t)
        if df is None or len(df) < 60:
            continue

        cached_fund = db.cache_get(f"fund:{t}")
        res = analyze_sepa_vcp(
            ticker=t,
            df=df,
            benchmark_df=spy_df,
            asset_type="stock",
            benchmark_ticker="SPY",
            fundamentals=cached_fund,
            data_source=sources.get(t, "yfinance"),
        )
        m = meta_map.get(t) or {}
        if not res.get("name") or res.get("name") == t:
            res["name"] = m.get("name") or t
        if not res.get("sector") and m.get("sector"):
            res["sector"] = m["sector"]
        res["is_new_discovery"] = t not in watchlist_set
        preliminary.append(res)

    preliminary = assign_cross_sectional_rs_ratings(preliminary)

    # Enrich top 8 highest-scoring discoveries with Earnings & Fundamentals in parallel (4 workers)
    priority = sorted(
        [r for r in preliminary if r["liquidity"]["passed"]],
        key=lambda x: x["score"],
        reverse=True,
    )[:8]
    if priority:
        if progress_callback:
            progress_callback(86, 100, priority[0]["ticker"], f"A verificar Earnings dos Top {len(priority)} em paralelo...")
        with ThreadPoolExecutor(max_workers=4) as pool:
            fut_map = {
                pool.submit(get_fundamentals_and_earnings, item["ticker"], False): item
                for item in priority
            }
            done_e = 0
            for fut in as_completed(fut_map):
                item = fut_map[fut]
                t = item["ticker"]
                done_e += 1
                try:
                    fund, f_warn = fut.result()
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
                        updated["is_new_discovery"] = item.get("is_new_discovery", True)
                        item.update(updated)
                except Exception:
                    pass
                if progress_callback:
                    pct = 86 + int(round((done_e / max(len(priority), 1)) * 12))
                    progress_callback(pct, 100, t, f"Earnings & Fundamentais ({done_e}/{len(priority)})")

    preliminary.sort(key=lambda x: x["score"], reverse=True)
    now_ts = time.time()
    response = _format_scan_response(
        preliminary,
        now_ts,
        warnings=list(dict.fromkeys(warnings))[:6],
        from_cache=False,
    )
    response["discovery_meta"] = {
        "mode": "us_all",
        "source": stage1["source"],
        "preset": stage1["preset"],
        "preset_name": stage1["preset_name"],
        "us_universe_scanned": stage1["us_universe_scanned"],
        "total_matched_stage1": stage1["total_matched_stage1"],
        "analyzed_count": len(preliminary),
        "new_outside_watchlist_count": sum(1 for r in preliminary if r.get("is_new_discovery")),
    }
    db.cache_set(cache_key, "scan", response, 1800)  # 30 min cache
    return response


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
    pocket_pivot_count = sum(1 for i in liquid_items if i.get("quant", {}).get("pocket_pivot", {}).get("detected"))
    squeeze_count = sum(
        1
        for i in liquid_items
        if i.get("quant", {}).get("ttm_squeeze", {}).get("squeeze_on")
        or i.get("quant", {}).get("ttm_squeeze", {}).get("squeeze_fire_long")
    )
    ep_count = sum(1 for i in liquid_items if i.get("quant", {}).get("episodic_pivot", {}).get("detected"))
    htf_count = sum(1 for i in liquid_items if i.get("quant", {}).get("high_tight_flag", {}).get("detected"))
    wt3_count = sum(1 for i in liquid_items if i.get("quant", {}).get("three_weeks_tight", {}).get("detected"))
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
            "pocket_pivot_count": pocket_pivot_count,
            "squeeze_count": squeeze_count,
            "ep_count": ep_count,
            "htf_count": htf_count,
            "wt3_count": wt3_count,
            "earnings_warning_count": earnings_warn_count,
        },
        "opportunities": liquid_items,
        "filtered_illiquid": [i for i in items if not i.get("liquidity", {}).get("passed", True)],
        "warnings": warnings,
    }
