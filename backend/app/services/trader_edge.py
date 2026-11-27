from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.services.market_data import get_ohlcv, is_crypto_ticker

# Mapping Yahoo Finance sector names -> liquid US Sector SPDR ETFs (already cached by Macro module)
SECTOR_TO_ETF: dict[str, tuple[str, str]] = {
    "technology": ("XLK", "Tecnologia"),
    "financial services": ("XLF", "Financeiro"),
    "financial": ("XLF", "Financeiro"),
    "healthcare": ("XLV", "Saúde"),
    "energy": ("XLE", "Energia"),
    "consumer cyclical": ("XLY", "Consumo Discricionário"),
    "consumer defensive": ("XLP", "Consumo Básico"),
    "industrials": ("XLI", "Indústria"),
    "basic materials": ("XLB", "Materiais"),
    "utilities": ("XLU", "Utilities"),
    "real estate": ("XLRE", "Imobiliário"),
    "communication services": ("XLC", "Comunicações"),
}

EU_SUFFIXES = (".LS", ".DE", ".PA", ".AS", ".MC", ".MI", ".L", ".SW", ".ST")

# Official Federal Reserve FOMC decision dates (2nd day, 14:00 ET) & US BLS CPI release dates (08:30 ET)
OFFICIAL_FOMC_DATES: list[str] = [
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-10-29", "2025-12-10",
    # 2026
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    # 2027
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-22", "2027-11-03", "2027-12-15",
]

OFFICIAL_CPI_DATES: list[str] = [
    # 2025
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10",
    "2025-05-13", "2025-06-11", "2025-07-15", "2025-08-12",
    "2025-09-11", "2025-10-15", "2025-11-13", "2025-12-10",
    # 2026
    "2026-01-13", "2026-02-11", "2026-03-11", "2026-04-10",
    "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-11", "2026-10-14", "2026-11-12", "2026-12-10",
    # 2027
    "2027-01-13", "2027-02-10", "2027-03-10", "2027-04-13",
    "2027-05-12", "2027-06-10", "2027-07-14", "2027-08-11",
    "2027-09-14", "2027-10-13", "2027-11-10", "2027-12-10",
]


def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    # Friday is weekday() == 4
    offset = (4 - d.weekday()) % 7
    res = date(year, month, 1 + offset)
    # If New Year's Day is Friday (Jan 1), BLS NFP shifts to 2nd Friday
    if month == 1 and res.day == 1:
        res = date(year, month, 8)
    return res


def get_upcoming_macro_events(
    reference_date: Optional[date] = None,
    window_days: int = 2,
) -> dict[str, Any]:
    """
    Returns high-impact US macro events (FOMC, CPI, NFP Payrolls) happening within `window_days` (default <= 48h).
    Zero network dependencies — completely silent on normal trading days.
    """
    today = reference_date or datetime.now(timezone.utc).date()
    events: list[dict[str, Any]] = []

    for ds in OFFICIAL_FOMC_DATES:
        d = date.fromisoformat(ds)
        events.append(
            {
                "date": ds,
                "code": "FOMC",
                "title": "Decisão de Juros Fed (FOMC)",
                "time_pt": "19:00 Lisboa",
                "impact": "ALTO",
                "days_away": (d - today).days,
            }
        )

    for ds in OFFICIAL_CPI_DATES:
        d = date.fromisoformat(ds)
        events.append(
            {
                "date": ds,
                "code": "CPI",
                "title": "Inflação EUA (CPI)",
                "time_pt": "13:30 Lisboa",
                "impact": "ALTO",
                "days_away": (d - today).days,
            }
        )

    # Generate NFP (Payrolls — 1st Friday of month) around current year
    for yr in (today.year, today.year + 1):
        for mo in range(1, 13):
            d = _first_friday(yr, mo)
            events.append(
                {
                    "date": d.isoformat(),
                    "code": "NFP",
                    "title": "Emprego EUA (Payrolls / NFP)",
                    "time_pt": "13:30 Lisboa",
                    "impact": "ALTO",
                    "days_away": (d - today).days,
                }
            )

    future = sorted([e for e in events if e["days_away"] >= 0], key=lambda x: (x["days_away"], x["code"]))
    within_window = [e for e in future if e["days_away"] <= window_days]

    return {
        "has_imminent_event": len(within_window) > 0,
        "upcoming_within_48h": within_window,
        "next_event": future[0] if future else None,
    }


