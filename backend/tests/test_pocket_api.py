import unittest

from pocket_api import (
    POCKET_DEPOSIT_EVENT,
    POCKET_FTD_EVENT,
    POCKET_REGISTRATION_EVENT,
    build_pocket_user_info_url,
    mask_secret,
    normalize_pocket_postback_payload,
)


class PocketApiTest(unittest.TestCase):
    def test_builds_signed_user_info_url(self):
        url = build_pocket_user_info_url("797973", "123456", "DhXLWwQTak7ka8Fn6kkf")

        self.assertEqual(
            url,
            "https://pocketpartners.com/api/user-info/797973/123456/cbaf69d09eec8ce37cd44f459632cc59",
        )

    def test_masks_token_with_first_two_and_last_two_chars(self):
        self.assertEqual(mask_secret("DhXLWwQTak7ka8Fn6kkf"), "Dh****************kf")

    def test_normalizes_registration_postback(self):
        normalized = normalize_pocket_postback_payload(
            {
                "event": "registration",
                "click_id": "7097261848",
                "site_id": "42",
                "trader_id": "900102",
                "cid": "84664",
                "sub_id1": "welcome",
                "sub_id2": "tracker-click-123",
            }
        )

        self.assertEqual(normalized["event_slug"], POCKET_REGISTRATION_EVENT)
        self.assertEqual(normalized["telegram_id"], 7097261848)
        self.assertEqual(normalized["click_id"], "7097261848")
        self.assertEqual(normalized["trader_id"], "900102")
        self.assertEqual(normalized["site_id"], "42")
        self.assertEqual(normalized["cid"], "84664")
        self.assertEqual(normalized["sub_id1"], "welcome")
        self.assertEqual(normalized["sub_id2"], "tracker-click-123")
        self.assertEqual(normalized["unique_key"], "registration:7097261848:900102")

    def test_rejects_bad_click_id(self):
        normalized = normalize_pocket_postback_payload(
            {"event": "registration", "click_id": "not-a-telegram-id", "trader_id": "900102"}
        )

        self.assertEqual(normalized["event_slug"], POCKET_REGISTRATION_EVENT)
        self.assertIsNone(normalized["telegram_id"])

    def test_normalizes_first_deposit_postback(self):
        normalized = normalize_pocket_postback_payload(
            {
                "event": "ftd",
                "click_id": "7097261848",
                "trader_id": "900102",
                "sumdep": "250.50",
                "sub_id2": "tracker-click-123",
            }
        )

        self.assertEqual(normalized["event_slug"], POCKET_FTD_EVENT)
        self.assertEqual(normalized["telegram_id"], 7097261848)
        self.assertEqual(normalized["deposit_amount"], "250.50")
        self.assertEqual(normalized["unique_key"], "ftd:7097261848:900102:250.50")

    def test_normalizes_repeat_deposit_postback(self):
        normalized = normalize_pocket_postback_payload(
            {
                "event": "repeat_deposit",
                "click_id": "7097261848",
                "trader_id": "900102",
                "sumdep": "40",
            }
        )

        self.assertEqual(normalized["event_slug"], POCKET_DEPOSIT_EVENT)
        self.assertEqual(normalized["deposit_amount"], "40.00")


if __name__ == "__main__":
    unittest.main()
