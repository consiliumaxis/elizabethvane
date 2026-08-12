import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PrecontactProfileTest(unittest.TestCase):
    def test_chatterfy_upsert_accepts_identity_and_preserves_bot_name(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn('payload.get("tg_name")', source)
        self.assertIn('payload.get("tg_username")', source)
        self.assertIn("INSERT INTO users (\n                    user_id, username, first_name, aio_visit_uuid", source)
        self.assertIn("AND (first_name IS NULL OR TRIM(first_name) = '')", source)
        self.assertIn("AND (username IS NULL OR TRIM(username) = '')", source)

    def test_late_aio_identity_retries_start_chatterfy_idempotently(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("async def send_pending_chatterfy_start_event", source)
        self.assertIn('{"status": "pending", "reason": "missing_aio_visit_uuid"}', source)
        self.assertIn('unique_key=f"{CHATTERFY_START_EVENT}:{int(user_id)}"', source)
        self.assertIn("asyncio.create_task(send_pending_chatterfy_start_event(user_id))", source)
        self.assertIn("chatterfy_start_result = await send_pending_chatterfy_start_event", source)


if __name__ == "__main__":
    unittest.main()
