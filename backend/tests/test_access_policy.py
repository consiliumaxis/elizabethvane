import unittest
from decimal import Decimal
from pathlib import Path

from backend.access_policy import (
    ACCESS_POLICY_ALL,
    ACCESS_POLICY_REGISTRATION,
    ACCESS_POLICY_REGISTRATION_DEPOSIT,
    normalize_access_policy,
    normalize_min_deposit,
    system_policy_grants_signal_access,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AccessPolicyTest(unittest.TestCase):
    def test_registration_policy_requires_registration(self):
        settings = {"policy": ACCESS_POLICY_REGISTRATION}

        self.assertFalse(system_policy_grants_signal_access(settings, {"pocket_registered": 0}))
        self.assertTrue(system_policy_grants_signal_access(settings, {"pocket_registered": 1}))

    def test_registration_deposit_policy_requires_total_deposit_threshold(self):
        settings = {"policy": ACCESS_POLICY_REGISTRATION_DEPOSIT, "min_deposit_amount": "50"}

        self.assertFalse(
            system_policy_grants_signal_access(
                settings,
                {"pocket_registered": 1, "pocket_deposited": 1, "pocket_deposit_amount": "49.99"},
            )
        )
        self.assertTrue(
            system_policy_grants_signal_access(
                settings,
                {"pocket_registered": 1, "pocket_deposited": 1, "pocket_deposit_amount": "50.00"},
            )
        )

    def test_all_policy_grants_access_without_pocket_fields(self):
        self.assertTrue(system_policy_grants_signal_access({"policy": ACCESS_POLICY_ALL}, {}))

    def test_policy_and_deposit_normalization(self):
        self.assertEqual(normalize_access_policy("after registration"), ACCESS_POLICY_REGISTRATION)
        self.assertEqual(normalize_access_policy("registration-and-deposit"), ACCESS_POLICY_REGISTRATION_DEPOSIT)
        self.assertEqual(normalize_access_policy("everyone"), ACCESS_POLICY_ALL)
        self.assertEqual(normalize_access_policy("unknown"), ACCESS_POLICY_REGISTRATION_DEPOSIT)
        self.assertEqual(normalize_min_deposit("-10"), Decimal("0.00"))
        self.assertEqual(normalize_min_deposit("25,5"), Decimal("25.50"))


class AccessPolicySourceTest(unittest.TestCase):
    def test_backend_exposes_admin_settings_and_guards_signal_endpoints(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("get_system_access_settings_row", source)
        self.assertIn("system_access_data = data.get(\"system_access\")", source)
        self.assertIn("admin_system_access_settings", source)
        self.assertIn("await require_signal_access(user_id, \"binary\")", source)
        self.assertIn("await require_signal_access(user_id, \"forex\")", source)
        self.assertIn("SIGNAL_ACCESS_REQUIRED_DETAIL", source)
        self.assertIn('override_mode == "allow"', source)
        self.assertIn('override_mode == "deny"', source)
        self.assertIn('"policy": "blocked"', source)

    def test_schema_and_admin_ui_have_access_policy_controls(self):
        schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        ui = (PROJECT_ROOT / "frontend/src/admin/pages/SettingsPage.jsx").read_text(encoding="utf-8")
        css = (PROJECT_ROOT / "frontend/src/admin/admin.css").read_text(encoding="utf-8")

        self.assertIn("admin_system_access_settings", schema)
        self.assertIn("registration_deposit", schema)
        self.assertIn("ACCESS_POLICIES", ui)
        self.assertIn("После регистрации и депозита", ui)
        self.assertIn("payload.system_access", ui)
        self.assertIn("registration_url", schema)
        self.assertIn("systemRegistrationUrl", ui)
        self.assertIn("sync_shared_ai_access_settings", (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8"))
        self.assertIn(".admin-access-policy", css)
        self.assertIn(".admin-access-policy-text", css)
        self.assertIn("grid-template-columns: 28px minmax(0, 1fr) auto", css)

    def test_frontend_shows_signal_gate_modal_on_access_denied(self):
        modal = PROJECT_ROOT / "frontend/src/components/SignalGateModal.jsx"
        self.assertTrue(modal.exists(), "SignalGateModal should be available in Elizabeth frontend")

        modal_source = modal.read_text(encoding="utf-8")
        self.assertIn("Full signal access is not enabled yet", modal_source)
        self.assertIn("Open Channel", modal_source)
        self.assertIn("Message Manager", modal_source)

        for component_path in (
            "frontend/src/components/binary/BinarySignalSettings.jsx",
            "frontend/src/components/forex/ForexAnalysisSettings.jsx",
            "frontend/src/components/demo/DemoAnalysisSettings.jsx",
        ):
            source = (PROJECT_ROOT / component_path).read_text(encoding="utf-8")
            self.assertIn("import SignalGateModal", source)
            self.assertIn("signalGateOpen", source)
            self.assertIn("setSignalGateOpen(true)", source)
            self.assertIn("signal_access_required", source)
            self.assertIn("registration_and_deposit_required", source)
            self.assertIn("<SignalGateModal", source)

        css = (PROJECT_ROOT / "frontend/src/index.css").read_text(encoding="utf-8")
        self.assertIn(".signal-gate-overlay", css)
        self.assertIn(".signal-gate-modal", css)


if __name__ == "__main__":
    unittest.main()
