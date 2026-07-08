import unittest

from strategy_indicators import (
    align_analysis_indicators_to_strategy,
    choose_effective_indicator_keys,
    normalize_indicator_keys,
)


class StrategyIndicatorsTest(unittest.TestCase):
    def test_normalizes_indicator_keys_without_losing_strategy_filters(self):
        self.assertEqual(
            normalize_indicator_keys(["bb", "EMA 9", "PIVOT_POINTS_HL", "fibonacci", "DMI", "bb"]),
            ["BB", "EMA 9", "PIVOT_POINTS_HL", "FIBONACCI", "DMI"],
        )

    def test_database_strategy_keys_win_over_stale_client_keys(self):
        db_keys = ["bb", "ema9", "atr", "ema50", "ema200", "adx", "fibonacci", "DMI", "SUPERTREND", "ICHIMOKU"]
        stale_client_keys = ["RSI", "MACD", "ATR", "EMA50", "EMA200", "FIBONACCI"]

        self.assertEqual(
            choose_effective_indicator_keys(stale_client_keys, db_keys),
            ["BB", "EMA9", "ATR", "EMA50", "EMA200", "ADX", "FIBONACCI", "DMI", "SUPERTREND", "ICHIMOKU"],
        )

    def test_client_keys_are_used_only_when_database_has_no_strategy_keys(self):
        self.assertEqual(choose_effective_indicator_keys(["rsi", "macd"], []), ["RSI", "MACD"])

    def test_analysis_indicators_are_aligned_to_existing_configured_strategy_keys(self):
        analysis = {
            "indicators": {
                "ATR": {"value": "0.007", "signal": "NEUTRAL"},
                "RSI": {"value": "38.095", "signal": "NEUTRAL"},
                "MACD": {"value": "-0.000628", "signal": "SELL"},
                "EMA50": {"value": "79.026", "signal": "SELL"},
                "EMA200": {"value": "79.030", "signal": "SELL"},
                "Fibonacci": {"value": "79.046", "signal": "BUY"},
            },
            "votes": {"BUY": 1, "SELL": 3, "NEUTRAL": 2},
        }
        allowed = ["bb", "ema9", "atr", "ema50", "ema200", "adx", "fibonacci", "DMI", "SUPERTREND", "ICHIMOKU"]

        result = align_analysis_indicators_to_strategy(analysis, allowed)

        self.assertEqual(list(result["indicators"].keys()), ["ATR", "EMA50", "EMA200", "FIBONACCI"])
        self.assertNotIn("RSI", result["indicators"])
        self.assertNotIn("MACD", result["indicators"])
        self.assertEqual(result["indicators"]["ATR"]["value"], "0.007")
        self.assertEqual(result["votes"], {"BUY": 1, "SELL": 2, "NEUTRAL": 1})

    def test_alignment_keeps_generated_stream_values_for_all_configured_keys(self):
        analysis = {
            "indicators": {
                "BB": {"value": "Mid band", "signal": "SELL"},
                "EMA9": {"value": 19.05874, "signal": "SELL"},
                "ATR": {"value": 0.001, "signal": "NEUTRAL"},
            }
        }

        result = align_analysis_indicators_to_strategy(analysis, ["bb", "ema9", "atr"])

        self.assertEqual(list(result["indicators"].keys()), ["BB", "EMA9", "ATR"])
        self.assertEqual(result["indicators"]["BB"]["value"], "Mid band")

    def test_alignment_can_fill_missing_configured_indicators_without_placeholders(self):
        analysis = {
            "price": 19.05874,
            "recommendation": "SELL",
            "indicators": {
                "ATR": {"value": 0.001, "signal": "NEUTRAL"},
            },
        }
        allowed = ["BB", "ATR", "ADX", "DMI", "SUPERTREND", "ICHIMOKU", "PIVOT_POINTS_HL"]

        result = align_analysis_indicators_to_strategy(analysis, allowed, fill_missing=True)

        self.assertEqual(list(result["indicators"].keys()), allowed)
        self.assertEqual(result["indicators"]["ATR"]["value"], 0.001)
        self.assertEqual(result["indicators"]["DMI"]["signal"], "SELL")
        self.assertEqual(result["indicators"]["ADX"]["value"], 24.0)
        self.assertNotEqual(result["indicators"]["BB"]["value"], "Configured")
        self.assertNotEqual(result["indicators"]["ICHIMOKU"]["value"], "Configured")

    def test_fill_missing_keeps_each_strategy_indicator_count_exact(self):
        strategies = {
            "minimal": ["RSI", "MACD", "ATR", "EMA50"],
            "trend": ["ADX", "DMI", "SUPERTREND", "ICHIMOKU", "EMA9", "EMA50", "EMA200", "PSAR", "BB"],
            "full": [
                "RSI",
                "MACD",
                "STOCH",
                "BB",
                "EMA9",
                "ATR",
                "EMA50",
                "EMA200",
                "ADX",
                "CCI",
                "PSAR",
                "FIBONACCI",
                "PIVOT_POINTS_HL",
                "DMI",
                "SUPERTREND",
                "ICHIMOKU",
                "EMA9_21",
            ],
        }

        for name, allowed in strategies.items():
            with self.subTest(strategy=name):
                analysis = {
                    "price": 79.015,
                    "recommendation": "SELL",
                    "indicators": {
                        "ATR": {"value": 0.007, "signal": "NEUTRAL"},
                        "RSI": {"value": 38.095, "signal": "NEUTRAL"},
                    },
                }

                result = align_analysis_indicators_to_strategy(analysis, allowed, fill_missing=True)

                self.assertEqual(len(result["indicators"]), len(allowed))
                self.assertEqual(list(result["indicators"].keys()), allowed)
                self.assertFalse(any(str(indicator.get("value")) == "Configured" for indicator in result["indicators"].values()))


if __name__ == "__main__":
    unittest.main()
