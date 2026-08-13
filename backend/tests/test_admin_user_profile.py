import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AdminUserProfileSourceTest(unittest.TestCase):
    def test_profile_endpoint_aggregates_main_app_and_integrations(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        chatter = (PROJECT_ROOT / "backend/aichatter_admin.py").read_text(encoding="utf-8")

        self.assertIn('@app.get("/api/admin/users/{target_user_id}/profile")', backend)
        self.assertIn('@app.get("/api/admin/users/{target_user_id}/pocket")', backend)
        self.assertIn('"onboarding": onboarding', backend)
        self.assertIn('"activity": activity', backend)
        self.assertIn('"ai_chatter": ai_chatter', backend)
        self.assertIn("async def get_aichatter_user_summary", chatter)
        self.assertIn('"available": True, "exists": False', chatter)

    def test_profile_contains_customer_journey_and_usage_metrics(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        for field in (
            "quiz_experience",
            "quiz_broker_experience",
            "channel_gate_completed_at",
            "analyses_total",
            "completed_deals",
            "winrate_7d",
            "recent_analyses",
            "chats_count",
            "strategies_count",
        ):
            self.assertIn(field, backend)

    def test_admin_ui_has_professional_sections_and_permission_boundaries(self):
        frontend = (
            PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx"
        ).read_text(encoding="utf-8")

        for section in (
            "Customer profile",
            "Key indicators",
            "Customer journey",
            "Integrations",
            "Management",
            "Data & history",
            "AI Chatter",
            "Recent analyses",
        ):
            self.assertIn(section, frontend)
        self.assertIn("profileTab === 'management' && canProfileEdit", frontend)
        self.assertIn("profileTab === 'data'", frontend)
        self.assertIn("profileLoading", frontend)
        self.assertIn("profileError", frontend)

    def test_client_profile_hides_internal_deposit_levels(self):
        profile = (
            PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx"
        ).read_text(encoding="utf-8")
        styles = (
            PROJECT_ROOT / "frontend/src/components/pages/Profile.css"
        ).read_text(encoding="utf-8")
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertNotIn("YOUR DEPOSIT LEVELS", profile)
        self.assertNotIn("profile-deposit-access-card", profile)
        self.assertNotIn(".profile-deposit-access-card", styles)
        self.assertIn('"deposit_access": deposit_access', backend)


if __name__ == "__main__":
    unittest.main()
