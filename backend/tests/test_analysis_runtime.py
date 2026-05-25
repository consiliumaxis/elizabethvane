import unittest

from analysis_runtime import fallback_to_baseline_analysis


class AnalysisRuntimeTest(unittest.TestCase):
    def test_fallback_keeps_existing_baseline_result(self):
        baseline = {
            "recommendation": "BUY",
            "indicators": {"RSI": {"value": 55, "signal": "BUY"}},
        }

        self.assertIs(fallback_to_baseline_analysis(baseline), baseline)

    def test_fallback_builds_safe_neutral_result_without_baseline(self):
        result = fallback_to_baseline_analysis(None)

        self.assertEqual(result["recommendation"], "NEUTRAL")
        self.assertEqual(result["signal"], "NEUTRAL")
        self.assertEqual(result["indicators"], {})


if __name__ == "__main__":
    unittest.main()

