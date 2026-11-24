from app.config import settings
from app.database import Database
from app.services.settings_service import (
    apply_universe_pack,
    get_settings_overview,
    load_persisted_settings,
    test_ai_connection as run_ai_connection_test,
    update_user_settings,
)


def test_settings_persistence_universe_packs_and_cache(tmp_path):
    temp_db = Database(db_path=tmp_path / "test_settings.db")

    # Preserve original values to restore after test
    orig_cap = settings.default_capital_eur
    orig_stop = settings.default_stop_loss_pct
    orig_provider = settings.ai_provider
    orig_key = settings.gemini_api_key

    try:
        # 1. Update risk & AI settings and persist to temp SQLite
        ov = update_user_settings(
            {
                "default_capital_eur": 350.0,
                "default_stop_loss_pct": 5.5,
                "ai_provider": "none",
                "gemini_api_key": "AIzaSyTestSecretKey123456",
            },
            database=temp_db,
            apply_scheduler=False,
        )
        assert ov["risk"]["default_capital_eur"] == 350.0
        assert ov["risk"]["default_stop_loss_pct"] == 5.5
        assert ov["ai"]["gemini_configured"] is True
        assert "AIza" in ov["ai"]["gemini_api_key_masked"]
        assert "TestSecretKey" not in ov["ai"]["gemini_api_key_masked"]

        # 2. Simulate restart: reset runtime values then reload from SQLite
        settings.default_capital_eur = 100.0
        settings.default_stop_loss_pct = 6.0
        load_persisted_settings(database=temp_db)
        assert settings.default_capital_eur == 350.0
        assert settings.default_stop_loss_pct == 5.5

        # 3. Test AI connection in fallback mode
        res_ai = run_ai_connection_test()
        assert res_ai["ok"] is True
        assert res_ai["provider"] == "fallback"

        # 4. Apply curated universe pack (replace_class) & verify watchlist updates
        res_pack = apply_universe_pack("us_sector_etfs", mode="replace_class", database=temp_db)
        assert res_pack["applied_count"] == 11
        stocks = temp_db.get_watchlist(asset_type="stock")
        assert len(stocks) == 11
        assert any(s["ticker"] == "XLK" for s in stocks)

        # 5. Cache stats & purge
        temp_db.cache_set("test:key", "prices", {"v": 1}, 600)
        stats = temp_db.get_storage_stats()
        assert stats["cache_by_category"].get("prices", 0) >= 1
        cleared = temp_db.cache_clear(category="prices")
        assert cleared >= 1
        assert temp_db.get_storage_stats()["cache_by_category"].get("prices", 0) == 0

        # 6. Clear Gemini key cleanly
        ov2 = update_user_settings({"clear_gemini_key": True}, database=temp_db, apply_scheduler=False)
        assert ov2["ai"]["gemini_configured"] is False
    finally:
        settings.default_capital_eur = orig_cap
        settings.default_stop_loss_pct = orig_stop
        settings.ai_provider = orig_provider
        settings.gemini_api_key = orig_key
