import unittest
from datetime import datetime
from pathlib import Path

from manager_stats import (
    MANAGER_STATS_AUDIT_STATUSES,
    STAFF_ROLE_ADMIN,
    STAFF_ROLE_MANAGER,
    calculate_winrate,
    display_country,
    format_manager_stats,
    normalize_staff_role,
    parse_stats_target,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ManagerStatsTest(unittest.TestCase):
    def test_parses_telegram_id_and_username(self):
        self.assertEqual(parse_stats_target("/stats 123456789"), ("id", 123456789))
        self.assertEqual(parse_stats_target("/stats @Dev_site"), ("username", "dev_site"))
        self.assertEqual(parse_stats_target("/stats@testElizabeth_bot @Client_1"), ("username", "client_1"))
        self.assertEqual(parse_stats_target("/stats"), (None, None))
        self.assertEqual(parse_stats_target("/stats @bad user"), (None, None))

    def test_normalizes_roles_and_calculates_winrate(self):
        self.assertEqual(normalize_staff_role("ADMIN"), STAFF_ROLE_ADMIN)
        self.assertEqual(normalize_staff_role("manager"), STAFF_ROLE_MANAGER)
        self.assertEqual(normalize_staff_role("unknown"), STAFF_ROLE_MANAGER)
        self.assertEqual(calculate_winrate(5, 2), 71.4)
        self.assertIsNone(calculate_winrate(0, 0))
        self.assertIn("success", MANAGER_STATS_AUDIT_STATUSES)
        self.assertIn("denied", MANAGER_STATS_AUDIT_STATUSES)

    def test_formats_copy_friendly_summary(self):
        text = format_manager_stats(
            {
                "user_id": 123456789,
                "username": "nick",
                "country": "IN",
                "deposit_amount": "15",
                "first_deposit_at": datetime(2026, 5, 10, 12, 0),
                "wins_total": 125,
                "losses_total": 49,
                "wins_7d": 31,
                "losses_7d": 11,
            }
        )

        self.assertIn("Client: @nick (ID 123456789)", text)
        self.assertIn("Country: India", text)
        self.assertIn("Deposit: 15.00 USD (10.05.2026)", text)
        self.assertIn("Total trades: 174", text)
        self.assertIn("Winrate: 71.8%", text)
        self.assertIn("Last 7 days: 42 trades, winrate 73.8%", text)

    def test_formats_missing_values_without_fake_zero_winrate(self):
        text = format_manager_stats(
            {
                "user_id": 42,
                "first_name": "Client",
                "country": "",
                "deposit_amount": 0,
            }
        )

        self.assertEqual(display_country("UA"), "Ukraine")
        self.assertIn("Country: Not specified", text)
        self.assertIn("Deposit: Not recorded", text)
        self.assertIn("Winrate: —", text)

    def test_schema_and_command_have_role_and_audit_guards(self):
        schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("role VARCHAR(16) NOT NULL DEFAULT 'admin'", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS manager_stats_audit", schema)
        self.assertIn("country VARCHAR(32)", schema)
        self.assertIn('@dp.message(Command("stats"))', backend)
        self.assertIn('await message.answer("Insufficient permissions")', backend)
        self.assertIn("async def get_manager_stats_summary", backend)
        self.assertIn('@app.get("/api/admin/staff/audit")', backend)
        self.assertIn("ORDER BY audit.created_at DESC, audit.id DESC", backend)
        self.assertIn("NOW() - INTERVAL 7 DAY", backend)
        self.assertIn("format_manager_stats(summary)", backend)
        self.assertLess(
            backend.index('@dp.message(Command("stats"))'),
            backend.index("@dp.message()"),
        )

    def test_admin_has_separate_managers_section(self):
        app = (PROJECT_ROOT / "frontend/src/admin/AdminApp.jsx").read_text(encoding="utf-8")
        page = (PROJECT_ROOT / "frontend/src/admin/pages/ManagersPage.jsx").read_text(encoding="utf-8")

        self.assertIn("{ id: 'managers', label: tr('Managers', 'Менеджеры'), visible:", app)
        self.assertIn("PERMISSIONS.staffView", app)
        self.assertIn("<ManagersPage adminUser={adminUser} />", app)
        self.assertIn("/api/admin/staff", page)
        self.assertIn("/api/admin/staff/audit", page)
        self.assertIn("tr('/stats request history', 'История запросов /stats')", page)
        self.assertIn("tr('Managers and administrators', 'Менеджеры и администраторы')", page)
        self.assertIn("/stats @nickname", page)


if __name__ == "__main__":
    unittest.main()
