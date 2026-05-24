import unittest

from binary_signal import enforce_binary_signal


class EnforceBinarySignalTest(unittest.TestCase):
    def test_restores_direction_from_indicator_value_when_signal_is_neutral(self):
        data = {
            "recommendation": "NEUTRAL",
            "indicators": {
                "EMA50": {"value": "BUY", "signal": "NEUTRAL"},
                "EMA200": {"value": "BUY", "signal": "NEUTRAL"},
                "DMI": {"value": "SELL", "signal": "NEUTRAL"},
            },
        }

        result = enforce_binary_signal(data)

        self.assertEqual(result["recommendation"], "BUY")
        self.assertEqual(result["signal"], "BUY")
        self.assertEqual(result["indicators"]["EMA50"]["signal"], "BUY")

    def test_uses_weighted_scores_when_indicator_votes_are_tied(self):
        data = {
            "symbol": "AUD/CHF",
            "interval": "5min",
            "recommendation": "NEUTRAL",
            "weighted_scores": {"buy": 1.2, "sell": 2.1, "neutral": 4.0},
            "indicators": {
                "EMA50": {"value": "BUY", "signal": "NEUTRAL"},
                "DMI": {"value": "SELL", "signal": "NEUTRAL"},
            },
        }

        result = enforce_binary_signal(data)

        self.assertEqual(result["recommendation"], "SELL")

    def test_keeps_true_neutral_when_no_directional_evidence_exists(self):
        data = {
            "recommendation": "NEUTRAL",
            "weighted_scores": {"buy": 0, "sell": 0, "neutral": 5},
            "indicators": {
                "RSI": {"value": 50, "signal": "NEUTRAL"},
                "ATR": {"value": 0.001, "signal": "NEUTRAL"},
            },
        }

        result = enforce_binary_signal(data)

        self.assertEqual(result["recommendation"], "NEUTRAL")
        self.assertNotIn("signal", result)


if __name__ == "__main__":
    unittest.main()
