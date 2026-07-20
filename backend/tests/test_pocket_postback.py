import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PocketPostbackSourceTest(unittest.TestCase):
    def test_pocket_postback_accepts_registration_ftd_and_deposit(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("/api/integrations/pocket/postback", source)
        self.assertIn('/postback/{bot_id}/{event_code}', source)
        self.assertIn("POCKET_REGISTRATION_EVENT", source)
        self.assertIn("POCKET_FTD_EVENT", source)
        self.assertIn("POCKET_DEPOSIT_EVENT", source)
        self.assertIn("normalize_pocket_postback_payload", source)

    def test_pocket_postback_stores_tracking_metadata(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        for field in (
            "pocket_click_id",
            "pocket_site_id",
            "pocket_cid",
            "pocket_sub_id1",
            "pocket_sub_id2",
            "trader_id",
        ):
            self.assertIn(field, source)

    def test_schema_has_pocket_tracking_columns_and_log_table(self):
        source = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")

        for field in (
            "pocket_click_id",
            "pocket_site_id",
            "pocket_cid",
            "pocket_sub_id1",
            "pocket_sub_id2",
            "pocket_registered",
            "pocket_deposited",
            "pocket_deposit_amount",
            "pocket_postback_events",
        ):
            self.assertIn(field, source)

    def test_postback_uses_secret_and_telegram_click_id(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("POCKET_POSTBACK_SECRET", source)
        self.assertIn("X-Pocket-Secret", source)
        self.assertIn("telegram_id = normalized.get(\"telegram_id\")", source)
        self.assertIn("WHERE user_id = %s", source)
        self.assertIn("SELECT id, status FROM pocket_postback_events WHERE unique_key", source)
        self.assertIn("sync_aichatter_pocket_event", source)


if __name__ == "__main__":
    unittest.main()
