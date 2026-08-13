import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AioProfileStatusFieldsSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        cls.schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        cls.tracking = (PROJECT_ROOT / "backend/aio_tracking.py").read_text(encoding="utf-8")
        cls.users_page = (
            PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx"
        ).read_text(encoding="utf-8")

    def test_status_fields_are_allowed_and_persist_sync_state(self):
        for field_name in ("tg_dep_ok", "tg_vip", "tg_copy"):
            self.assertIn(f'"{field_name}"', self.tracking)
        for column_name in (
            "aio_status_fields_visit_uuid",
            "aio_dep_ok_synced_value",
            "aio_vip_synced_value",
            "aio_copy_synced_value",
        ):
            self.assertIn(column_name, self.schema)
            self.assertIn(column_name, self.backend)

    def test_new_and_existing_profiles_are_synchronized(self):
        self.assertIn("async def sync_aio_profile_status_fields", self.backend)
        self.assertIn("async def aio_profile_status_backfill_worker", self.backend)
        self.assertGreaterEqual(
            self.backend.count("sync_aio_profile_status_fields("),
            6,
        )
        self.assertIn("select_aio_profile_status_fields", self.backend)
        self.assertIn(
            'deposit_access_enabled=deposit_profile.get("deposit_access")',
            self.backend,
        )
        self.assertNotIn(
            '"tg_vip": int(deposit_profile.get("vip_access") or 0)',
            self.backend,
        )
        self.assertNotIn(
            '"tg_copy": int(deposit_profile.get("copy_access") or 0)',
            self.backend,
        )
        self.assertIn("get_user_deposit_access_profile", self.backend)
        self.assertIn('"aio_status_fields": aio_status_fields_result', self.backend)

    def test_user_cards_receive_and_render_pocket_milestones(self):
        list_query = self.backend.split("async def admin_users", 1)[1].split(
            "async def admin_user_profile_details", 1
        )[0]
        self.assertIn("pocket_registered", list_query)
        self.assertIn("pocket_deposited", list_query)
        self.assertIn("admin-user-profile-milestones", self.users_page)
        self.assertIn("admin-user-list-statuses", self.users_page)
        self.assertIn("Pocket registration confirmed", self.users_page)
        self.assertIn("Pocket deposit confirmed", self.users_page)


if __name__ == "__main__":
    unittest.main()