def compute_dcr_and_volume_runrate(
    df: pd.DataFrame,
    ticker: str = "",
    asset_type: str = "stock",
    now_utc: Optional[datetime] = None,
) -> dict[str, Any]:
    """
    1. DCR% (Daily Closing Range): (Close - Low) / (High - Low) * 100
       - >= 75%: Strong institutional close at top of range (bullish follow-through)
       - < 40%: Weak close / rejection (high fakeout risk)
    2. Intraday Projected Volume Run-Rate:
       - If the latest candle belongs to today's active market session, projects full-day volume
         based on elapsed session time vs 50-day average volume.
    """
    if df is None or df.empty:
        return {
            "available": False,
            "dcr_pct": None,
            "dcr_state": "N/D",
            "dcr_label": "Indisponível",
            "volume_ratio": None,
            "projected_volume_ratio": None,
            "is_intraday_projected": False,
        }

    last = df.iloc[-1]
    h = float(last["high"])
    l = float(last["low"])
    c = float(last["close"])
    v = float(last["volume"])
    last_date_str = str(last["date"])[:10]

    dcr_pct = round(((c - l) / (h - l)) * 100.0, 1) if h > l else 50.0
    dcr_pct = float(np.clip(dcr_pct, 0.0, 100.0))

    if dcr_pct >= 75.0:
        dcr_state, dcr_label = "FORTE", "Fecho no Topo"
    elif dcr_pct >= 40.0:
        dcr_state, dcr_label = "NEUTRO", "Fecho Intermédio"
    else:
        dcr_state, dcr_label = "FRACO", "Fecho Fraco (Risco Fakeout)"

    vols = df["volume"].astype(float)
    # Exclude today's partial candle from the 50-day average baseline when possible
    baseline_vols = vols.iloc[:-1].tail(50) if len(vols) >= 15 else vols.tail(50)
    avg_vol = float(baseline_vols.mean()) if len(baseline_vols) > 0 else 0.0
    vol_ratio = round(v / avg_vol, 2) if avg_vol > 0 else None

    # Intraday session projection (Run-Rate)
    now = now_utc or datetime.now(timezone.utc)
    is_projected = False
    projected_ratio = vol_ratio

    try:
        tk_up = (ticker or "").upper()
        if asset_type == "crypto" or is_crypto_ticker(tk_up):
            if last_date_str == now.strftime("%Y-%m-%d"):
                elapsed_min = now.hour * 60 + now.minute
                if 30 <= elapsed_min <= 1410 and avg_vol > 0:
                    frac = elapsed_min / 1440.0
                    projected_ratio = round((v / frac) / avg_vol, 2)
                    is_projected = True
        elif tk_up.endswith(EU_SUFFIXES):
            cet = now.astimezone(ZoneInfo("Europe/Berlin"))
            if cet.weekday() < 5 and last_date_str == cet.strftime("%Y-%m-%d"):
                mins_from_open = (cet.hour * 60 + cet.minute) - (9 * 60)
                if 15 <= mins_from_open <= 500 and avg_vol > 0:
                    frac = mins_from_open / 510.0
                    projected_ratio = round((v / frac) / avg_vol, 2)
                    is_projected = True
        else:
            ny = now.astimezone(ZoneInfo("America/New_York"))
            if ny.weekday() < 5 and last_date_str == ny.strftime("%Y-%m-%d"):
                mins_from_open = (ny.hour * 60 + ny.minute) - (9 * 60 + 30)
                if 15 <= mins_from_open <= 385 and avg_vol > 0:
                    frac = mins_from_open / 390.0
                    projected_ratio = round((v / frac) / avg_vol, 2)
                    is_projected = True
    except Exception:
        pass

    return {
        "available": True,
        "dcr_pct": dcr_pct,
        "dcr_state": dcr_state,
        "dcr_label": dcr_label,
        "volume_ratio": vol_ratio,
        "projected_volume_ratio": projected_ratio,
        "is_intraday_projected": is_projected,
    }


