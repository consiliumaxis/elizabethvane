import unittest

from analysis_engine import compute_analysis_decision
from stream_indicators import coherent_stream_indicator_value, distribute_stream_indicator_signals


class AnalysisSignalQualityTest(unittest.TestCase):
    def test_realistic_momentum_payload_produces_directional_signal(self):
        payload = {
            "price": 1.08432,
            "indicators": {
                "RSI": {"rsi": 58.2},
                "MACD": {"macd": 0.00042, "signal": 0.00021},
                "STOCH": {"k": 57.0, "d": 49.0},
                "BB": {"lower_band": 1.08000, "upper_band": 1.09000},
                "EMA50": {"value": 1.08320},
                "EMA200": {"value": 1.08140},
                "ADX": {"adx": 19.0},
                "DMI": {"plus_di": 27.0, "minus_di": 18.0},
                "PSAR": {"psar": 1.08290},
                "ATR": {"atr": 0.00110},
            },
        }
        allowed = ["RSI", "MACD", "STOCH", "BB", "EMA50", "EMA200", "ADX", "DMI", "PSAR", "ATR"]

        result = compute_analysis_decision(
            payload,
            symbol="EUR/USD",
            interval="5m",
            allowed_indicators=allowed,
        )

        self.assertEqual(result["recommendation"], "BUY")
        self.assertGreaterEqual(result["confidence"], 28)
        self.assertEqual(result["indicators"]["RSI"]["signal"], "BUY")
        self.assertEqual(result["indicators"]["DMI"]["signal"], "BUY")
        self.assertEqual(result["indicators"]["ADX"]["signal"], "NEUTRAL")

    def test_price_based_indicator_does_not_claim_direction_at_equal_value(self):
        payload = {
            "price": 1.08432,
            "indicators": {
                "EMA50": {"value": 1.08432},
                "PSAR": {"psar": 1.08432},
                "ATR": {"atr": 0.00110},
            },
        }

        result = compute_analysis_decision(
            payload,
            symbol="EUR/USD",
            interval="5m",
            allowed_indicators=["EMA50", "PSAR", "ATR"],
        )

        self.assertEqual(result["recommendation"], "NEUTRAL")
        self.assertEqual(result["indicators"]["EMA50"]["signal"], "NEUTRAL")
        self.assertEqual(result["indicators"]["PSAR"]["signal"], "NEUTRAL")

    def test_stream_generated_values_reproduce_their_displayed_signals(self):
        price = 1.08432
        keys = ["RSI", "MACD", "CCI", "ADX", "ATR", "EMA50", "EMA200", "DMI"]
        displayed_signals = distribute_stream_indicator_signals(keys, "SELL")
        payload = {
            "price": price,
            "indicators": {
                key: coherent_stream_indicator_value(key, displayed_signals[key], price)
                for key in keys
            },
        }

        result = compute_analysis_decision(
            payload,
            symbol="EUR/USD",
            interval="5m",
            allowed_indicators=keys,
        )

        for key in keys:
            self.assertEqual(result["indicators"][key]["signal"], displayed_signals[key], key)


if __name__ == "__main__":
    unittest.main()
