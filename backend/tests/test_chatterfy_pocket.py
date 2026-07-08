import os
import unittest
from urllib.parse import parse_qs, urlparse

from chatterfy_pocket import build_chatterfy_pocket_postback_url


class ChatterfyPocketPostbackTest(unittest.TestCase):
    def setUp(self):
        self.previous_base_url = os.environ.get("CHATTERFY_POCKET_POSTBACK_BASE_URL")
        os.environ["CHATTERFY_POCKET_POSTBACK_BASE_URL"] = (
            "https://api.chatterfy.ai/api/postbacks/test-token/tracker-postback"
        )

    def tearDown(self):
        if self.previous_base_url is None:
            os.environ.pop("CHATTERFY_POCKET_POSTBACK_BASE_URL", None)
        else:
            os.environ["CHATTERFY_POCKET_POSTBACK_BASE_URL"] = self.previous_base_url

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


if __name__ == "__main__":
    unittest.main()
