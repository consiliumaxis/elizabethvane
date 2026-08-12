import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AdminUserPocketFiltersSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        cls.users_page = (
            PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx"
        ).read_text(encoding="utf-8")

    def test_api_supports_exclusive_pocket_stages(self):
        endpoint = self.backend.split('async def admin_users(', 1)[1].split(
            'async def admin_user_profile_details', 1
        )[0]
        self.assertIn('pocket_status: str = "all"', endpoint)
        self.assertIn('"not_registered"', endpoint)
        self.assertIn('"registered"', endpoint)
        self.assertIn('"deposited"', endpoint)
        self.assertIn('COALESCE(u.pocket_registered, 0) = 0', endpoint)
        self.assertIn('COALESCE(u.pocket_registered, 0) = 1', endpoint)
        self.assertIn('COALESCE(u.pocket_deposited, 0) = 1', endpoint)
        self.assertIn('Unknown Pocket status filter', endpoint)
        self.assertGreaterEqual(endpoint.count('WHERE {pocket_filter_sql}'), 3)

    def test_admin_ui_sends_and_renders_pocket_filter(self):
        self.assertIn("const [pocketStatus, setPocketStatus] = useState('all')", self.users_page)
        self.assertIn('pocket_status: currentPocketStatus', self.users_page)
        self.assertIn('admin-user-pocket-filters', self.users_page)
        self.assertIn("value: 'not_registered'", self.users_page)
        self.assertIn("value: 'registered'", self.users_page)
        self.assertIn("value: 'deposited'", self.users_page)


if __name__ == "__main__":
    unittest.main()
