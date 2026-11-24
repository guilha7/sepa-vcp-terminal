import logging
from typing import Any, Optional

import httpx

from app.config import settings
from app.database import Database, db as default_db
from app.services.market_data import get_latest_price, normalize_ticker

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Free external notification dispatcher (Telegram Bot API & Discord Webhooks)
    + Custom Price Alerts monitor + Macro Regime Shift detector.
    100% fault-tolerant: never raises into calling trading flows.
    """

    def __init__(self, database: Database = default_db):
        self.db = database

    def get_channel_config(self) -> dict[str, str]:
        tg_token = (self.db.get_state("telegram_bot_token") or settings.telegram_bot_token or "").strip()
        tg_chat = (self.db.get_state("telegram_chat_id") or settings.telegram_chat_id or "").strip()
        discord_url = (self.db.get_state("discord_webhook_url") or settings.discord_webhook_url or "").strip()
        return {
            "telegram_bot_token": tg_token,
            "telegram_chat_id": tg_chat,
            "discord_webhook_url": discord_url,
        }

    def get_channel_status(self) -> dict[str, Any]:
        cfg = self.get_channel_config()
        return {
            "telegram_configured": bool(cfg["telegram_bot_token"] and cfg["telegram_chat_id"]),
            "discord_configured": bool(cfg["discord_webhook_url"]),
            "telegram_chat_id_masked": (
                f"***{cfg['telegram_chat_id'][-4:]}" if len(cfg["telegram_chat_id"]) >= 4 else ("configurado" if cfg["telegram_chat_id"] else "")
            ),
            "discord_configured_preview": (
                cfg["discord_webhook_url"][:36] + "..." if cfg["discord_webhook_url"] else ""
            ),
        }

    def update_channels(
        self,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
    ) -> dict[str, Any]:
        if telegram_bot_token is not None:
            self.db.set_state("telegram_bot_token", telegram_bot_token.strip())
        if telegram_chat_id is not None:
            self.db.set_state("telegram_chat_id", telegram_chat_id.strip())
        if discord_webhook_url is not None:
            self.db.set_state("discord_webhook_url", discord_webhook_url.strip())
        return self.get_channel_status()

    def dispatch(
        self,
        title: str,
        message: str,
        level: str = "info",
        category: str = "SYSTEM",
        ticker: Optional[str] = None,
        persist_alert: bool = True,
    ) -> dict[str, Any]:
        """Stores in SQLite alerts table and dispatches to configured Telegram/Discord channels."""
        if persist_alert:
            self.db.add_alert(level=level, category=category, message=f"{title}: {message}", ticker=ticker)

        cfg = self.get_channel_config()
        sent = {"telegram": False, "discord": False, "errors": []}

        # Telegram Bot API (100% free)
        if cfg["telegram_bot_token"] and cfg["telegram_chat_id"]:
            icon = "🟢" if level == "success" else ("🔴" if level == "danger" else ("🟡" if level == "warning" else "🔵"))
            text = f"{icon} *{title}*\n{message}"
            url = f"https://api.telegram.org/bot{cfg['telegram_bot_token']}/sendMessage"
            try:
                with httpx.Client(timeout=6.0) as client:
                    resp = client.post(
                        url,
                        json={
                            "chat_id": cfg["telegram_chat_id"],
                            "text": text,
                            "parse_mode": "Markdown",
                            "disable_web_page_preview": True,
                        },
                    )
                    if resp.status_code == 200:
                        sent["telegram"] = True
                    else:
                        sent["errors"].append(f"Telegram HTTP {resp.status_code}")
            except Exception as exc:
                sent["errors"].append(f"Telegram: {type(exc).__name__}")
                logger.debug("Erro envio Telegram: %s", exc)

        # Discord Webhook (100% free)
        if cfg["discord_webhook_url"]:
            color_map = {"success": 0x10B981, "danger": 0xEF4444, "warning": 0xF59E0B, "info": 0x06B6D4}
            payload = {
                "username": "SEPA/VCP Terminal",
                "embeds": [
                    {
                        "title": title,
                        "description": message,
                        "color": color_map.get(level, 0x06B6D4),
                        "footer": {"text": f"Categoria: {category}" + (f" • {ticker}" if ticker else "")},
                    }
                ],
            }
            try:
                with httpx.Client(timeout=6.0) as client:
                    resp = client.post(cfg["discord_webhook_url"], json=payload)
                    if 200 <= resp.status_code < 300:
                        sent["discord"] = True
                    else:
                        sent["errors"].append(f"Discord HTTP {resp.status_code}")
            except Exception as exc:
                sent["errors"].append(f"Discord: {type(exc).__name__}")
                logger.debug("Erro envio Discord: %s", exc)

        return sent

    def check_macro_regime_shift(self, new_regime: str, label: str, score: float) -> bool:
        prev = self.db.get_state("last_macro_regime")
        self.db.set_state("last_macro_regime", new_regime)
        if prev and prev != new_regime:
            level = "success" if new_regime == "RISK_ON" else ("danger" if new_regime == "RISK_OFF" else "warning")
            self.dispatch(
                title=f"Mudança no Semáforo Macro: {prev} → {new_regime}",
                message=f"O ambiente de mercado mudou para {label} (Score {score}/100). Ajusta a exposição de risco!",
                level=level,
                category="MACRO_SHIFT",
                persist_alert=True,
            )
            return True
        return False

    def create_price_alert(self, ticker: str, condition: str, target_price: float, notes: str = "") -> dict:
        norm = normalize_ticker(ticker)
        return self.db.create_price_alert(norm, condition, target_price, notes)

    def check_price_alerts(
        self,
        price_overrides: Optional[dict[str, float]] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        active = self.db.list_price_alerts(only_active=True)
        triggered_list: list[dict[str, Any]] = []
        warnings: list[str] = []
        cache_px: dict[str, float] = dict(price_overrides or {})

        for alert in active:
            t = alert["ticker"]
            if t not in cache_px:
                px, w = get_latest_price(t, force_refresh=force_refresh)
                warnings.extend(w)
                if px is not None:
                    cache_px[t] = px

            if t not in cache_px:
                continue

            live = float(cache_px[t])
            target = float(alert["target_price"])
            cond = alert["condition"]
            hit = (cond == "ABOVE" and live >= target) or (cond == "BELOW" and live <= target)
            if hit:
                updated = self.db.trigger_price_alert(alert["id"], live)
                triggered_list.append(updated or alert)
                op_str = "acima de" if cond == "ABOVE" else "abaixo de"
                extra_note = f" | Nota: {alert['notes']}" if alert.get("notes") else ""
                self.dispatch(
                    title=f"Alerta de Preço Atingido: {t}",
                    message=f"{t} cruzou {op_str} {target} (Preço atual: {live:.4f}){extra_note}",
                    level="success" if cond == "ABOVE" else "warning",
                    category="PRICE_ALERT",
                    ticker=t,
                    persist_alert=True,
                )

        return {
            "checked": len(active),
            "triggered": triggered_list,
            "warnings": list(dict.fromkeys(warnings)),
        }


notification_service = NotificationService()
