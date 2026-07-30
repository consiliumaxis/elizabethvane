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

        self.assertLess(block.index("get_staff_profile"), block.index("get_admin_panel_token"))
        self.assertIn("ADMIN_CENTER_PERMISSIONS", block)
        self.assertIn("admin buttons working", block)

    def test_sync_does_not_overwrite_existing_avatar_with_empty_value(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("NULLIF(VALUES(avatar_url), '')", source)

    def test_profile_uses_user_avatar_url(self):
        source = (PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx").read_text(encoding="utf-8")

        self.assertIn("user.avatar_url", source)
        self.assertIn("brokenAvatarUrl", source)
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

    def test_profile_edit_permission_is_managed_per_user(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        admin = (PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx").read_text(encoding="utf-8")
        schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")

        self.assertIn("/api/admin/users/profile-edit", backend)
        self.assertIn("profile_edit_allowed", backend)
        self.assertIn("profile_edit_allowed TINYINT(1)", schema)
        self.assertIn("profile_name VARCHAR(80)", schema)
        self.assertIn("profile_trader_id VARCHAR(64)", schema)
        self.assertIn("toggleProfileEditing", admin)
        self.assertIn("Редактирование имени и Trader ID", admin)

    def test_manual_trader_id_is_not_sent_to_pocket(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("manual_trader_id", backend)
        self.assertIn("if manual_trader_id or not user_id", backend)
        self.assertIn("AND (profile_trader_id IS NULL OR TRIM(profile_trader_id) = '')", backend)
        self.assertIn("Manual Trader ID is not eligible for Pocket balance sync", backend)
        self.assertIn("balance_sync_enabled = 0", backend)

    def test_user_profile_uses_invisible_text_edit_targets_only_with_permission(self):
        source = (PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx").read_text(encoding="utf-8")
        styles = (PROJECT_ROOT / "frontend/src/components/pages/Profile.css").read_text(encoding="utf-8")

        self.assertIn("profileEditingAllowed", source)
        self.assertIn("openProfileEditor('name')", source)
        self.assertIn("openProfileEditor('trader_id')", source)
        self.assertIn("method: 'PATCH'", source)
        self.assertIn("manualTraderIdHint", source)
        self.assertIn("profile-text-edit-trigger", source)
        self.assertIn("background: transparent", styles)
        self.assertNotIn("profile-inline-edit", source)
        self.assertNotIn("manualValue", source)


if __name__ == "__main__":
    unittest.main()
