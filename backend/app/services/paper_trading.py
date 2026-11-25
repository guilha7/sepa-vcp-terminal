import math
import time
from typing import Any, Optional

from app.config import settings
from app.database import Database, db as default_db
from app.models import PaperPositionCreate, PaperPositionJournalUpdate, PositionCalcRequest
from app.services.market_data import (
    get_eurusd_rate,
    get_latest_price,
    get_ohlcv,
    is_crypto_ticker,
    normalize_ticker,
)
from app.services.notifications import NotificationService, notification_service as default_notifier


def _resolve_fx(asset_currency: str, override: Optional[float] = None) -> tuple[float, list[str]]:
    """Returns USD-per-1-EUR rate if asset is priced in USD, or 1.0 if priced in EUR."""
    if asset_currency == "EUR":
        return 1.0, []
    if override is not None and override > 0:
        return round(float(override), 5), []
    return get_eurusd_rate(force_refresh=False)


def calculate_position(req: PositionCalcRequest) -> dict[str, Any]:
    """
    Module 5: Strict Risk Position Calculator with live EUR/USD conversion.
    Default stop-loss: 6.0%, hard absolute ceiling: 7.0%.
    Computes exact shares/coins, real EUR max loss, stop price, 2R/3R/custom targets, and R/R ratio.
    """
    stop_pct = float(req.stop_loss_pct)
    if stop_pct > settings.max_stop_loss_pct:
        raise ValueError(f"Stop-Loss ({stop_pct}%) ultrapassa o teto máximo absoluto de {settings.max_stop_loss_pct}%.")

    fx_rate, fx_warnings = _resolve_fx(req.asset_currency, req.fx_rate_override)
    entry = float(req.entry_price)  # in asset currency (USD or EUR)
    capital_eur = float(req.capital_eur)
    capital_asset_ccy = capital_eur * fx_rate  # converting EUR capital into asset currency

    stop_price = entry * (1.0 - stop_pct / 100.0)
    risk_per_unit_ccy = entry - stop_price

    if req.sizing_mode == "account_risk":
        allowed_loss_ccy = capital_asset_ccy * (float(req.risk_pct_of_account) / 100.0)
        raw_qty = allowed_loss_ccy / risk_per_unit_ccy
        max_affordable_qty = capital_asset_ccy / entry
        raw_qty = min(raw_qty, max_affordable_qty)
    else:
        raw_qty = capital_asset_ccy / entry

    if req.allow_fractional:
        quantity = round(raw_qty, 6) if entry >= 1 else round(raw_qty, 4)
    else:
        quantity = float(math.floor(raw_qty))

    position_value_ccy = quantity * entry
    position_value_eur = round(position_value_ccy / fx_rate, 2)
    max_loss_ccy = quantity * risk_per_unit_ccy
    max_loss_eur = round(max_loss_ccy / fx_rate, 2)
    max_loss_pct_of_capital = round((max_loss_eur / capital_eur * 100.0), 2) if capital_eur > 0 else 0.0

    target_2r = entry + 2.0 * risk_per_unit_ccy
    target_3r = entry + 3.0 * risk_per_unit_ccy
    profit_2r_eur = round((quantity * (target_2r - entry)) / fx_rate, 2)
    profit_3r_eur = round((quantity * (target_3r - entry)) / fx_rate, 2)

    custom_rr = None
    custom_profit_eur = None
    if req.custom_target_price is not None:
        custom_rr = round((req.custom_target_price - entry) / risk_per_unit_ccy, 2) if risk_per_unit_ccy > 0 else None
        custom_profit_eur = round((quantity * (req.custom_target_price - entry)) / fx_rate, 2)

    risk_warning = None
    if stop_pct > 6.0:
        risk_warning = (
            f"Atenção: Stop em {stop_pct:.1f}% está acima da recomendação padrão de 6.0% "
            f"(no limite de tolerância de 7.0%)."
        )

    def _rp(v: float) -> float:
        return round(v, 2) if v >= 100 else (round(v, 4) if v >= 1 else round(v, 6))

    return {
        "capital_eur": round(capital_eur, 2),
        "asset_currency": req.asset_currency,
        "fx_rate_eurusd": fx_rate,
        "entry_price": _rp(entry),
        "stop_loss_pct": round(stop_pct, 2),
        "stop_loss_price": _rp(stop_price),
        "sizing_mode": req.sizing_mode,
        "quantity": quantity,
        "position_value_eur": position_value_eur,
        "position_value_asset_ccy": round(position_value_ccy, 2),
        "max_loss_eur": max_loss_eur,
        "max_loss_pct_of_capital": max_loss_pct_of_capital,
        "target_2r_price": _rp(target_2r),
        "target_2r_profit_eur": profit_2r_eur,
        "target_3r_price": _rp(target_3r),
        "target_3r_profit_eur": profit_3r_eur,
        "risk_reward_standard": "1 : 2.0 (2R) / 1 : 3.0 (3R)",
        "custom_target_price": _rp(req.custom_target_price) if req.custom_target_price else None,
        "custom_rr_ratio": custom_rr,
        "custom_profit_eur": custom_profit_eur,
        "risk_warning": risk_warning,
        "warnings": fx_warnings,
    }


