import os
import unittest

from aio_tracking import (
    build_aio_field_trigger_url,
    build_aio_pocket_deposit_conversion_url,
    build_aio_pocket_ftd_conversion_url,
    build_aio_pocket_registration_conversion_url,
    extract_aio_visit_uuid_from_start_text,
    normalize_aio_revenue,
    normalize_aio_visit_uuid,
)


class AioTrackingTest(unittest.TestCase):
    def setUp(self):
        self.previous_env = {
            key: os.environ.get(key)
            for key in (
                "AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID",
                "AIO_POCKET_FTD_CONVERSION_TYPE_UUID",
                "AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID",
            )
        }
        os.environ["AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID"] = "68909ba1-2f86-44ed-97af-3a521017fe45"
        os.environ["AIO_POCKET_FTD_CONVERSION_TYPE_UUID"] = "69d70644-42bf-44de-82b2-be76891ebeb5"
        os.environ["AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID"] = "427e553c-8ba2-4c24-8935-f27ea372f70a"

    def tearDown(self):
        for key, value in self.previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_extracts_uuid_from_start_payload(self):
        self.assertEqual(
            extract_aio_visit_uuid_from_start_text("/start 10ac5afb-cbce-4465-95dc-d22a2f735574"),
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
        )
        self.assertIsNone(normalize_aio_visit_uuid("/start bad"))

    def test_normalizes_revenue(self):
        self.assertEqual(normalize_aio_revenue("12.345"), "12.35")
        self.assertEqual(normalize_aio_revenue(None), "0.00")

    def test_builds_pocket_registration_conversion_url(self):
        url = build_aio_pocket_registration_conversion_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            7097261848,
            "900102",
        )

        self.assertEqual(
            url,
            "https://app.aio.tech/api/v1/trigger/conversion-request"
            "?visit_uuid=10ac5afb-cbce-4465-95dc-d22a2f735574"
            "&conversion_type_uuid=68909ba1-2f86-44ed-97af-3a521017fe45"
            "&tgid=7097261848"
            "&tg_trader_id=900102",
        )

    def test_builds_pocket_ftd_conversion_url(self):
        url = build_aio_pocket_ftd_conversion_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "250.505",
            7097261848,
            "900102",
        )

        self.assertIn("conversion_type_uuid=69d70644-42bf-44de-82b2-be76891ebeb5", url)
        self.assertIn("arrived_revenue=250.51", url)
        self.assertIn("tgid=7097261848", url)
        self.assertIn("tg_trader_id=900102", url)

    def test_builds_pocket_deposit_conversion_url(self):
        url = build_aio_pocket_deposit_conversion_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "40",
            7097261848,
            "900102",
        )

        self.assertIn("conversion_type_uuid=427e553c-8ba2-4c24-8935-f27ea372f70a", url)
        self.assertIn("arrived_revenue=40.00", url)

    def test_builds_field_trigger_url(self):
        url = build_aio_field_trigger_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "tg_first_name",
            "Dev Sbite",
        )

        self.assertEqual(
            url,
            "https://app.aio.tech/api/v1/trigger/field/10ac5afb-cbce-4465-95dc-d22a2f735574/"
            "?tg_first_name=Dev+Sbite",
        )


if __name__ == "__main__":
    unittest.main()
