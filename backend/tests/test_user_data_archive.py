import unittest
from datetime import datetime
from decimal import Decimal

from user_data_archive import (
    build_archive_summary,
    clear_cache_confirmation,
    deserialize_archive_payload,
    serialize_archive_payload,
    validate_clear_cache_confirmation,
)


class UserDataArchiveTest(unittest.TestCase):
    def test_confirmation_contains_exact_user_id(self):
        self.assertEqual(clear_cache_confirmation(123), "CLEAR 123")
        self.assertTrue(validate_clear_cache_confirmation(123, " CLEAR 123 "))
        self.assertFalse(validate_clear_cache_confirmation(123, "CLEAR 124"))
        self.assertFalse(validate_clear_cache_confirmation(123, "clear 123"))

    def test_archive_serialization_handles_database_values(self):
        payload = {
            "created_at": datetime(2026, 7, 30, 22, 50),
            "balance": Decimal("15.25"),
        }
        serialized = serialize_archive_payload(payload)
        restored = deserialize_archive_payload(serialized)
        self.assertEqual(restored["created_at"], "2026-07-30T22:50:00")
        self.assertEqual(restored["balance"], "15.25")

    def test_summary_counts_records_by_system_and_table(self):
        snapshot = {
            "identity": {
                "user_id": 1,
                "display_name": "Elizabeth",
                "username": "elizabeth",
                "trader_id": "T-10",
                "balance": Decimal("125.50"),
                "deposit_amount": Decimal("50.00"),
                "country": "GB",
            },
            "main_app": {
                "users": [{"user_id": 1}],
                "messages": [{"id": 1}, {"id": 2}],
            },
            "ai_chatter": {
                "messages": [{"id": 3}],
                "user_state": [],
            },
        }
        summary = build_archive_summary(snapshot)
        self.assertEqual(summary["total_records"], 4)
        self.assertEqual(summary["sections"]["main_app"]["records"], 3)
        self.assertEqual(summary["sections"]["ai_chatter"]["tables"]["messages"], 1)
        self.assertEqual(summary["trader_id"], "T-10")
        self.assertEqual(summary["user_id"], 1)
        self.assertEqual(summary["balance"], Decimal("125.50"))
        self.assertEqual(summary["deposit_amount"], Decimal("50.00"))
        self.assertEqual(summary["country"], "GB")


if __name__ == "__main__":
    unittest.main()
