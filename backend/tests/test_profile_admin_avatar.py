import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProfileAdminAvatarTest(unittest.TestCase):
    def test_profile_api_returns_admin_status_and_url(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("AS is_admin", source)
        self.assertIn("admin_url", source)
        self.assertIn("build_admin_webapp_url()", source)

    def test_admin_auth_allows_authenticated_telegram_admins_with_stale_token(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        start = source.index("async def get_admin_user(")
        end = source.index("async def get_stream_settings_row", start)
        block = source[start:end]

        self.assertLess(block.index("is_admin_user"), block.index("get_admin_panel_token"))
        self.assertIn("admin buttons working", block)

    def test_sync_does_not_overwrite_existing_avatar_with_empty_value(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("NULLIF(VALUES(avatar_url), '')", source)

    def test_profile_uses_user_avatar_url(self):
        source = (PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx").read_text(encoding="utf-8")

        self.assertIn("user.avatar_url", source)
        self.assertIn("avatarBroken", source)
        self.assertNotIn("eric-avatar.jpg", source)
        self.assertNotIn("elizabeth-avatar.jpg", source)

    def test_profile_uses_telegram_display_name(self):
        source = (PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx").read_text(encoding="utf-8")

        self.assertIn("profileDisplayName", source)
        self.assertIn("user.first_name", source)
        self.assertIn("user.username", source)
        self.assertNotIn('<h2 className="profile-name">Elizabeth Vane</h2>', source)

    def test_admin_users_render_user_avatar(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx").read_text(encoding="utf-8")

        self.assertIn("getAvatarUrl", source)
        self.assertIn("admin-user-avatar", source)


if __name__ == "__main__":
    unittest.main()
