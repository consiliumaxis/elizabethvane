import os
import unittest

from aio_tracking import (
    build_aio_field_trigger_url,
    build_aio_fields_trigger_url,
    build_aio_postback_url,
    build_aio_pocket_deposit_conversion_url,
    build_aio_pocket_ftd_conversion_url,
    build_aio_pocket_registration_conversion_url,
    extract_aio_visit_uuid_from_start_text,
    normalize_aio_country_code,
    normalize_aio_revenue,
    normalize_aio_visit_uuid,
    select_aio_profile_status_fields,
)


class AioTrackingTest(unittest.TestCase):
    def setUp(self):
        self.previous_env = {
            key: os.environ.get(key)
            for key in (
                "AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID",
                "AIO_POCKET_FTD_CONVERSION_TYPE_UUID",
                "AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID",
                "AIO_CHATTERFY_START_CONVERSION_TYPE_UUID",
                "AIO_CHATTERFY_BOT_START_CONVERSION_TYPE_UUID",
                "AIO_CHANNEL_SUBSCRIBE_CONVERSION_TYPE_UUID",
                "AIO_COPY_HOT_DOWN_CONVERSION_TYPE_UUID",
                "AIO_VIP_UPGRADE_CONVERSION_TYPE_UUID",
            )
        }
        os.environ["AIO_POCKET_REGISTRATION_CONVERSION_TYPE_UUID"] = "68909ba1-2f86-44ed-97af-3a521017fe45"
        os.environ["AIO_POCKET_FTD_CONVERSION_TYPE_UUID"] = "69d70644-42bf-44de-82b2-be76891ebeb5"
        os.environ["AIO_POCKET_DEPOSIT_CONVERSION_TYPE_UUID"] = "427e553c-8ba2-4c24-8935-f27ea372f70a"
        os.environ["AIO_CHATTERFY_START_CONVERSION_TYPE_UUID"] = "a39ea9ab-20ec-4628-8f19-ee8dcd6d25b9"
        os.environ["AIO_CHATTERFY_BOT_START_CONVERSION_TYPE_UUID"] = "f84ed98b-0882-422a-b0ca-bd89c0b2561d"
        os.environ["AIO_CHANNEL_SUBSCRIBE_CONVERSION_TYPE_UUID"] = "0a74b0c3-1c23-45d3-828e-9a910043e4a4"
        os.environ["AIO_COPY_HOT_DOWN_CONVERSION_TYPE_UUID"] = "b922aaf1-6ffa-4b2e-a859-e5aecb4cde6f"
        os.environ["AIO_VIP_UPGRADE_CONVERSION_TYPE_UUID"] = "187edcc0-9508-4ce0-96eb-5f390787f568"

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

    def test_normalizes_iso_country_code(self):
        self.assertEqual(normalize_aio_country_code(" ua "), "UA")
        self.assertEqual(normalize_aio_country_code("IN"), "IN")
        self.assertIsNone(normalize_aio_country_code("Ukraine"))
        self.assertIsNone(normalize_aio_country_code("U1"))
        self.assertIsNone(normalize_aio_country_code(""))

    def test_builds_start_chatterfy_conversion_url_with_configured_uuid(self):
        url = build_aio_postback_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "start_chatterfy",
            unique_key="start_chatterfy:7097261848",
        )

        self.assertIn("conversion_type_uuid=a39ea9ab-20ec-4628-8f19-ee8dcd6d25b9", url)
        self.assertIn("unique=start_chatterfy%3A7097261848", url)

    def test_builds_start_bot_chatterfy_conversion_url_with_separate_uuid(self):
        url = build_aio_postback_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "start_bot_chatterfy",
            unique_key="start_bot_chatterfy:7097261848",
        )

        self.assertIn("conversion_type_uuid=f84ed98b-0882-422a-b0ca-bd89c0b2561d", url)
        self.assertIn("unique=start_bot_chatterfy%3A7097261848", url)

    def test_builds_channel_subscription_with_dedicated_conversion_endpoint(self):
        url = build_aio_postback_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "channel_subscribe",
            revenue="0",
            currency="USD",
            unique_key="channel_subscribe:7097261848",
        )

        self.assertEqual(
            url,
            "https://app.aio.tech/api/v1/trigger/conversion/"
            "10ac5afb-cbce-4465-95dc-d22a2f735574/"
            "0a74b0c3-1c23-45d3-828e-9a910043e4a4"
            "?arrived_revenue=0.00&currency=usd",
        )

    def test_builds_copy_conversion_with_dedicated_conversion_endpoint(self):
        url = build_aio_postback_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "copy_hot_down",
            revenue="0",
            currency="USD",
        )

        self.assertEqual(
            url,
            "https://app.aio.tech/api/v1/trigger/conversion/"
            "10ac5afb-cbce-4465-95dc-d22a2f735574/"
            "b922aaf1-6ffa-4b2e-a859-e5aecb4cde6f"
            "?arrived_revenue=0.00&currency=usd",
        )

    def test_builds_vip_conversion_with_dedicated_conversion_endpoint(self):
        url = build_aio_postback_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            "vip_upgrade",
            revenue="0",
            currency="USD",
        )

        self.assertEqual(
            url,
            "https://app.aio.tech/api/v1/trigger/conversion/"
            "10ac5afb-cbce-4465-95dc-d22a2f735574/"
            "187edcc0-9508-4ce0-96eb-5f390787f568"
            "?arrived_revenue=0.00&currency=usd",
        )

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

    def test_builds_multiple_status_fields_in_one_request(self):
        url = build_aio_fields_trigger_url(
            "10ac5afb-cbce-4465-95dc-d22a2f735574",
            {"tg_dep_ok": 0, "tg_vip": 0, "tg_copy": 0},
        )

        self.assertEqual(
            url,
            "https://app.aio.tech/api/v1/trigger/field/10ac5afb-cbce-4465-95dc-d22a2f735574/"
            "?tg_dep_ok=0&tg_vip=0&tg_copy=0",
        )

    def test_threshold_sync_does_not_promote_vip_or_copy(self):
        fields = select_aio_profile_status_fields(
            deposit_access_enabled=1,
            synced_values={"tg_dep_ok": 0, "tg_vip": 0, "tg_copy": 0},
        )

        self.assertEqual(fields, {"tg_dep_ok": 1})

    def test_new_visit_initializes_vip_and_copy_to_zero(self):
        fields = select_aio_profile_status_fields(
            deposit_access_enabled=1,
            synced_values={"tg_dep_ok": 1, "tg_vip": 1, "tg_copy": 1},
            visit_changed=True,
        )

        self.assertEqual(fields, {"tg_dep_ok": 1, "tg_vip": 0, "tg_copy": 0})

    def test_existing_vip_and_copy_values_are_not_overwritten(self):
        fields = select_aio_profile_status_fields(
            deposit_access_enabled=1,
            synced_values={"tg_dep_ok": 1, "tg_vip": 1, "tg_copy": 1},
        )

        self.assertEqual(fields, {})

    def test_rejects_unknown_batch_field(self):
        with self.assertRaisesRegex(ValueError, "AIO field name is invalid"):
            build_aio_fields_trigger_url(
                "10ac5afb-cbce-4465-95dc-d22a2f735574",
                {"unknown_field": 0},
            )


if __name__ == "__main__":
    unittest.main()
