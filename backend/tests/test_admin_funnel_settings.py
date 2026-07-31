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
        self.assertIn("quiz_intro_video_enabled: quizIntroVideoEnabled", source)
        self.assertIn("uploadQuizIntroVideo", source)
        self.assertIn("quizIntroVideoLibrary", source)
        self.assertIn("selectQuizIntroVideo", source)
        self.assertIn("confirmQuizIntroVideoAction", source)
        self.assertIn("/api/admin/settings/quiz-intro-video", source)
        self.assertIn("Кружок перед опросником", source)
        self.assertIn("Библиотека сохранённых MP4", source)
        self.assertIn("Сбросить до стандартного", source)
        self.assertIn("Восстановить системный кружок?", source)
        self.assertIn("Стартовый опросник", source)
        self.assertIn("normalizeFinalMessageConfig", source)
        self.assertIn("final_message_config: preparedFinalMessageConfig", source)
        self.assertIn("Финальное сообщение", source)
        self.assertIn("Предпросмотр в Telegram", source)
        self.assertIn("moveFinalMessageButton", source)
        self.assertIn("Показать меню бота", source)
        self.assertIn("Открыть мини-приложение", source)

    def test_admin_support_settings_store_quiz_config(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("normalize_quiz_config", source)
        self.assertIn("quiz_config", source)
        self.assertIn("quiz_intro_video_enabled", source)
        self.assertIn("admin_quiz_intro_video_upload", source)
        self.assertIn("admin_quiz_intro_video_reset", source)
        self.assertIn("admin_quiz_intro_video_select", source)
        self.assertIn("admin_quiz_intro_video_delete", source)
        self.assertIn("QUIZ_INTRO_VIDEO_LIBRARY_DIR", source)
        self.assertIn("activate_quiz_intro_video", source)
        self.assertIn("WHERE environment = %s", source)
        self.assertIn("MAX_QUIZ_INTRO_VIDEO_SIZE", source)
        self.assertIn("get_quiz_config_row", source)
        self.assertIn("check_subscription_enabled", source)
        self.assertIn("channel_id", source)
        self.assertIn("validate_final_message_config", source)
        self.assertIn("final_message_config", source)

    def test_schema_has_onboarding_and_quiz_columns(self):
        source = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")

        self.assertIn("CREATE TABLE IF NOT EXISTS user_onboarding", source)
        self.assertIn("CREATE TABLE IF NOT EXISTS admin_quiz_intro_videos", source)
        self.assertIn("environment VARCHAR(16)", source)
        self.assertIn("uq_admin_quiz_intro_videos_sha256", source)
        self.assertIn("quiz_broker_experience", source)
        self.assertIn("quiz_config LONGTEXT", source)
        self.assertIn("quiz_intro_video_enabled TINYINT(1)", source)
        self.assertIn("final_message_config LONGTEXT", source)
        self.assertIn("check_subscription_enabled", source)
        self.assertIn("channel_gate_completed_at", source)

    def test_completed_quiz_opens_app_without_channel_gate(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        finish_source = source.split("async def finish_quiz_and_open_app", 1)[1].split(
            "async def route_user_after_start", 1
        )[0]
        route_source = source.split("async def route_user_after_start", 1)[1].split(
            "async def write_manager_stats_audit", 1
        )[0]
        continue_source = source.split("async def handle_funnel_continue", 1)[1].split(
            "async def handle_funnel_open_menu", 1
        )[0]

        self.assertNotIn("send_channel_gate", finish_source)
        self.assertIn("complete_channel_subscription", finish_source)
        self.assertIn("send_funnel_final_message", finish_source)
        self.assertNotIn("send_channel_gate", route_source)
        self.assertNotIn("is_user_channel_member", continue_source)


if __name__ == "__main__":
    unittest.main()
