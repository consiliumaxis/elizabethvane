import unittest
from pathlib import Path

from aio_tracking import is_unresolved_aio_visit_uuid_placeholder


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ChatterfyAccessPostbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        cls.schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        cls.admin = (
            PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx"
        ).read_text(encoding="utf-8")
        cls.profile = (
            PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx"
        ).read_text(encoding="utf-8")

    def test_schema_tracks_grants_and_inbound_events(self):
        self.assertIn("chatterfy_vip_granted_at", self.schema)
        self.assertIn("chatterfy_copy_granted_at", self.schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS chatterfy_access_events", self.schema)
        self.assertIn("UNIQUE KEY uq_chatterfy_access_once", self.schema)

    def test_webhook_is_protected_and_has_two_access_kinds(self):
        self.assertIn('/api/integrations/chatterfy/access/{access_kind}', self.backend)
        self.assertIn("require_chatterfy_webhook_secret(supplied_secret)", self.backend)
        self.assertIn('"vip": CHATTERFY_VIP_EVENT', self.backend)
        self.assertIn('"copy": CHATTERFY_COPY_EVENT', self.backend)

    def test_delivery_is_deduplicated_and_retryable(self):
        self.assertIn('unique_key=f"chatterfy:{normalized_event_slug}:{int(user_id)}"', self.backend)
        self.assertIn("WHERE id = %s AND status = 'failed'", self.backend)
        self.assertIn("send_pending_chatterfy_access_events", self.backend)

    def test_unresolved_start0_is_ignored_by_access_webhook(self):
        for raw in ("{start0}", "{{start0}}", "start0", "{ START0 }"):
            self.assertTrue(is_unresolved_aio_visit_uuid_placeholder(raw))
        self.assertFalse(
            is_unresolved_aio_visit_uuid_placeholder(
                "0141c6c0-2772-484f-b808-9419b8c930e8"
            )
        )
        self.assertIn(
            "is_unresolved_aio_visit_uuid_placeholder(raw_candidate)",
            self.backend,
        )

    def test_statuses_are_visible_in_admin_and_client_profile(self):
        self.assertIn("chatterfyVipGranted", self.admin)
        self.assertIn("chatterfyCopyGranted", self.admin)
        self.assertIn("VIP active", self.profile)
        self.assertIn("Copy active", self.profile)


if __name__ == "__main__":
    unittest.main()

