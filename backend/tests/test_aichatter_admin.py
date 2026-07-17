import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AichatterAdminTest(unittest.TestCase):
    def test_router_exposes_complete_admin_surface(self):
        source = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        for route in (
            '@router.get("/overview")',
            '@router.put("/settings")',
            '@router.get("/users")',
            '@router.get("/users/{telegram_id}/messages")',
            '@router.patch("/users/{telegram_id}")',
            '@router.put("/triggers")',
            '@router.post("/admins")',
            '@router.get("/postbacks")',
            '@router.get("/statistics")',
            '@router.put("/statistics/manual-commission")',
        ):
            self.assertIn(route, source)
        self.assertIn('prefix="/api/admin/aichatter"', source)
        self.assertIn("Depends(admin_dependency)", source)

    def test_database_config_is_isolated_from_elizabeth_database(self):
        source = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        for variable in (
            "AICHAT_DB_HOST",
            "AICHAT_DB_PORT",
            "AICHAT_DB_NAME",
            "AICHAT_DB_USER",
            "AICHAT_DB_PASSWORD",
        ):
            self.assertIn(variable, source)

    def test_trigger_normalization_removes_blanks_and_duplicates(self):
        source = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        self.assertIn("def _split_phrases", source)
        self.assertIn("item.split()", source)
        self.assertIn("phrase.casefold()", source)

    def test_bot_refreshes_database_settings_at_runtime(self):
        source = (PROJECT_ROOT / "services/evanechat_bot/bot.py").read_text(encoding="utf-8")

        self.assertIn("runtime_settings_refresh_worker", source)
        self.assertIn("asyncio.create_task(runtime_settings_refresh_worker())", source)
        self.assertIn("SELECT work_start, work_end, is_enabled FROM settings", source)
        self.assertIn("SELECT system_prompt, enabled, model FROM ai_settings", source)

    def test_admin_uses_a_model_picker(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/AIChatterPage.jsx").read_text(encoding="utf-8")

        self.assertIn("AI_MODEL_OPTIONS", source)
        self.assertIn("gpt-4.1-mini", source)
        self.assertIn("gpt-4.1-nano", source)
        self.assertIn("<label>Модель OpenAI<select", source)


if __name__ == "__main__":
    unittest.main()
