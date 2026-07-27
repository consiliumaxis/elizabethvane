import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

try:
    from backend.studio_statistics import (
        aggregate_studio_statistics,
        normalize_daily_stat,
        normalize_date_range,
        normalize_strategy_winrates,
    )
except ModuleNotFoundError:
    from studio_statistics import (
        aggregate_studio_statistics,
        normalize_daily_stat,
        normalize_date_range,
        normalize_strategy_winrates,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class StudioStatisticsTest(unittest.TestCase):
    def test_normalizes_range_and_daily_values(self):
        start, end = normalize_date_range("2026-07-10", "2026-07-01")
        self.assertEqual(start, date(2026, 7, 1))
        self.assertEqual(end, date(2026, 7, 10))

        row = normalize_daily_stat(
            {
                "date": "2026-07-10",
                "new_users": "120",
                "total_users": "50120",
                "deals": "100000",
                "volume": "1250000,50",
                "strategy_winrates": [
                    {"strategy_id": 1, "strategy_name": "Prime", "winrate": "72.5"}
                ],
            }
        )
        self.assertEqual(row["new_users"], 120)
        self.assertEqual(row["total_users"], 50120)
        self.assertEqual(row["deals"], 100000)
        self.assertEqual(row["volume"], Decimal("1250000.50"))

    def test_rejects_invalid_winrates(self):
        with self.assertRaises(ValueError):
            normalize_strategy_winrates(
                [{"strategy_id": 1, "strategy_name": "Prime", "winrate": 101}]
            )

    def test_aggregates_additive_metrics_and_average_winrates(self):
        summary = aggregate_studio_statistics(
            [
                {
                    "stat_date": "2026-07-01",
                    "new_users": 10,
                    "total_users": 1000,
                    "deals": 100000,
                    "volume": "250000.25",
                    "strategy_winrates": [
                        {"strategy_id": 1, "strategy_name": "Prime", "winrate": 70},
                        {"strategy_id": 2, "strategy_name": "Rapid", "winrate": 80},
                    ],
                },
                {
                    "stat_date": "2026-07-02",
                    "new_users": 12,
                    "total_users": 1012,
                    "deals": 120000,
                    "volume": "350000.75",
                    "strategy_winrates": [
                        {"strategy_id": 1, "strategy_name": "Prime", "winrate": 74},
                        {"strategy_id": 2, "strategy_name": "Rapid", "winrate": 76},
                    ],
                },
            ]
        )

        self.assertEqual(summary["new_users"], 22)
        self.assertEqual(summary["total_users"], 1012)
        self.assertEqual(summary["deals"], 220000)
        self.assertEqual(summary["volume"], "600001.00")
        self.assertEqual(summary["strategy_winrates"][0]["winrate"], 78.0)
        self.assertEqual(summary["strategy_winrates"][1]["winrate"], 72.0)

    def test_schema_api_and_frontend_are_wired(self):
        schema = (PROJECT_ROOT / "backend/db_bootstrap.py").read_text(encoding="utf-8")
        backend = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")
        app = (PROJECT_ROOT / "frontend/src/admin/AdminApp.jsx").read_text(encoding="utf-8")
        page_path = PROJECT_ROOT / "frontend/src/admin/pages/StudioStatisticsPage.jsx"

        self.assertIn("CREATE TABLE IF NOT EXISTS admin_studio_daily_stats", schema)
        self.assertIn('@app.get("/api/admin/studio-statistics")', backend)
        self.assertIn('@app.post("/api/admin/studio-statistics/day")', backend)
        self.assertIn('@app.delete("/api/admin/studio-statistics/day/{stat_date}")', backend)
        self.assertTrue(page_path.exists())
        self.assertIn("StudioStatisticsPage", app)


if __name__ == "__main__":
    unittest.main()
