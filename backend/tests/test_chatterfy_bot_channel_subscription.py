import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ChatterfyBotChannelSubscriptionSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        cls.schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        cls.users_page = (
            PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx"
        ).read_text(encoding="utf-8")

    def test_webhook_accepts_channel_subscription_for_bot_identity(self):
        self.assertIn("CHANNEL_SUBSCRIBE_EVENT", self.backend)
        self.assertIn(
            "event_slug in {CHATTERFY_BOT_START_EVENT, CHANNEL_SUBSCRIBE_EVENT}",
            self.backend,
        )
        self.assertIn(
            "await record_chatterfy_bot_channel_subscription(user_id)",
            self.backend,
        )

    def test_subscription_is_stored_separately_from_bot_funnel(self):
        column_name = "chatterfy_bot_channel_subscribed_at"
        self.assertIn(f"{column_name} TIMESTAMP NULL DEFAULT NULL", self.schema)
        self.assertIn(f"SET {column_name} = COALESCE(", self.backend)
        subscription_helper = self.backend.split(
            "async def record_chatterfy_bot_channel_subscription", 1
        )[1].split("@app.post", 1)[0]
        self.assertNotIn("user_onboarding", subscription_helper)
        self.assertNotIn("channel_gate_completed_at", subscription_helper)

    def test_admin_profile_exposes_subscription_status_only(self):
        self.assertIn("chatterfy_bot_channel_subscribed_at", self.backend)
        self.assertIn("chatterfyChannelSubscribed", self.users_page)
        self.assertIn("Подписка на канал", self.users_page)
        client_profile = (PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("chatterfy_bot_channel_subscribed_at", client_profile)


if __name__ == "__main__":
    unittest.main()
