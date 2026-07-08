import unittest

from chatterfy_tracking import (
    CHATTERFY_BOT_START_EVENT,
    CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    CHATTERFY_START_EVENT,
    normalize_chatterfy_event,
    normalize_chatterfy_payload,
    normalize_telegram_id,
)


class ChatterfyTrackingTest(unittest.TestCase):
    def test_normalizes_start_event_aliases(self):
        for raw in ("", None, "start", "bot_start", "dialog", "Start Chatterfy"):
            self.assertEqual(normalize_chatterfy_event(raw), CHATTERFY_START_EVENT)

    def test_normalizes_bot_start_event(self):
        self.assertEqual(normalize_chatterfy_event("start_bot_chatterfy"), CHATTERFY_BOT_START_EVENT)

    def test_normalizes_channel_subscription_event_aliases(self):
        for raw in ("subscribe", "channel_subscribe", "join-request-telegram-channel"):
            self.assertEqual(normalize_chatterfy_event(raw), CHATTERFY_CHANNEL_SUBSCRIBE_EVENT)

    def test_normalizes_telegram_id(self):
        self.assertEqual(normalize_telegram_id("7097261848"), 7097261848)
        self.assertIsNone(normalize_telegram_id("bad-id"))

    def test_normalizes_payload_aliases(self):
        normalized = normalize_chatterfy_payload(
            {
                "conversion": "dialog",
                "telegram_id": "7097261848",
                "username": "@devsbite",
                "first_name": "Dev",
                "contact_id": "contact-42",
            }
        )

        self.assertEqual(normalized["event_slug"], CHATTERFY_START_EVENT)
        self.assertEqual(normalized["telegram_id"], 7097261848)
        self.assertEqual(normalized["tg_username"], "devsbite")
        self.assertEqual(normalized["tg_first_name"], "Dev")
        self.assertEqual(normalized["chatterfy_id"], "contact-42")
        self.assertEqual(normalized["unique_key"], "start_chatterfy:7097261848:contact-42")


if __name__ == "__main__":
    unittest.main()
