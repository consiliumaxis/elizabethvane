import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AioGeoPostbackSourceTest(unittest.TestCase):
    def test_schema_retains_geo_and_inbound_conversion(self):
        schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")

        self.assertIn("aio_country_code CHAR(2)", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS aio_inbound_postbacks", schema)
        self.assertIn("conversion_type_uuid VARCHAR(64)", schema)
        self.assertIn("country_code CHAR(2)", schema)
        self.assertIn("uq_aio_inbound_visit_conversion", schema)

    def test_webhook_is_authenticated_validated_and_idempotent(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn('/api/v1/trigger/conversion-request', source)
        self.assertIn('/api/integrations/aio/geo', source)
        self.assertIn("X-AIO-Geo-Secret", source)
        self.assertIn("require_aio_geo_postback_secret", source)
        self.assertIn("get_aio_geo_postback_conversion_type_uuids", source)
        self.assertIn("AIO_CHATTERFY_BOT_START_CONVERSION_TYPE_UUID", source)
        self.assertIn("AIO_CHANNEL_SUBSCRIBE_CONVERSION_TYPE_UUID", source)
        self.assertIn(
            "conversion_type_uuid not in get_aio_geo_postback_conversion_type_uuids()",
            source,
        )
        self.assertIn("normalize_aio_country_code", source)
        self.assertIn("ON DUPLICATE KEY UPDATE", source)

    def test_pending_geo_is_applied_after_identity_arrives(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("async def apply_pending_aio_geo_for_visit", source)
        self.assertIn('"reason": "user_not_linked"', source)
        self.assertIn('"reason": "aio_visit_uuid_is_not_unique"', source)
        self.assertIn("aio_country_code = %s", source)
        self.assertIn("await apply_pending_aio_geo_for_user(int(user_id))", source)
        self.assertIn("aio_geo_result = await apply_pending_aio_geo_for_user", source)
        self.assertIn("asyncio.create_task(apply_pending_aio_geo_for_user(user_id))", source)

    def test_admin_card_exposes_aio_identity_and_histories(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        frontend = (
            PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx"
        ).read_text(encoding="utf-8")

        self.assertIn('"aio_inbound_postbacks": aio_inbound_postbacks', backend)
        self.assertIn('"aio_outbound_events": aio_outbound_events', backend)
        self.assertIn("Conversion identity", frontend)
        self.assertIn("Входящие конверсии AIO", frontend)
        self.assertIn("conversion_type_uuid", frontend)
        self.assertIn("Гео AIO", frontend)

    def test_user_archive_includes_and_clears_aio_geo(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn('"aio_inbound_postbacks"', backend)
        self.assertIn('"aio_country_code = NULL"', backend)


if __name__ == "__main__":
    unittest.main()
