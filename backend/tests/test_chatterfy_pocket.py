import os
import unittest
from urllib.parse import parse_qs, urlparse

from chatterfy_pocket import (
    build_chatterfy_bot_pocket_postback_url,
    build_chatterfy_pocket_postback_url,
)


class ChatterfyPocketPostbackTest(unittest.TestCase):
    def setUp(self):
        self.test_env = {
            "CHATTERFY_POCKET_POSTBACK_BASE_URL": (
                "https://api.chatterfy.ai/api/postbacks/test-token/tracker-postback"
            ),
            "CHATTERFY_BOT_POCKET_POSTBACK_BASE_URL": (
                "https://api.chatterfy.ai/api/postbacks/"
                "01a00f6f-d580-77f4-8df1-646adad11d0f/bot-postback"
            ),
            "CHATTERFY_BOT_REGISTRATION_STEP_ID": "01a006d7-5a3d-7dba-8e44-b31c8d0bbb20",
            "CHATTERFY_BOT_DEPOSIT_STEP_ID": "01a006d7-5a71-7c1c-8997-8694739020c2",
            "CHATTERFY_BOT_FTD_STEP_ID": "01a006d7-5a6f-7315-bd36-6db8c5ca29a7",
        }
        self.previous_env = {key: os.environ.get(key) for key in self.test_env}
        os.environ.update(self.test_env)

    def tearDown(self):
        for key, previous_value in self.previous_env.items():
            if previous_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = previous_value

    def assert_query_params(self, url, expected):
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        self.assertEqual(base_url, "https://api.chatterfy.ai/api/postbacks/test-token/tracker-postback")
        self.assertEqual({key: values[0] for key, values in parse_qs(parsed.query).items()}, expected)

    def test_builds_registration_url_with_crm_fields(self):
        url = build_chatterfy_pocket_postback_url(
            event_slug="registration",
            clickid="75NcUdgVsx",
            trader_id="136021659",
            trader_aio_id="eddc8d4c-e8f3-49ce-9cc8-5001bca040da",
            tgid=7097261848,
            unique_key="registration:7097261848:136021659",
        )

        self.assert_query_params(
            url,
            {
                "tracker.event": "registration",
                "clickid": "75NcUdgVsx",
                "fields.trader_id": "136021659",
                "fields.trader_aio_id": "eddc8d4c-e8f3-49ce-9cc8-5001bca040da",
                "fields.tgid": "7097261848",
                "tracker.tid": "registration:7097261848:136021659",
            },
        )

    def test_builds_first_deposit_url_with_revenue(self):
        url = build_chatterfy_pocket_postback_url(
            event_slug="ftd",
            clickid="75NcUdgVsx",
            trader_id="136021659",
            trader_aio_id="eddc8d4c-e8f3-49ce-9cc8-5001bca040da",
            tgid=7097261848,
            revenue="25",
            unique_key="ftd:7097261848:136021659:25.00",
        )

        self.assert_query_params(
            url,
            {
                "tracker.event": "sale",
                "clickid": "75NcUdgVsx",
                "tracker.cost": "25.00",
                "tracker.currency": "usd",
                "tracker.tid": "ftd:7097261848:136021659:25.00",
                "fields.trader_id": "136021659",
                "fields.trader_aio_id": "eddc8d4c-e8f3-49ce-9cc8-5001bca040da",
                "fields.tgid": "7097261848",
            },
        )

    def test_builds_repeat_deposit_url_with_revenue(self):
        url = build_chatterfy_pocket_postback_url(
            event_slug="dep",
            clickid="75NcUdgVsx",
            trader_id="136021659",
            trader_aio_id="eddc8d4c-e8f3-49ce-9cc8-5001bca040da",
            tgid=7097261848,
            revenue="9.5",
            unique_key="dep:7097261848:136021659:9.50",
        )

        self.assert_query_params(
            url,
            {
                "tracker.event": "resale",
                "clickid": "75NcUdgVsx",
                "tracker.cost": "9.50",
                "tracker.currency": "usd",
                "tracker.tid": "dep:7097261848:136021659:9.50",
                "fields.trader_id": "136021659",
                "fields.trader_aio_id": "eddc8d4c-e8f3-49ce-9cc8-5001bca040da",
                "fields.tgid": "7097261848",
            },
        )

    def assert_bot_postback(self, event_slug, expected_step_id):
        url = build_chatterfy_bot_pocket_postback_url(
            event_slug=event_slug,
            tgid=7097261848,
        )
        parsed = urlparse(url)
        self.assertEqual(
            f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
            "https://api.chatterfy.ai/api/postbacks/"
            "01a00f6f-d580-77f4-8df1-646adad11d0f/bot-postback",
        )
        self.assertEqual(
            {key: values[0] for key, values in parse_qs(parsed.query).items()},
            {
                "chat_id": "7097261848",
                "step_id": expected_step_id,
                "status": "auto",
            },
        )

    def test_builds_bot_registration_postback(self):
        self.assert_bot_postback(
            "registration",
            "01a006d7-5a3d-7dba-8e44-b31c8d0bbb20",
        )

    def test_builds_bot_first_deposit_postback(self):
        self.assert_bot_postback(
            "ftd",
            "01a006d7-5a6f-7315-bd36-6db8c5ca29a7",
        )

    def test_builds_bot_repeat_deposit_postback(self):
        self.assert_bot_postback(
            "dep",
            "01a006d7-5a71-7c1c-8997-8694739020c2",
        )

    def test_bot_postback_rejects_invalid_event_and_chat_id(self):
        with self.assertRaises(ValueError):
            build_chatterfy_bot_pocket_postback_url(
                event_slug="unknown",
                tgid=7097261848,
            )
        with self.assertRaises(ValueError):
            build_chatterfy_bot_pocket_postback_url(
                event_slug="registration",
                tgid="bad-id",
            )


if __name__ == "__main__":
    unittest.main()