def compute_mtf_confluence(df: pd.DataFrame, asset_type: str = "stock") -> dict[str, Any]:
    """
    Multi-Timeframe (Weekly + Daily) Alignment Check:
    Resamples daily OHLCV to Weekly (W-FRI) and evaluates whether Weekly trend supports Daily setups
    and whether the asset is already overextended above its 10-week SMA.
    """
    if df is None or len(df) < 60:
        return {
            "available": False,
            "state": "N/D",
            "label": "Histórico curto",
            "dist_10w_pct": None,
            "weekly_above_10w": None,
            "weekly_above_30w": None,
        }

    work = df.copy()
    work["dt"] = pd.to_datetime(work["date"], errors="coerce")
    work = work.dropna(subset=["dt"]).set_index("dt")
    weekly = work.resample("W-FRI").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    ).dropna(subset=["close"])

    if len(weekly) < 12:
        return {
            "available": False,
            "state": "N/D",
            "label": "Histórico semanal curto",
            "dist_10w_pct": None,
            "weekly_above_10w": None,
            "weekly_above_30w": None,
        }

    w_close = weekly["close"].astype(float)
    w_sma10 = w_close.rolling(10).mean()
    w_sma30 = w_close.rolling(30).mean() if len(w_close) >= 30 else None

    cur = float(w_close.iloc[-1])
    sma10_val = float(w_sma10.iloc[-1]) if pd.notna(w_sma10.iloc[-1]) else None
    sma30_val = float(w_sma30.iloc[-1]) if (w_sma30 is not None and pd.notna(w_sma30.iloc[-1])) else None
    sma30_prev = float(w_sma30.iloc[-5]) if (w_sma30 is not None and len(w_sma30) >= 35 and pd.notna(w_sma30.iloc[-5])) else sma30_val

    above_10w = bool(sma10_val and cur > sma10_val)
    above_30w = bool(sma30_val is None or cur > sma30_val)
    rising_30w = bool(sma30_val is None or sma30_prev is None or sma30_val >= sma30_prev * 0.995)

    dist_10w_pct = round(((cur - sma10_val) / sma10_val) * 100.0, 1) if (sma10_val and sma10_val > 0) else None
    ext_limit = 25.0 if asset_type == "crypto" else 15.0
    weekly_overextended = bool(dist_10w_pct is not None and dist_10w_pct > ext_limit)

    d_close = df["close"].astype(float)
    d_sma50 = float(d_close.rolling(50).mean().iloc[-1]) if len(d_close) >= 50 else cur
    daily_bull = float(d_close.iloc[-1]) > d_sma50
    weekly_bull = above_10w and above_30w and rising_30w

    if weekly_bull and daily_bull:
        if weekly_overextended:
            state = "ESTICADO_SEMANAL"
            label = f"Esticado no Semanal (+{dist_10w_pct:.1f}% da 10w)"
        else:
            state = "ALINHADO"
            label = "Semanal + Diário Alinhados ✓"
    elif not weekly_bull and not daily_bull:
        state = "BAIXA"
        label = "Tendência de Baixa (Semanal & Diário)"
    else:
        state = "CONFLITO_SEMANAL"
        label = "Conflito Semanal vs. Diário"

    return {
        "available": True,
        "state": state,
        "label": label,
        "dist_10w_pct": dist_10w_pct,
        "weekly_above_10w": above_10w,
        "weekly_above_30w": above_30w,
        "weekly_overextended": weekly_overextended,
    }


def compute_sector_peer_rs(
    ticker: str,
    df: pd.DataFrame,
    sector: Optional[str],
    asset_type: str = "stock",
) -> dict[str, Any]:
    """
    Compares the stock directly against its own US Sector ETF (e.g. NVDA vs XLK over 1M & 3M)
    to tell the trader instantly if this stock is a TRUE sector leader or a laggard.
    Uses cached OHLCV (zero extra latency when Macro Rotation cache is warm).
    """
    if asset_type == "crypto" or not sector or df is None or len(df) < 65:
        return {"available": False}

    sec_info = SECTOR_TO_ETF.get(sector.strip().lower())
    if not sec_info:
        return {"available": False}

    etf_ticker, sector_pt = sec_info
    if (ticker or "").strip().upper() == etf_ticker:
        return {"available": False}

    etf_df, _, _ = get_ohlcv(etf_ticker, period="15mo", force_refresh=False)
    if etf_df is None or len(etf_df) < 65:
        return {"available": False}

    def _ret(frame: pd.DataFrame, days: int) -> Optional[float]:
        if len(frame) <= days:
            return None
        c1 = float(frame["close"].iloc[-1])
        c0 = float(frame["close"].iloc[-(days + 1)])
        return round(((c1 - c0) / c0) * 100.0, 2) if c0 > 0 else None

    a_3m = _ret(df, 63)
    e_3m = _ret(etf_df, 63)
    a_1m = _ret(df, 21)
    e_1m = _ret(etf_df, 21)

    if a_3m is None or e_3m is None:
        return {"available": False}

    diff_3m = round(a_3m - e_3m, 2)
    diff_1m = round(a_1m - e_1m, 2) if (a_1m is not None and e_1m is not None) else None

    if diff_3m >= 3.0 and (diff_1m is None or diff_1m >= -2.0):
        status = "LIDER_SETOR"
        label = f"Líder do Setor ({diff_3m:+.1f}% vs {etf_ticker} em 3M)"
    elif diff_3m <= -3.0:
        status = "ATRASADO_SETOR"
        label = f"Abaixo do Setor ({diff_3m:+.1f}% vs {etf_ticker} em 3M)"
    else:
        status = "EM_LINHA"
        label = f"Em linha com {etf_ticker} ({diff_3m:+.1f}% em 3M)"

    return {
        "available": True,
        "sector_etf": etf_ticker,
        "sector_name_pt": sector_pt,
        "asset_return_3m": a_3m,
        "sector_return_3m": e_3m,
        "outperformance_3m_pct": diff_3m,
        "outperformance_1m_pct": diff_1m,
        "status": status,
        "label": label,
    }
