import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AdminFunnelSettingsTest(unittest.TestCase):
    def test_admin_settings_page_contains_quiz_editor(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/SettingsPage.jsx").read_text(encoding="utf-8")

        self.assertIn("QUIZ_STEPS", source)
        self.assertIn("DEFAULT_QUIZ_CONFIG", source)
        self.assertIn("normalizeQuizConfig", source)
        self.assertIn("updateQuizQuestion", source)
        self.assertIn("addQuizOption", source)
        self.assertIn("quiz_config: normalizeQuizConfig(quizConfig)", source)
        self.assertIn("Стартовый опросник", source)

    def test_admin_support_settings_store_quiz_config(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("normalize_quiz_config", source)
        self.assertIn("quiz_config", source)
        self.assertIn("get_quiz_config_row", source)
        self.assertIn("check_subscription_enabled", source)
        self.assertIn("channel_id", source)

    def test_schema_has_onboarding_and_quiz_columns(self):
        source = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS user_onboarding", source)
        self.assertIn("quiz_broker_experience", source)
        self.assertIn("quiz_config LONGTEXT", source)
        self.assertIn("check_subscription_enabled", source)
        self.assertIn("channel_gate_completed_at", source)


if __name__ == "__main__":
    unittest.main()
