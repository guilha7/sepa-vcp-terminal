import json
from fastapi import APIRouter, HTTPException

from app.config import PROJECT_ROOT
from app.database import db
from app.models import AlertChannelsUpdate, PriceAlertCreate
from app.services.notifications import notification_service

router = APIRouter(prefix="/api/alerts", tags=["Alertas & Notificações"])


@router.get("")
def get_alerts_overview(limit: int = 30):
    return {
        "alerts": db.list_alerts(limit=min(max(limit, 1), 100)),
        "unread_count": db.count_unread_alerts(),
        "price_alerts": db.list_price_alerts(only_active=False),
        "channels": notification_service.get_channel_status(),
    }


@router.post("/read-all")
def mark_alerts_read():
    count = db.mark_all_alerts_read()
    return {"status": "ok", "marked_read": count}


@router.post("/price")
def create_price_alert(payload: PriceAlertCreate):
    alert = notification_service.create_price_alert(
        ticker=payload.ticker,
        condition=payload.condition,
        target_price=payload.target_price,
        notes=payload.notes,
    )
    return {"status": "created", "alert": alert}


@router.delete("/price/{alert_id}")
def delete_price_alert(alert_id: int):
    ok = db.delete_price_alert(alert_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Alerta de preço #{alert_id} não encontrado.")
    return {"status": "deleted", "id": alert_id}


@router.post("/price/check")
def check_price_alerts_now():
    return notification_service.check_price_alerts(force_refresh=True)


@router.post("/channels")
def update_notification_channels(payload: AlertChannelsUpdate):
    status = notification_service.update_channels(
        telegram_bot_token=payload.telegram_bot_token,
        telegram_chat_id=payload.telegram_chat_id,
        discord_webhook_url=payload.discord_webhook_url,
    )
    return {"status": "updated", "channels": status}


@router.post("/test")
def test_notification_channels():
    sent = notification_service.dispatch(
        title="Teste de Ligação — SEPA/VCP Terminal",
        message="As notificações gratuitas (Telegram / Discord) estão ativas e prontas para alertar breakouts, stops e mudanças macro!",
        level="success",
        category="TEST",
        persist_alert=True,
    )
    return {"status": "sent", "delivery": sent, "channels": notification_service.get_channel_status()}


@router.post("/send-morning-briefing")
def send_morning_briefing_now():
    """Sends the rich Morning Briefing (Macro + IBD + Breadth + Leaders + Crypto + Top Setups) to Telegram/Discord."""
    from app.services.macro_rotation import compute_macro_and_rotation
    from app.services.scanner_service import run_sepa_vcp_scan
    from cloud_monitor import build_morning_briefing_message

    macro = compute_macro_and_rotation(force_refresh=False)
    scan = run_sepa_vcp_scan(asset_type=None, force_refresh=False)
    title, msg, level = build_morning_briefing_message(macro, scan)
    sent = notification_service.dispatch(
        title=title,
        message=msg,
        level=level,
        category="MORNING_BRIEFING",
        persist_alert=True,
    )
    return {"status": "sent", "title": title, "preview": msg, "delivery": sent}


@router.post("/export-cloud")
def export_alerts_to_cloud_json():
    """Exports active SQLite price alerts to alertas_cloud.json for GitHub Actions 24/7 monitoring."""
    cloud_path = PROJECT_ROOT / "alertas_cloud.json"
    existing = {
        "check_macro_shift": True,
        "check_vcp_breakouts": True,
        "breakout_min_score": 70,
        "price_alerts": [],
        "custom_watchlist": [],
    }
    if cloud_path.exists():
        try:
            loaded = json.loads(cloud_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing.update(loaded)
        except Exception:
            pass

    active_local = db.list_price_alerts(only_active=True)
    exported = [
        {
            "id": f"local-{a['id']}",
            "ticker": a["ticker"],
            "condition": a["condition"],
            "target_price": float(a["target_price"]),
            "notes": a.get("notes") or "",
            "enabled": True,
        }
        for a in active_local
    ]
    existing["price_alerts"] = exported
    cloud_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "status": "exported",
        "path": str(cloud_path),
        "exported_count": len(exported),
    }
