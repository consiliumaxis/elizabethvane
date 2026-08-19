import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class UserCacheAdminTest(unittest.TestCase):
    def test_archive_schema_and_admin_routes_exist(self):
        schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS user_data_archives", schema)
        self.assertIn("/api/admin/users/{target_user_id}/archives", backend)
        self.assertIn("/api/admin/users/{target_user_id}/clear-cache", backend)
        self.assertIn("validate_clear_cache_confirmation", backend)
        self.assertIn("snapshot_main_user_data", backend)

    def test_clear_preserves_identity_staff_and_archive_history(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        start = backend.index("async def clear_main_user_data")
        end = backend.index("async def mark_user_archive_failed", start)
        block = backend[start:end]

        self.assertIn("UPDATE users SET", block)
        self.assertIn("trader_id = NULL", block)
        self.assertIn("chatterfy_bot_lead_id = NULL", block)
        self.assertIn("DELETE FROM user_onboarding", block)
        self.assertIn("DELETE FROM pocket_postback_events", block)
        self.assertIn("DELETE FROM chatterfy_join_approval_postbacks", block)
        self.assertIn("DELETE FROM chatterfy_direct_postback_events", block)
        self.assertIn("DELETE FROM chatterfy_access_events", block)
        self.assertNotIn("DELETE FROM users", block)
        self.assertNotIn("DELETE FROM admin_users", block)
        self.assertNotIn("DELETE FROM user_data_archives", block)

    def test_archive_preserves_chatterfy_delivery_markers_before_clear(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        start = backend.index("async def snapshot_main_user_data")
        end = backend.index("async def clear_main_user_data", start)
        block = backend[start:end]

        self.assertIn("SELECT * FROM chatterfy_join_approval_postbacks", block)
        self.assertIn("SELECT * FROM chatterfy_direct_postback_events", block)
        self.assertIn("SELECT * FROM chatterfy_access_events", block)

    def test_ai_chatter_snapshot_and_clear_cover_user_state(self):
        backend = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        self.assertIn("snapshot_aichatter_user_data", backend)
        self.assertIn("clear_aichatter_user_data", backend)
        for table_name in (
            "messages",
            "conversation_memory",
            "user_state",
            "funnel_media_sent",
            "bot_block_log",
            "postback_events",
            "postback_state",
        ):
            self.assertIn(table_name, backend)

    def test_admin_ui_requires_phrase_and_offers_archive_download(self):
        source = (
            PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx"
        ).read_text(encoding="utf-8")

        self.assertIn("Очистить кэш", source)
        self.assertIn("Архив данных", source)
        self.assertIn("confirmationMatches", source)
        self.assertIn("Создать архив и очистить", source)
        self.assertIn("Скачать JSON", source)
        self.assertIn("Данные на момент очистки", source)
        self.assertIn("Имя пользователя", source)
        self.assertIn("Баланс", source)
        self.assertIn("ARCHIVE_FIELD_LABELS", source)


if __name__ == "__main__":
    unittest.main()
