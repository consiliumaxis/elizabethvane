import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AIChatAffiliateAdapterSourceTest(unittest.TestCase):
    def test_affiliate_adapter_exposes_required_routes(self):
        source = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")

        for route in (
            "/affiliate/check-user-globally",
            "/affiliate/check-registration",
            "/affiliate/check-deposit",
            "/affiliate/user-info",
        ):
            self.assertIn(route, source)

    def test_affiliate_adapter_requires_shared_secret(self):
        backend = (PROJECT_ROOT / "backend" / "main.py").read_text(encoding="utf-8")
        bot = (PROJECT_ROOT / "services" / "evanechat_bot" / "bot.py").read_text(encoding="utf-8")

        self.assertIn("AFFILIATE_API_SECRET", backend)
        self.assertIn("X-Affiliate-Secret", backend)
        self.assertIn("secrets.compare_digest", backend)
        self.assertIn("X-Affiliate-Secret", bot)

    def test_new_bot_has_no_source_project_links(self):
        service_root = PROJECT_ROOT / "services" / "evanechat_bot"
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in service_root.rglob("*.py")
        )

        for stale_value in ("ftSYZTHiI0s3MGUy", "NFgzhqfwJlgwNDIy", "NEKZfvx9OYUyNzk6", "shortink.io"):
            self.assertNotIn(stale_value, source)


if __name__ == "__main__":
    unittest.main()
