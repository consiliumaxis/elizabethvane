import sys
import types
import unittest

if "httpx" not in sys.modules:
    sys.modules["httpx"] = types.SimpleNamespace(
        Response=object,
        AsyncClient=object,
        HTTPStatusError=Exception,
    )

from analysis_ai_service import sanitize_gpt_analysis


class AnalysisAiConsistencyTest(unittest.TestCase):
    def test_numeric_baseline_overrides_contradictory_gpt_indicator_signals(self):
        parsed = {
            "recommendation": "SELL",
            "confidence": 61,
            "indicators": {
                "RSI": {"value": 52, "signal": "SELL"},
                "EMA50": {"value": 1.09000, "signal": "SELL"},
                "MACD": {"value": -0.001, "signal": "SELL"},
            },
            "key_levels": {},
        }
        baseline = {
            "indicators": {
                "RSI": {"value": 58.2, "signal": "BUY", "weight": 1.2},
                "EMA50": {"value": 1.08320, "signal": "BUY", "weight": 1.1},
                "MACD": {"value": {"hist": 0.00021}, "signal": "BUY", "weight": 1.0},
            }
        }

        result = sanitize_gpt_analysis(
            parsed,
            symbol="EUR/USD",
            interval="5m",
            price=1.08432,
            raw_payload={"price": 1.08432},
            baseline_analysis=baseline,
        )

        self.assertEqual(result["recommendation"], "BUY")
        self.assertEqual(result["indicators"]["RSI"]["signal"], "BUY")
        self.assertEqual(result["indicators"]["RSI"]["value"], 58.2)
        self.assertIn("numeric_majority_enforced", result["confidence_reason"])

    def test_neutral_numeric_baseline_is_not_relabelled_by_gpt(self):
        parsed = {
            "recommendation": "BUY",
            "confidence": 55,
            "indicators": {"ADX": {"value": 31, "signal": "BUY"}},
            "key_levels": {},
        }
        baseline = {
            "indicators": {"ADX": {"value": 18.0, "signal": "NEUTRAL", "weight": 1.0}}
        }

        result = sanitize_gpt_analysis(
            parsed,
            symbol="EUR/USD",
            interval="5m",
            price=1.08432,
            raw_payload={"price": 1.08432},
            baseline_analysis=baseline,
        )

        self.assertEqual(result["indicators"]["ADX"]["signal"], "NEUTRAL")
        self.assertEqual(result["indicators"]["ADX"]["value"], 18.0)


if __name__ == "__main__":
    unittest.main()
