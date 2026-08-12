import unittest
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from registration_links import build_registration_url, parse_registration_link_target


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class RegistrationLinksTest(unittest.TestCase):
    def test_parses_link_username_and_chatterfy_lead_targets(self):
        self.assertEqual(
            parse_registration_link_target("/link @Client_Name"),
            ("username", "client_name"),
        )
        self.assertEqual(
            parse_registration_link_target("/link@ElizabethVane_bot @Client_Name"),
            ("username", "client_name"),
        )
        self.assertEqual(
            parse_registration_link_target("/link lead-019ff2de"),
            ("lead_id", "lead-019ff2de"),
        )
        self.assertEqual(parse_registration_link_target("/link @bad user"), (None, None))

    def test_appends_all_tracking_fields_to_plain_campaign_url(self):
        result = build_registration_url(
            "https://u3.shortink.io/register?utm_campaign=836376&ac=elizabeth_vane_rev1",
            click_id=7097261848,
            aio_visit_uuid="10ac5afb-cbce-4465-95dc-d22a2f735574",
            chatterfy_lead_id="lead-123",
        )
        query = dict(parse_qsl(urlsplit(result).query, keep_blank_values=True))

        self.assertEqual(query["click_id"], "7097261848")
        self.assertEqual(query["sub_id2"], "10ac5afb-cbce-4465-95dc-d22a2f735574")
        self.assertEqual(query["sub_id3"], "lead-123")
        self.assertEqual(query["utm_campaign"], "836376")
        self.assertEqual(query["ac"], "elizabeth_vane_rev1")

    def test_missing_optional_ids_are_kept_empty(self):
        result = build_registration_url(
            "https://u3.shortink.io/register?click_id={click_id}&sub_id2={sub_id2}&sub_id3={sub_id3}",
            click_id=7097261848,
        )
        query = dict(parse_qsl(urlsplit(result).query, keep_blank_values=True))

        self.assertEqual(query["click_id"], "7097261848")
        self.assertEqual(query["sub_id2"], "")
        self.assertEqual(query["sub_id3"], "")

    def test_fixed_campaign_value_is_not_overwritten_by_empty_duplicate(self):
        result = build_registration_url(
            "https://u3.shortink.io/register?cid=962430&cid={cid}&ac=elizabeth_vane_rev1&ac={ac}",
            click_id=7097261848,
        )
        query = parse_qsl(urlsplit(result).query, keep_blank_values=True)

        self.assertEqual([value for key, value in query if key == "cid"], ["962430"])
        self.assertEqual([value for key, value in query if key == "ac"], ["elizabeth_vane_rev1"])

    def test_backend_and_ui_expose_manager_and_client_flows(self):
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        profile = (PROJECT_ROOT / "frontend/src/components/pages/Profile.jsx").read_text(encoding="utf-8")
        settings = (PROJECT_ROOT / "frontend/src/admin/pages/SettingsPage.jsx").read_text(encoding="utf-8")
        users = (PROJECT_ROOT / "frontend/src/admin/pages/UsersPage.jsx").read_text(encoding="utf-8")
        managers = (PROJECT_ROOT / "frontend/src/admin/pages/ManagersPage.jsx").read_text(encoding="utf-8")

        self.assertIn('@dp.message(Command("link"))', backend)
        self.assertIn('/api/user/registration-link', backend)
        self.assertIn('/api/internal/chatterfy/lead', backend)
        self.assertIn('/api/integrations/chatterfy/lead', backend)
        self.assertIn('CHATTERFY_WEBHOOK_SECRET =', backend)
        self.assertIn('require_chatterfy_webhook_secret(supplied_secret)', backend)
        self.assertIn('tracker_click_id=str(tracker_click_id)', backend)
        self.assertIn('chatterfy_tracker_click_id = CASE', backend)
        self.assertIn('unique_key=f"{CHATTERFY_START_EVENT}:{user_id}"', backend)
        self.assertIn('text="Registration link"', backend)
        self.assertIn('not registration_link.get("registered")', backend)
        self.assertIn('Number(user.pocket_registered || 0) !== 1', profile)
        self.assertIn("'/api/user/registration-link'", profile)
        self.assertIn("{'{sub_id3}'}", settings)
        self.assertIn('/api/admin/users/${encodeURIComponent(userId)}/pocket', users)
        self.assertIn("Pocket postback history", users)
        self.assertIn("Chatterfy Chat ID", users)
        self.assertIn("tracker.clickid", users)
        self.assertIn("pocket.chatterfy_tracker_click_id", users)
        self.assertIn("sub_id3 ←", users)
        self.assertIn("/link @username", managers)
        self.assertIn("get_registration_link_by_target(target_kind, target_value)", backend)


if __name__ == "__main__":
    unittest.main()
