import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from app.config import DEFAULT_CRYPTO_UNIVERSE, DEFAULT_STOCK_UNIVERSE, settings

_DB_LOCK = threading.RLock()


class Database:
    """Thread-safe SQLite storage for TTL cache, scans, watchlists, paper trading, alerts, and vision history."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else settings.resolved_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connect(self):
        with _DB_LOCK:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA synchronous=NORMAL;")
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    fetched_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at);

                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL CHECK(asset_type IN ('stock', 'crypto')),
                    enabled INTEGER NOT NULL DEFAULT 1,
                    added_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS scan_results (
                    ticker TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    score REAL NOT NULL,
                    stage2_passed INTEGER NOT NULL,
                    vcp_detected INTEGER NOT NULL,
                    breakout_signal INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    scanned_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_scan_score ON scan_results(score DESC);

                CREATE TABLE IF NOT EXISTS paper_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    asset_type TEXT NOT NULL DEFAULT 'stock',
                    entry_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    capital_allocated REAL NOT NULL,
                    stop_loss_pct REAL NOT NULL,
                    stop_loss_price REAL NOT NULL,
                    target_2r REAL NOT NULL,
                    target_3r REAL NOT NULL,
                    current_price REAL NOT NULL,
                    exit_price REAL,
                    pnl_eur REAL NOT NULL DEFAULT 0.0,
                    pnl_pct REAL NOT NULL DEFAULT 0.0,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    notes TEXT DEFAULT '',
                    opened_at REAL NOT NULL,
                    closed_at REAL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_paper_status ON paper_positions(status);

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    level TEXT NOT NULL,
                    category TEXT NOT NULL,
                    ticker TEXT,
                    message TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    read INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS vision_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT,
                    provider TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    condition TEXT NOT NULL CHECK(condition IN ('ABOVE', 'BELOW')),
                    target_price REAL NOT NULL,
                    notes TEXT DEFAULT '',
                    active INTEGER NOT NULL DEFAULT 1,
                    triggered INTEGER NOT NULL DEFAULT 0,
                    triggered_price REAL,
                    triggered_at REAL,
                    created_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_price_alerts_active ON price_alerts(active, triggered);

                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at REAL NOT NULL
                );
                """
            )

            # Safe incremental migrations for paper_positions (FX, auto 2R/BE, trailing, journal)
            existing_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(paper_positions)").fetchall()
            }
            migrations = [
                ("currency", "TEXT NOT NULL DEFAULT 'USD'"),
                ("fx_rate_eurusd", "REAL NOT NULL DEFAULT 1.0"),
                ("initial_quantity", "REAL"),
                ("realized_partial_pnl_eur", "REAL NOT NULL DEFAULT 0.0"),
                ("partial_2r_taken", "INTEGER NOT NULL DEFAULT 0"),
                ("breakeven_moved", "INTEGER NOT NULL DEFAULT 0"),
                ("auto_manage_2r", "INTEGER NOT NULL DEFAULT 1"),
                ("trailing_stop_mode", "TEXT NOT NULL DEFAULT 'NONE'"),
                ("setup_tag", "TEXT NOT NULL DEFAULT 'VCP'"),
                ("journal_emotion", "TEXT NOT NULL DEFAULT 'DISCIPLINADO'"),
                ("journal_lesson", "TEXT NOT NULL DEFAULT ''"),
            ]
            for col_name, col_def in migrations:
                if col_name not in existing_cols:
                    conn.execute(f"ALTER TABLE paper_positions ADD COLUMN {col_name} {col_def}")

            # Seed default watchlist if empty
            count = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()[0]
            if count == 0:
                now = time.time()
                rows = [(t, "stock", 1, now) for t in DEFAULT_STOCK_UNIVERSE] + [
                    (t, "crypto", 1, now) for t in DEFAULT_CRYPTO_UNIVERSE
                ]
                conn.executemany(
                    "INSERT OR IGNORE INTO watchlist (ticker, asset_type, enabled, added_at) VALUES (?, ?, ?, ?)",
                    rows,
                )

    # --- Cache Operations ---
    def cache_get(self, key: str, allow_stale: bool = False) -> Optional[Any]:
        now = time.time()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            if not allow_stale and row["expires_at"] < now:
                return None
            try:
                return json.loads(row["payload"])
            except json.JSONDecodeError:
                return None

    def cache_get_with_meta(self, key: str) -> Optional[dict]:
        now = time.time()
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload, fetched_at, expires_at FROM cache_entries WHERE key = ?",
                (key,),
            ).fetchone()
            if not row:
                return None
            try:
                return {
                    "data": json.loads(row["payload"]),
                    "fetched_at": row["fetched_at"],
                    "expires_at": row["expires_at"],
                    "is_stale": row["expires_at"] < now,
                }
            except json.JSONDecodeError:
                return None

    def cache_set(self, key: str, category: str, value: Any, ttl_seconds: int) -> None:
        now = time.time()
        payload = json.dumps(value, default=str)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO cache_entries (key, category, payload, fetched_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    category = excluded.category,
                    payload = excluded.payload,
                    fetched_at = excluded.fetched_at,
                    expires_at = excluded.expires_at
                """,
                (key, category, payload, now, now + ttl_seconds),
            )

    def cache_purge_expired(self) -> int:
        now = time.time()
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM cache_entries WHERE expires_at < ?", (now - 86400,))
            return cur.rowcount

    def cache_clear(self, category: Optional[str] = None) -> int:
        with self.connect() as conn:
            if category and category != "all":
                if category == "scan":
                    cur = conn.execute("DELETE FROM scan_results")
                    return cur.rowcount
                cur = conn.execute("DELETE FROM cache_entries WHERE category = ?", (category,))
                return cur.rowcount
            c1 = conn.execute("DELETE FROM cache_entries").rowcount
            c2 = conn.execute("DELETE FROM scan_results").rowcount
            return c1 + c2

    def get_storage_stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM cache_entries GROUP BY category"
            ).fetchall()
            by_cat = {r["category"]: int(r["cnt"]) for r in rows}
            scan_cnt = int(conn.execute("SELECT COUNT(*) FROM scan_results").fetchone()[0])
            paper_cnt = int(conn.execute("SELECT COUNT(*) FROM paper_positions").fetchone()[0])
            alerts_cnt = int(conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0])
            wl_cnt = int(conn.execute("SELECT COUNT(*) FROM watchlist WHERE enabled = 1").fetchone()[0])
        size_kb = round(self.db_path.stat().st_size / 1024.0, 1) if self.db_path.exists() else 0.0
        return {
            "db_path": str(self.db_path),
            "db_size_kb": size_kb,
            "cache_by_category": by_cat,
            "cache_total": sum(by_cat.values()),
            "scan_snapshots": scan_cnt,
            "paper_positions": paper_cnt,
            "alerts_count": alerts_cnt,
            "watchlist_active": wl_cnt,
        }

    # --- Watchlist Operations ---
    def get_watchlist(self, asset_type: Optional[str] = None, only_enabled: bool = True) -> list[dict]:
        query = "SELECT ticker, asset_type, enabled, added_at FROM watchlist WHERE 1=1"
        params: list[Any] = []
        if asset_type in ("stock", "crypto"):
            query += " AND asset_type = ?"
            params.append(asset_type)
        if only_enabled:
            query += " AND enabled = 1"
        query += " ORDER BY asset_type ASC, ticker ASC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def upsert_watchlist_ticker(self, ticker: str, asset_type: str, enabled: bool = True) -> None:
        t = ticker.strip().upper()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO watchlist (ticker, asset_type, enabled, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET asset_type = excluded.asset_type, enabled = excluded.enabled
                """,
                (t, asset_type, 1 if enabled else 0, time.time()),
            )

    def delete_watchlist_ticker(self, ticker: str) -> bool:
        t = ticker.strip().upper()
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM watchlist WHERE ticker = ?", (t,))
            return cur.rowcount > 0

    # --- Scan Results Operations ---
    def save_scan_results(self, items: list[dict], replace_asset_type: Optional[str] = None) -> None:
        now = time.time()
        with self.connect() as conn:
            if replace_asset_type in ("stock", "crypto"):
                conn.execute("DELETE FROM scan_results WHERE asset_type = ?", (replace_asset_type,))
            elif replace_asset_type == "all":
                conn.execute("DELETE FROM scan_results")

            for item in items:
                conn.execute(
                    """
                    INSERT INTO scan_results (
                        ticker, asset_type, score, stage2_passed, vcp_detected,
                        breakout_signal, status, payload, scanned_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET
                        asset_type = excluded.asset_type,
                        score = excluded.score,
                        stage2_passed = excluded.stage2_passed,
                        vcp_detected = excluded.vcp_detected,
                        breakout_signal = excluded.breakout_signal,
                        status = excluded.status,
                        payload = excluded.payload,
                        scanned_at = excluded.scanned_at
                    """,
                    (
                        item["ticker"],
                        item["asset_type"],
                        float(item.get("score", 0.0)),
                        1 if item.get("trend_template", {}).get("passed") else 0,
                        1 if item.get("vcp", {}).get("detected") else 0,
                        1 if item.get("vcp", {}).get("breakout_signal") else 0,
                        item.get("status", "STAGE_OTHER"),
                        json.dumps(item, default=str),
                        now,
                    ),
                )

    def load_scan_results(self, asset_type: Optional[str] = None) -> tuple[list[dict], Optional[float]]:
        query = "SELECT payload, scanned_at FROM scan_results"
        params: list[Any] = []
        if asset_type in ("stock", "crypto"):
            query += " WHERE asset_type = ?"
            params.append(asset_type)
        query += " ORDER BY score DESC"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
            if not rows:
                return [], None
            items = [json.loads(r["payload"]) for r in rows]
            latest = max(r["scanned_at"] for r in rows)
            return items, latest

    # --- Alerts Operations ---
    def add_alert(self, level: str, category: str, message: str, ticker: Optional[str] = None) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO alerts (level, category, ticker, message, created_at, read) VALUES (?, ?, ?, ?, ?, 0)",
                (level, category, ticker, message, time.time()),
            )
            return int(cur.lastrowid)

    def list_alerts(self, limit: int = 30) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def count_unread_alerts(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM alerts WHERE read = 0").fetchone()[0])

    def mark_all_alerts_read(self) -> int:
        with self.connect() as conn:
            cur = conn.execute("UPDATE alerts SET read = 1 WHERE read = 0")
            return cur.rowcount

    # --- Custom Price Alerts ---
    def create_price_alert(self, ticker: str, condition: str, target_price: float, notes: str = "") -> dict:
        now = time.time()
        t = ticker.strip().upper()
        with self.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO price_alerts (ticker, condition, target_price, notes, active, triggered, created_at)
                VALUES (?, ?, ?, ?, 1, 0, ?)
                """,
                (t, condition, float(target_price), notes or "", now),
            )
            row = conn.execute("SELECT * FROM price_alerts WHERE id = ?", (cur.lastrowid,)).fetchone()
            return dict(row)

    def list_price_alerts(self, only_active: bool = False) -> list[dict]:
        q = "SELECT * FROM price_alerts"
        if only_active:
            q += " WHERE active = 1 AND triggered = 0"
        q += " ORDER BY active DESC, triggered ASC, created_at DESC"
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(q).fetchall()]

    def trigger_price_alert(self, alert_id: int, live_price: float) -> Optional[dict]:
        now = time.time()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE price_alerts
                SET active = 0, triggered = 1, triggered_price = ?, triggered_at = ?
                WHERE id = ?
                """,
                (float(live_price), now, alert_id),
            )
            row = conn.execute("SELECT * FROM price_alerts WHERE id = ?", (alert_id,)).fetchone()
            return dict(row) if row else None

    def delete_price_alert(self, alert_id: int) -> bool:
        with self.connect() as conn:
            cur = conn.execute("DELETE FROM price_alerts WHERE id = ?", (alert_id,))
            return cur.rowcount > 0

    # --- Key-Value App State (Macro regime tracking, runtime alert channels) ---
    def get_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.connect() as conn:
            row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else default

    def set_state(self, key: str, value: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO app_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, time.time()),
            )

    # --- Vision History ---
    def save_vision_report(self, ticker: Optional[str], provider: str, report: dict) -> int:
        with self.connect() as conn:
            cur = conn.execute(
                "INSERT INTO vision_history (ticker, provider, report_json, created_at) VALUES (?, ?, ?, ?)",
                (ticker.upper() if ticker else None, provider, json.dumps(report, default=str), time.time()),
            )
            return int(cur.lastrowid)

    def list_vision_history(self, limit: int = 10) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT id, ticker, provider, report_json, created_at FROM vision_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            result = []
            for r in rows:
                result.append(
                    {
                        "id": r["id"],
                        "ticker": r["ticker"],
                        "provider": r["provider"],
                        "report": json.loads(r["report_json"]),
                        "created_at": r["created_at"],
                    }
                )
            return result


db = Database()