def _clean_owner(owner_name: Optional[str]) -> str:
    raw = (owner_name or "").strip()
    if not raw:
        return "default"
    return raw[:32].lower()


class PaperTradingService:
    def __init__(
        self,
        database: Database = default_db,
        notifier: Optional[NotificationService] = None,
    ):
        self.db = database
        self.notifier = notifier or (default_notifier if database is default_db else NotificationService(database))

    def open_position(self, req: PaperPositionCreate, owner_name: str = "default") -> dict[str, Any]:
        stop_pct = float(req.stop_loss_pct)
        if stop_pct > settings.max_stop_loss_pct:
            raise ValueError(f"Stop-Loss máximo absoluto permitido é {settings.max_stop_loss_pct}%.")

        owner = _clean_owner(owner_name)
        ticker = normalize_ticker(req.ticker)
        asset_type = "crypto" if (req.asset_type == "crypto" or is_crypto_ticker(ticker)) else "stock"
        fx_rate, _ = _resolve_fx(req.asset_currency, req.fx_rate_override)

        entry = float(req.entry_price)
        capital_eur = float(req.capital_eur)
        if req.quantity:
            qty = float(req.quantity)
            capital_allocated_eur = round((qty * entry) / fx_rate, 2)
        else:
            qty = round((capital_eur * fx_rate) / entry, 6)
            capital_allocated_eur = round(capital_eur, 2)

        stop_price = round(entry * (1.0 - stop_pct / 100.0), 6)
        risk = entry - stop_price
        target_2r = round(entry + 2.0 * risk, 6)
        target_3r = round(entry + 3.0 * risk, 6)
        now = time.time()

        with self.db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO paper_positions (
                    owner_name, ticker, asset_type, currency, fx_rate_eurusd,
                    entry_price, quantity, initial_quantity, capital_allocated,
                    stop_loss_pct, stop_loss_price, target_2r, target_3r,
                    current_price, exit_price, pnl_eur, realized_partial_pnl_eur, pnl_pct,
                    partial_2r_taken, breakeven_moved, auto_manage_2r, trailing_stop_mode,
                    setup_tag, journal_emotion, journal_lesson,
                    status, notes, opened_at, closed_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 0.0, 0.0, 0.0, 0, 0, ?, ?, ?, ?, ?, 'OPEN', ?, ?, NULL, ?)
                """,
                (
                    owner,
                    ticker,
                    asset_type,
                    req.asset_currency,
                    fx_rate,
                    entry,
                    qty,
                    qty,
                    capital_allocated_eur,
                    stop_pct,
                    stop_price,
                    target_2r,
                    target_3r,
                    entry,
                    1 if req.auto_manage_2r else 0,
                    req.trailing_stop_mode,
                    (req.setup_tag or "VCP").strip().upper(),
                    (req.journal_emotion or "DISCIPLINADO").strip().upper(),
                    req.journal_lesson or "",
                    req.notes or "",
                    now,
                    now,
                ),
            )
            pos_id = int(cur.lastrowid)
            row = conn.execute("SELECT * FROM paper_positions WHERE id = ?", (pos_id,)).fetchone()
            return dict(row)

    def list_positions(self, owner_name: Optional[str] = None) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            if owner_name is not None:
                owner = _clean_owner(owner_name)
                rows = conn.execute(
                    "SELECT * FROM paper_positions WHERE owner_name = ? ORDER BY opened_at DESC",
                    (owner,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM paper_positions ORDER BY opened_at DESC").fetchall()
            return [dict(r) for r in rows]

    def move_stop_to_breakeven(self, position_id: int, owner_name: Optional[str] = None) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)).fetchone()
            if not row or (owner_name is not None and row["owner_name"] != _clean_owner(owner_name)):
                raise KeyError(f"Posição #{position_id} não encontrada.")
            pos = dict(row)
            if pos["status"] != "OPEN":
                return pos
            entry = float(pos["entry_price"])
            new_stop = max(float(pos["stop_loss_price"]), entry)
            conn.execute(
                "UPDATE paper_positions SET stop_loss_price = ?, breakeven_moved = 1, updated_at = ? WHERE id = ?",
                (new_stop, time.time(), position_id),
            )
            return dict(conn.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)).fetchone())

    def update_journal(
        self,
        position_id: int,
        req: PaperPositionJournalUpdate,
        owner_name: Optional[str] = None,
    ) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)).fetchone()
            if not row or (owner_name is not None and row["owner_name"] != _clean_owner(owner_name)):
                raise KeyError(f"Posição #{position_id} não encontrada.")
            updates = []
            params: list[Any] = []
            if req.setup_tag is not None:
                updates.append("setup_tag = ?")
                params.append(req.setup_tag.strip().upper() or "VCP")
            if req.journal_emotion is not None:
                updates.append("journal_emotion = ?")
                params.append(req.journal_emotion.strip().upper() or "DISCIPLINADO")
            if req.journal_lesson is not None:
                updates.append("journal_lesson = ?")
                params.append(req.journal_lesson)
            if req.notes is not None:
                updates.append("notes = ?")
                params.append(req.notes)
            if req.auto_manage_2r is not None:
                updates.append("auto_manage_2r = ?")
                params.append(1 if req.auto_manage_2r else 0)
            if req.trailing_stop_mode is not None:
                updates.append("trailing_stop_mode = ?")
                params.append(req.trailing_stop_mode)

            if updates:
                updates.append("updated_at = ?")
                params.append(time.time())
                params.append(position_id)
                conn.execute(f"UPDATE paper_positions SET {', '.join(updates)} WHERE id = ?", params)

            return dict(conn.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)).fetchone())

    def close_position(
        self,
        position_id: int,
        exit_price: Optional[float] = None,
        status: str = "CLOSED_MANUAL",
        journal_lesson: Optional[str] = None,
        owner_name: Optional[str] = None,
    ) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)).fetchone()
            if not row or (owner_name is not None and row["owner_name"] != _clean_owner(owner_name)):
                raise KeyError(f"Posição #{position_id} não encontrada.")
            pos = dict(row)
            if pos["status"] != "OPEN":
                return pos

            fx = max(float(pos.get("fx_rate_eurusd") or 1.0), 0.1)
            px = float(exit_price) if exit_price is not None else float(pos["current_price"])
            rem_pnl_eur = ((px - float(pos["entry_price"])) * float(pos["quantity"])) / fx
            partial_pnl = float(pos.get("realized_partial_pnl_eur") or 0.0)
            total_pnl_eur = round(partial_pnl + rem_pnl_eur, 2)
            cap = float(pos["capital_allocated"])
            pnl_pct = round((total_pnl_eur / cap) * 100.0, 2) if cap > 0 else 0.0
            now = time.time()
            lesson = journal_lesson if journal_lesson is not None else pos.get("journal_lesson", "")

            conn.execute(
                """
                UPDATE paper_positions
                SET current_price = ?, exit_price = ?, pnl_eur = ?, pnl_pct = ?,
                    status = ?, journal_lesson = ?, closed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (px, px, total_pnl_eur, pnl_pct, status, lesson, now, now, position_id),
            )
            updated = conn.execute("SELECT * FROM paper_positions WHERE id = ?", (position_id,)).fetchone()
            return dict(updated)

    def delete_position(self, position_id: int, owner_name: Optional[str] = None) -> bool:
        with self.db.connect() as conn:
            if owner_name is not None:
                cur = conn.execute(
                    "DELETE FROM paper_positions WHERE id = ? AND owner_name = ?",
                    (position_id, _clean_owner(owner_name)),
                )
            else:
                cur = conn.execute("DELETE FROM paper_positions WHERE id = ?", (position_id,))
            return cur.rowcount > 0

    def _get_trailing_sma(self, ticker: str, window: int) -> Optional[float]:
        try:
            df, _, _ = get_ohlcv(ticker, period="3mo", force_refresh=False)
            if df is not None and len(df) >= window:
                return round(float(df["close"].astype(float).rolling(window).mean().iloc[-1]), 6)
        except Exception:
            pass
        return None

    def update_open_positions_with_prices(
        self,
        price_overrides: Optional[dict[str, float]] = None,
        sma_overrides: Optional[dict[str, float]] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Refreshes live P&L for OPEN paper positions with Minervini active exit rules:
        1. Auto 2R Partial Exit (50%) + automatic Breakeven Stop (0% risk)
        2. Optional Trailing Stop by SMA 10 / SMA 21 (ratchet upward only)
        3. Strict automatic Stop-Loss / Breakeven Stop closure + external Telegram/Discord alerts
        """
        warnings: list[str] = []
        triggered_stops: list[dict[str, Any]] = []
        triggered_partials: list[dict[str, Any]] = []
        pending_notifications: list[dict[str, Any]] = []
        now = time.time()

        with self.db.connect() as conn:
            open_rows = conn.execute("SELECT * FROM paper_positions WHERE status = 'OPEN'").fetchall()
            open_positions = [dict(r) for r in open_rows]

        price_cache: dict[str, float] = dict(price_overrides or {})
        sma_cache: dict[str, float] = dict(sma_overrides or {})

        for pos in open_positions:
            t = pos["ticker"]
            if t not in price_cache:
                px, w = get_latest_price(t, force_refresh=force_refresh)
                warnings.extend(w)
                if px is not None:
                    price_cache[t] = px
            tmode = pos.get("trailing_stop_mode") or "NONE"
            if tmode in ("SMA10", "SMA21") and t not in sma_cache:
                win = 10 if tmode == "SMA10" else 21
                sma_val = self._get_trailing_sma(t, win)
                if sma_val is not None:
                    sma_cache[t] = sma_val

        with self.db.connect() as conn:
            for pos in open_positions:
                t = pos["ticker"]
                if t not in price_cache:
                    continue

                live_px = float(price_cache[t])
                entry = float(pos["entry_price"])
                qty = float(pos["quantity"])
                fx = max(float(pos.get("fx_rate_eurusd") or 1.0), 0.1)
                cap = float(pos["capital_allocated"])
                stop_px = float(pos["stop_loss_price"])
                target_2r = float(pos["target_2r"])
                partial_pnl = float(pos.get("realized_partial_pnl_eur") or 0.0)
                partial_taken = int(pos.get("partial_2r_taken") or 0)
                be_moved = int(pos.get("breakeven_moved") or 0)
                auto_2r = int(pos.get("auto_manage_2r") if pos.get("auto_manage_2r") is not None else 1)
                tmode = pos.get("trailing_stop_mode") or "NONE"

                # 1. Auto 2R Partial Take-Profit (50%) + Move Stop to Breakeven!
                if auto_2r == 1 and partial_taken == 0 and live_px >= target_2r:
                    sold_qty = qty * 0.5
                    qty = round(qty - sold_qty, 6)
                    booked_eur = round(((live_px - entry) * sold_qty) / fx, 2)
                    partial_pnl = round(partial_pnl + booked_eur, 2)
                    partial_taken = 1
                    be_moved = 1
                    stop_px = max(stop_px, entry)

                    triggered_partials.append(
                        {
                            "id": pos["id"],
                            "ticker": t,
                            "price": live_px,
                            "booked_eur": booked_eur,
                            "new_stop_breakeven": stop_px,
                        }
                    )
                    msg = (
                        f"Alvo 2R atingido em {t} ({live_px:.4f})! Realizados 50% (+{booked_eur:.2f}€) "
                        f"e Stop movido automaticamente para Breakeven ({stop_px:.4f})."
                    )
                    conn.execute(
                        "INSERT INTO alerts (level, category, ticker, message, created_at, read) VALUES (?, ?, ?, ?, ?, 0)",
                        ("success", "TARGET_2R_PARTIAL", t, msg, now),
                    )
                    pending_notifications.append(
                        {"title": f"Alvo 2R + Breakeven: {t}", "message": msg, "level": "success", "category": "TARGET_2R_PARTIAL", "ticker": t}
                    )

                # 2. Trailing Stop by SMA10 / SMA21 (only ratchets stop UPWARD while in profit)
                if tmode in ("SMA10", "SMA21") and t in sma_cache and live_px > entry:
                    sma_val = float(sma_cache[t])
                    if sma_val > stop_px and sma_val < live_px:
                        stop_px = round(sma_val, 6)
                        if stop_px >= entry:
                            be_moved = 1

                # 3. Automatic Stop-Loss / Breakeven Execution
                if live_px <= stop_px:
                    exec_px = min(stop_px, live_px)
                    rem_pnl_eur = ((exec_px - entry) * qty) / fx
                    total_pnl_eur = round(partial_pnl + rem_pnl_eur, 2)
                    pnl_pct = round((total_pnl_eur / cap) * 100.0, 2) if cap > 0 else 0.0
                    close_status = "CLOSED_BE" if (be_moved == 1 and exec_px >= entry * 0.995) else "CLOSED_STOP"

                    conn.execute(
                        """
                        UPDATE paper_positions
                        SET quantity = ?, current_price = ?, exit_price = ?, stop_loss_price = ?,
                            realized_partial_pnl_eur = ?, partial_2r_taken = ?, breakeven_moved = ?,
                            pnl_eur = ?, pnl_pct = ?, status = ?, closed_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            qty, live_px, exec_px, stop_px,
                            partial_pnl, partial_taken, be_moved,
                            total_pnl_eur, pnl_pct, close_status, now, now, pos["id"],
                        ),
                    )
                    triggered_stops.append(
                        {
                            "id": pos["id"],
                            "ticker": t,
                            "stop_loss_price": stop_px,
                            "triggered_price": live_px,
                            "status": close_status,
                            "pnl_eur": total_pnl_eur,
                            "pnl_pct": pnl_pct,
                        }
                    )
                    level = "info" if close_status == "CLOSED_BE" else "danger"
                    label = "Breakeven/Trailing Stop" if close_status == "CLOSED_BE" else "Stop-Loss automático"
                    msg = (
                        f"{label} acionado em {t} (preço {live_px:.4f} <= stop {stop_px:.4f}). "
                        f"Posição fechada com {pnl_pct:+.2f}% ({total_pnl_eur:+.2f}€)."
                    )
                    conn.execute(
                        "INSERT INTO alerts (level, category, ticker, message, created_at, read) VALUES (?, ?, ?, ?, ?, 0)",
                        (level, "STOP_LOSS", t, msg, now),
                    )
                    pending_notifications.append(
                        {"title": f"{label}: {t}", "message": msg, "level": level, "category": "STOP_LOSS", "ticker": t}
                    )
                else:
                    rem_pnl_eur = ((live_px - entry) * qty) / fx
                    total_pnl_eur = round(partial_pnl + rem_pnl_eur, 2)
                    pnl_pct = round((total_pnl_eur / cap) * 100.0, 2) if cap > 0 else 0.0
                    conn.execute(
                        """
                        UPDATE paper_positions
                        SET quantity = ?, current_price = ?, stop_loss_price = ?,
                            realized_partial_pnl_eur = ?, partial_2r_taken = ?, breakeven_moved = ?,
                            pnl_eur = ?, pnl_pct = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (
                            qty, live_px, stop_px,
                            partial_pnl, partial_taken, be_moved,
                            total_pnl_eur, pnl_pct, now, pos["id"],
                        ),
                    )

        # Dispatch external Telegram/Discord pings safely OUTSIDE the SQLite transaction
        for n_item in pending_notifications:
            self.notifier.dispatch(**n_item, persist_alert=False)

        return {
            "updated_count": len(open_positions),
            "triggered_stops": triggered_stops,
            "triggered_partials": triggered_partials,
            "warnings": list(dict.fromkeys(warnings)),
        }

    def _compute_journal_stats(self, closed_pos: list[dict[str, Any]]) -> dict[str, Any]:
        by_setup: dict[str, dict[str, Any]] = {}
        by_emotion: dict[str, dict[str, Any]] = {}

        def _acc(bucket: dict[str, dict[str, Any]], key: str, pnl: float, r_mult: float):
            if key not in bucket:
                bucket[key] = {"tag": key, "trades": 0, "wins": 0, "losses": 0, "pnl_eur": 0.0, "r_sum": 0.0}
            b = bucket[key]
            b["trades"] += 1
            if pnl > 0:
                b["wins"] += 1
            else:
                b["losses"] += 1
            b["pnl_eur"] = round(b["pnl_eur"] + pnl, 2)
            b["r_sum"] += r_mult

        for p in closed_pos:
            pnl = float(p["pnl_eur"])
            risk_eur = float(p["capital_allocated"]) * (float(p["stop_loss_pct"]) / 100.0)
            r_mult = (pnl / risk_eur) if risk_eur > 0 else 0.0
            _acc(by_setup, (p.get("setup_tag") or "VCP").upper(), pnl, r_mult)
            _acc(by_emotion, (p.get("journal_emotion") or "DISCIPLINADO").upper(), pnl, r_mult)

        def _finalize(bucket: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
            out = []
            for v in bucket.values():
                t = v["trades"]
                out.append(
                    {
                        "tag": v["tag"],
                        "trades": t,
                        "wins": v["wins"],
                        "losses": v["losses"],
                        "win_rate_pct": round((v["wins"] / t) * 100.0, 1) if t else 0.0,
                        "pnl_eur": v["pnl_eur"],
                        "avg_r": round(v["r_sum"] / t, 2) if t else 0.0,
                    }
                )
            return sorted(out, key=lambda x: x["pnl_eur"], reverse=True)

        return {
            "by_setup": _finalize(by_setup),
            "by_emotion": _finalize(by_emotion),
        }

    def get_portfolio_summary(
        self,
        refresh_prices: bool = False,
        owner_name: Optional[str] = None,
        base_capital_eur: Optional[float] = None,
    ) -> dict[str, Any]:
        warnings: list[str] = []
        triggered_stops: list[dict[str, Any]] = []
        triggered_partials: list[dict[str, Any]] = []
        if refresh_prices:
            upd = self.update_open_positions_with_prices(force_refresh=True)
            warnings = upd["warnings"]
            triggered_stops = upd["triggered_stops"]
            triggered_partials = upd["triggered_partials"]

        fx_rate, fx_w = get_eurusd_rate(force_refresh=False)
        warnings.extend(fx_w)

        positions = self.list_positions(owner_name=owner_name)
        open_pos = [p for p in positions if p["status"] == "OPEN"]
        closed_pos = [p for p in positions if p["status"] != "OPEN"]

        realized_pnl = round(sum(float(p["pnl_eur"]) for p in closed_pos), 2)
        unrealized_pnl = round(sum(float(p["pnl_eur"]) for p in open_pos), 2)
        total_pnl = round(realized_pnl + unrealized_pnl, 2)
        capital_deployed = round(sum(float(p["capital_allocated"]) for p in open_pos), 2)

        wins = [p for p in closed_pos if float(p["pnl_eur"]) > 0]
        losses = [p for p in closed_pos if float(p["pnl_eur"]) <= 0]
        win_rate = round((len(wins) / len(closed_pos) * 100.0), 1) if closed_pos else 0.0

        gross_profit = sum(float(p["pnl_eur"]) for p in wins)
        gross_loss = abs(sum(float(p["pnl_eur"]) for p in losses))
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else (round(gross_profit, 2) if gross_profit > 0 else 0.0)

        base_equity = float(base_capital_eur) if (base_capital_eur is not None and base_capital_eur > 0) else float(settings.default_capital_eur)
        equity = base_equity
        peak = base_equity
        max_dd_pct = 0.0
        equity_curve = [{"label": "Início", "equity": round(equity, 2), "pnl": 0.0, "timestamp": 0}]

        for idx, p in enumerate(sorted(closed_pos, key=lambda x: x.get("closed_at") or x["opened_at"])):
            equity += float(p["pnl_eur"])
            if equity > peak:
                peak = equity
            dd = ((peak - equity) / peak * 100.0) if peak > 0 else 0.0
            max_dd_pct = max(max_dd_pct, dd)
            equity_curve.append(
                {
                    "label": f"#{idx + 1} {p['ticker']}",
                    "equity": round(equity, 2),
                    "pnl": round(float(p["pnl_eur"]), 2),
                    "timestamp": p.get("closed_at") or p["opened_at"],
                }
            )

        if open_pos:
            live_equity = equity + unrealized_pnl
            if live_equity > peak:
                peak = live_equity
            dd = ((peak - live_equity) / peak * 100.0) if peak > 0 else 0.0
            max_dd_pct = max(max_dd_pct, dd)
            equity_curve.append(
                {
                    "label": "Atual (Aberto)",
                    "equity": round(live_equity, 2),
                    "pnl": unrealized_pnl,
                    "timestamp": time.time(),
                }
            )

        r_multiples = []
        win_rs = []
        loss_rs = []
        for p in closed_pos:
            risk_eur = float(p["capital_allocated"]) * (float(p["stop_loss_pct"]) / 100.0)
            if risk_eur > 0:
                rm = float(p["pnl_eur"]) / risk_eur
                r_multiples.append(rm)
                if rm > 0:
                    win_rs.append(rm)
                else:
                    loss_rs.append(abs(rm))

        avg_r = round(sum(r_multiples) / len(r_multiples), 2) if r_multiples else 0.0
        avg_win_r = round(sum(win_rs) / len(win_rs), 2) if win_rs else 0.0
        avg_loss_r = round(sum(loss_rs) / len(loss_rs), 2) if loss_rs else 0.0

        # Van K. Tharp Expectancy & System Quality Number (SQN)
        n_r = len(r_multiples)
        win_prob = (len(win_rs) / n_r) if n_r > 0 else 0.0
        loss_prob = 1.0 - win_prob
        expectancy_r = round((win_prob * avg_win_r) - (loss_prob * avg_loss_r), 3) if n_r > 0 else 0.0

        sqn = None
        sqn_grade = "Amostra curta (< 5 trades)"
        if n_r >= 2:
            mean_r = sum(r_multiples) / n_r
            variance = sum((x - mean_r) ** 2 for x in r_multiples) / max(n_r - 1, 1)
            std_r = math.sqrt(variance)
            if std_r > 0:
                sqn = round((math.sqrt(min(n_r, 100)) * mean_r) / std_r, 2)
            elif mean_r > 0:
                sqn = 5.0
            else:
                sqn = 0.0

            if n_r < 5:
                sqn_grade = f"Preliminar ({n_r}/5 trades)"
            elif sqn >= 5.0:
                sqn_grade = "Santo Graal (≥ 5.0)"
            elif sqn >= 3.0:
                sqn_grade = "Excelente (3.0–4.9)"
            elif sqn >= 2.0:
                sqn_grade = "Bom / Profissional (2.0–2.9)"
            elif sqn >= 1.6:
                sqn_grade = "Aceitável (1.6–1.9)"
            else:
                sqn_grade = "Fraco (< 1.6 — Rever Regras)"

        # Portfolio Heat & Sector Concentration (Minervini / Van Tharp open risk monitor)
        open_risk_eur = 0.0
        be_protected_count = 0
        sector_buckets: dict[str, dict[str, Any]] = {}
        for p in open_pos:
            entry_p = float(p["entry_price"])
            stop_p = float(p["stop_loss_price"])
            qty_p = float(p["quantity"])
            fx_p = max(float(p.get("fx_rate_eurusd") or 1.0), 0.1)
            cap_p = float(p["capital_allocated"])

            # Risk to initial capital = 0€ once stop is moved to Breakeven or above entry!
            pos_risk = max(0.0, ((entry_p - stop_p) * qty_p) / fx_p)
            if pos_risk <= 0.01 or int(p.get("breakeven_moved") or 0) == 1 and stop_p >= entry_p * 0.999:
                pos_risk = 0.0
                be_protected_count += 1
            open_risk_eur += pos_risk

            if p.get("asset_type") == "crypto":
                sec_name = "Criptomoedas"
            else:
                cached_f = self.db.cache_get(f"fund:{p['ticker']}") or {}
                sec_name = (cached_f.get("sector") if isinstance(cached_f, dict) else None) or "Ações (Geral)"
            if sec_name not in sector_buckets:
                sector_buckets[sec_name] = {"sector": sec_name, "count": 0, "capital_eur": 0.0, "risk_eur": 0.0}
            sector_buckets[sec_name]["count"] += 1
            sector_buckets[sec_name]["capital_eur"] = round(sector_buckets[sec_name]["capital_eur"] + cap_p, 2)
            sector_buckets[sec_name]["risk_eur"] = round(sector_buckets[sec_name]["risk_eur"] + pos_risk, 2)

        open_risk_eur = round(open_risk_eur, 2)
        open_risk_pct = round((open_risk_eur / base_equity) * 100.0, 2) if base_equity > 0 else 0.0
        if open_risk_pct > 6.0:
            heat_level = "ALTO"
            heat_msg = f"Calor elevado ({open_risk_pct:.1f}% em risco aberto): evita abrir novas posições até protegeres stops em Breakeven."
        elif open_risk_pct > 4.0:
            heat_level = "MODERADO"
            heat_msg = f"Risco aberto moderado ({open_risk_pct:.1f}%): escolhe apenas setups A+."
        else:
            heat_level = "SEGURO"
            heat_msg = (
                "Risco aberto controlado (≤ 4% do capital base)."
                if open_pos
                else "Sem risco aberto (100% em liquidez)."
            )

        sector_exposure = []
        for b in sorted(sector_buckets.values(), key=lambda x: x["capital_eur"], reverse=True):
            pct_dep = round((b["capital_eur"] / capital_deployed) * 100.0, 1) if capital_deployed > 0 else 0.0
            sector_exposure.append({**b, "capital_pct": pct_dep})

        concentration_warning = None
        if len(open_pos) >= 2 and sector_exposure:
            top_sec = sector_exposure[0]
            if (len(open_pos) >= 3 and top_sec["capital_pct"] >= 45.0) or (
                len(open_pos) == 2 and top_sec["count"] >= 2 and top_sec["capital_pct"] >= 60.0
            ):
                concentration_warning = (
                    f"Concentração elevada: {top_sec['capital_pct']:.0f}% do capital aberto está em "
                    f"'{top_sec['sector']}' ({top_sec['count']} posições) — risco correlacionado num dia de queda."
                )

        portfolio_heat = {
            "open_risk_eur": open_risk_eur,
            "open_risk_pct": open_risk_pct,
            "breakeven_protected_count": be_protected_count,
            "open_positions_count": len(open_pos),
            "heat_level": heat_level,
            "heat_message": heat_msg,
            "sector_exposure": sector_exposure,
            "concentration_warning": concentration_warning,
        }

        return {
            "fx_rate_eurusd": fx_rate,
            "metrics": {
                "base_capital_eur": base_equity,
                "current_equity_eur": round(base_equity + total_pnl, 2),
                "capital_deployed_eur": capital_deployed,
                "total_pnl_eur": total_pnl,
                "total_pnl_pct": round((total_pnl / base_equity) * 100.0, 2) if base_equity > 0 else 0.0,
                "realized_pnl_eur": realized_pnl,
                "unrealized_pnl_eur": unrealized_pnl,
                "total_trades": len(positions),
                "open_trades": len(open_pos),
                "closed_trades": len(closed_pos),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate_pct": win_rate,
                "profit_factor": profit_factor,
                "max_drawdown_pct": round(max_dd_pct, 2),
                "avg_r_multiple": avg_r,
                "avg_win_r": avg_win_r,
                "avg_loss_r": avg_loss_r,
                "expectancy_r": expectancy_r,
                "sqn": sqn,
                "sqn_grade": sqn_grade,
                "auto_stops_count": sum(1 for p in closed_pos if p["status"] == "CLOSED_STOP"),
                "partial_2r_count": sum(1 for p in positions if int(p.get("partial_2r_taken") or 0) == 1),
            },
            "portfolio_heat": portfolio_heat,
            "journal_stats": self._compute_journal_stats(closed_pos),
            "positions": positions,
            "equity_curve": equity_curve,
            "triggered_stops": triggered_stops,
            "triggered_partials": triggered_partials,
            "alerts": self.db.list_alerts(limit=15),
            "warnings": list(dict.fromkeys(warnings)),
        }


paper_trading_service = PaperTradingService()
