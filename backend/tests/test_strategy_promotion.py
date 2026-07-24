import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class StrategyPromotionTest(unittest.TestCase):
    def test_admin_api_preserves_owner_and_allows_safe_system_toggle(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("AS owner_users_count", source)
        self.assertIn('row["can_toggle_system"] = 1 if owner_users_count > 0 else 0', source)
        self.assertNotIn("User strategy cannot be converted to system strategy", source)
        self.assertIn("Built-in system strategy cannot be converted to a user strategy", source)

    def test_demoting_promoted_strategy_resets_non_owner_selections(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("if current_is_system == 1 and is_system == 0:", source)
        self.assertIn("SET strategy_id = 1", source)
        self.assertIn("AND user_id NOT IN", source)
        self.assertIn("FROM user_presets up", source)

    def test_promoted_strategy_cannot_be_changed_through_user_crud(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn("Editable user strategy not found", source)
        self.assertIn("Deletable user strategy not found", source)
        self.assertGreaterEqual(source.count("AND p.is_system = 0"), 2)

    def test_admin_ui_exposes_toggle_for_owned_strategies(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/StrategiesPage.jsx").read_text(encoding="utf-8")

        self.assertIn("can_toggle_system", source)
        self.assertIn("Сделать системной", source)
        self.assertIn("admin-system-switch-track", source)
        self.assertIn("Владелец сохраняется", source)
        self.assertIn("is_system: form.is_system", source)

    def test_empty_timeframes_mean_all_and_do_not_block_promotion(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/StrategiesPage.jsx").read_text(encoding="utf-8")

        self.assertNotIn("Выберите хотя бы один таймфрейм", source)
        self.assertIn("стратегия доступна для всех таймфреймов", source)

    def test_strategy_actions_use_visible_floating_notifications(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/StrategiesPage.jsx").read_text(encoding="utf-8")
        styles = (PROJECT_ROOT / "frontend/src/admin/admin.css").read_text(encoding="utf-8")

        self.assertIn("function StrategyToast", source)
        self.assertIn("admin-floating-toast", source)
        self.assertIn("window.setTimeout(() => setStatus(''), 4000)", source)
        self.assertIn("position: fixed", styles)
        self.assertIn("z-index: 10000", styles)

    def test_strategy_metrics_stay_compact_on_mobile(self):
        source = (PROJECT_ROOT / "frontend/src/admin/pages/StrategiesPage.jsx").read_text(encoding="utf-8")
        styles = (PROJECT_ROOT / "frontend/src/admin/admin.css").read_text(encoding="utf-8")

        self.assertIn("admin-strategy-editor-head", source)
        self.assertIn('<div className="admin-metric-label">Пользователи</div>', source)
        self.assertGreaterEqual(styles.count("grid-template-columns: repeat(3, minmax(0, 1fr))"), 2)
        self.assertIn(".admin-strategy-mini-card .admin-metric-value.small", styles)


if __name__ == "__main__":
    unittest.main()
