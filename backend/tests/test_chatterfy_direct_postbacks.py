import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ChatterfyDirectPostbacksTest(unittest.TestCase):
    def test_contact_follows_aio_start_chatterfy_not_telegram_start(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        start_event_block = source.split(
            "async def send_pending_chatterfy_start_event(", 1
        )[1].split("async def send_pending_channel_subscription_event", 1)[0]
        telegram_start_block = source.split(
            "async def cmd_start(message: types.Message):", 1
        )[1].split("@dp.message", 1)[0]

        self.assertIn("aio_result = await send_aio_postback_event(", start_event_block)
        self.assertIn(
            "normalized_event_slug != CHATTERFY_START_EVENT",
            start_event_block,
        )
        self.assertIn(
            "send_chatterfy_contact_start_postback(int(user_id))",
            start_event_block,
        )
        self.assertNotIn(
            "send_chatterfy_contact_start_postback",
            telegram_start_block,
        )

    def test_registration_and_deposits_are_mapped_to_direct_bot_postbacks(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        pocket_block = source.split("async def process_pocket_postback(", 1)[1].split(
            '@app.api_route("/api/integrations/pocket/postback"', 1
        )[0]

        self.assertIn("send_chatterfy_bot_pocket_postback(", pocket_block)
        self.assertIn("CHATTERFY_ACCOUNT_REGISTRATION_POSTBACK_URL", pocket_block)
        self.assertIn('event_slug="pocket_registration_account"', pocket_block)

    def test_direct_postback_storage_is_idempotent(self):
        source = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "CREATE TABLE IF NOT EXISTS chatterfy_direct_postback_events",
            source,
        )
        self.assertIn(
            "UNIQUE KEY uq_chatterfy_direct_once (user_id, event_slug, unique_key)",
            source,
        )


if __name__ == "__main__":
    unittest.main()
