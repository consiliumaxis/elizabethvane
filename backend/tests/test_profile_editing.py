import unittest

from profile_editing import (
    PROFILE_NAME_MAX_LENGTH,
    PROFILE_TRADER_ID_MAX_LENGTH,
    effective_profile_name,
    effective_profile_trader_id,
    has_manual_profile_trader_id,
    normalize_profile_name,
    normalize_profile_trader_id,
)


class ProfileEditingTest(unittest.TestCase):
    def test_normalizes_user_visible_name(self):
        self.assertEqual(normalize_profile_name("  Elizabeth   Vane  "), "Elizabeth Vane")
        self.assertEqual(normalize_profile_name("Елизавета"), "Елизавета")
        with self.assertRaisesRegex(ValueError, "empty"):
            normalize_profile_name("   ")
        with self.assertRaisesRegex(ValueError, "no longer"):
            normalize_profile_name("x" * (PROFILE_NAME_MAX_LENGTH + 1))

    def test_accepts_manual_trader_id_without_pocket_format_assumptions(self):
        self.assertEqual(normalize_profile_trader_id("  Demo Trader #42  "), "Demo Trader #42")
        with self.assertRaisesRegex(ValueError, "empty"):
            normalize_profile_trader_id("")
        with self.assertRaisesRegex(ValueError, "no longer"):
            normalize_profile_trader_id("x" * (PROFILE_TRADER_ID_MAX_LENGTH + 1))

    def test_manual_values_override_display_only(self):
        self.assertEqual(
            effective_profile_name("Custom name", "Telegram name", "telegram_user"),
            "Custom name",
        )
        self.assertEqual(
            effective_profile_name("", "Telegram name", "telegram_user"),
            "Telegram name",
        )
        self.assertEqual(effective_profile_trader_id("MANUAL-7", "900102"), "MANUAL-7")
        self.assertEqual(effective_profile_trader_id("", "900102"), "900102")
        self.assertTrue(has_manual_profile_trader_id("MANUAL-7"))
        self.assertFalse(has_manual_profile_trader_id(" "))


if __name__ == "__main__":
    unittest.main()
