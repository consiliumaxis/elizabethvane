import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ChatterfyJoinApprovalPostbackSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        cls.schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")

    def test_delivery_log_is_unique_per_telegram_user(self):
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS chatterfy_join_approval_postbacks",
            self.schema,
        )
        table = self.schema.split(
            "CREATE TABLE IF NOT EXISTS chatterfy_join_approval_postbacks", 1
        )[1].split(") ENGINE=InnoDB", 1)[0]
        self.assertIn("user_id BIGINT NOT NULL PRIMARY KEY", table)
        self.assertIn("attempt_count INT NOT NULL DEFAULT 1", table)
        self.assertIn("sent_at TIMESTAMP NULL DEFAULT NULL", table)

    def test_delivery_claim_prevents_duplicate_success(self):
        helper = self.backend.split(
            "async def send_chatterfy_join_approval_postback", 1
        )[1].split("async def send_aio_postback_event", 1)[0]
        self.assertIn("INSERT IGNORE INTO chatterfy_join_approval_postbacks", helper)
        self.assertIn('"duplicate" if previous_status == "sent"', helper)
        self.assertIn("status = 'failed'", helper)
        self.assertIn("response.status_code >= 400", helper)

    def test_postback_runs_after_join_is_accepted_and_before_onboarding(self):
        handler = self.backend.split("async def handle_channel_join_request", 1)[1].split(
            "async def map_quiz_answer_with_ai", 1
        )[0]
        approval = handler.index("approve_chat_join_request")
        postback = handler.index("await send_chatterfy_join_approval_postback")
        onboarding = handler.index("await complete_channel_subscription")
        self.assertLess(approval, postback)
        self.assertLess(postback, onboarding)


if __name__ == "__main__":
    unittest.main()
