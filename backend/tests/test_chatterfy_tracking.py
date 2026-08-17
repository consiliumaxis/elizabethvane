import unittest

from chatterfy_tracking import (
    CHATTERFY_BOT_START_EVENT,
    CHATTERFY_CHANNEL_SUBSCRIBE_EVENT,
    CHATTERFY_START_EVENT,
    DEFAULT_CHATTERFY_ACCOUNT_REGISTRATION_POSTBACK_URL,
    DEFAULT_CHATTERFY_CONTACT_START_POSTBACK_URL,
    DEFAULT_CHATTERFY_JOIN_APPROVAL_POSTBACK_URL,
    build_chatterfy_bot_postback_url,
    build_chatterfy_join_approval_postback_url,
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

    def test_builds_join_approval_postback_for_telegram_chat(self):
        request_url = build_chatterfy_join_approval_postback_url(
            DEFAULT_CHATTERFY_JOIN_APPROVAL_POSTBACK_URL,
            "7097261848",
        )

        self.assertIn("chat_id=7097261848", request_url)
        self.assertIn("step_id=01a006d8-3872-7c3a-9584-5d9a1f01b4f1", request_url)
        self.assertTrue(request_url.endswith("status=auto"))
        self.assertNotIn("{chatId}", request_url)

    def test_join_approval_postback_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            build_chatterfy_join_approval_postback_url(
                DEFAULT_CHATTERFY_JOIN_APPROVAL_POSTBACK_URL,
                "not-a-chat-id",
            )
        with self.assertRaises(ValueError):
            build_chatterfy_join_approval_postback_url(
                "https://example.com/without-placeholder",
                "7097261848",
            )

    def test_builds_contact_postback_for_start_chatterfy(self):
        request_url = build_chatterfy_bot_postback_url(
            DEFAULT_CHATTERFY_CONTACT_START_POSTBACK_URL,
            "7097261848",
        )

        self.assertEqual(
            request_url,
            "https://api.chatterfy.ai/api/postbacks/"
            "01a000ec-a191-79d0-a2f1-4fb6cc6d4b4e/bot-postback"
            "?chat_id=7097261848&step_id=01a006d8-3875-7769-8247-a62621401769&status=auto",
        )

    def test_builds_additional_account_registration_postback(self):
        request_url = build_chatterfy_bot_postback_url(
            DEFAULT_CHATTERFY_ACCOUNT_REGISTRATION_POSTBACK_URL,
            7097261848,
        )

        self.assertEqual(
            request_url,
            "https://api.chatterfy.ai/api/postbacks/"
            "01a000ec-a191-79d0-a2f1-4fb6cc6d4b4e/bot-postback"
            "?chat_id=7097261848&step_id=01a006d8-3877-7c09-b65b-a0ba558d6870&status=auto",
        )


if __name__ == "__main__":
    unittest.main()
