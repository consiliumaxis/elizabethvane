import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RegistrationLinkVisibilityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        cls.schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        cls.settings = (
            PROJECT_ROOT / "frontend/src/admin/pages/SettingsPage.jsx"
        ).read_text(encoding="utf-8")
        cls.profile = (
            PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx"
        ).read_text(encoding="utf-8")

    def test_database_defaults_preserve_existing_visibility(self):
        self.assertIn(
            "registration_button_bot_enabled TINYINT(1) NOT NULL DEFAULT 1",
            self.schema,
        )
        self.assertIn(
            "registration_button_app_enabled TINYINT(1) NOT NULL DEFAULT 1",
            self.schema,
        )
        self.assertIn(
            '"registration_button_bot_enabled", "ALTER TABLE admin_system_access_settings',
            self.schema,
        )
        self.assertIn(
            '"registration_button_app_enabled", "ALTER TABLE admin_system_access_settings',
            self.schema,
        )

    def test_admin_settings_round_trip_both_switches(self):
        for field_name in (
            "registration_button_bot_enabled",
            "registration_button_app_enabled",
        ):
            self.assertIn(field_name, self.backend)
            self.assertIn(field_name, self.settings)

        self.assertIn("setRegistrationButtonBotEnabled", self.settings)
        self.assertIn("setRegistrationButtonAppEnabled", self.settings)
        self.assertIn("Show button in bot", self.settings)
        self.assertIn("Show button in app", self.settings)
        self.assertIn(
            'system_access_data.get("registration_button_bot_enabled", current_visibility[0])',
            self.backend,
        )
        self.assertIn(
            'system_access_data.get("registration_button_app_enabled", current_visibility[1])',
            self.backend,
        )

    def test_bot_and_app_use_separate_visibility_flags(self):
        self.assertIn('registration_link.get("show_in_bot")', self.backend)
        self.assertIn('"registration_link_app_enabled"', self.backend)
        self.assertIn(
            "registrationLinkAppEnabled && Number(user.pocket_registered || 0) !== 1",
            self.profile,
        )

    def test_manager_link_command_is_not_gated_by_display_switches(self):
        start = self.backend.index("async def cmd_manager_registration_link")
        end = self.backend.find("\n@", start)
        command_source = self.backend[start : end if end != -1 else None]

        self.assertIn("get_registration_link_by_target", command_source)
        self.assertNotIn("show_in_bot", command_source)
        self.assertNotIn("show_in_app", command_source)


if __name__ == "__main__":
    unittest.main()
