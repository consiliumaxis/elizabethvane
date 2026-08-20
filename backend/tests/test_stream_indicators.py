import unittest

from stream_indicators import (
    coherent_stream_indicator_value,
    distribute_stream_indicator_signals,
    stream_indicator_is_neutral_only,
)


class StreamIndicatorValuesTest(unittest.TestCase):
    def test_oscillator_values_match_their_signals(self):
        self.assertGreaterEqual(coherent_stream_indicator_value("RSI", "BUY", 100), 55)
        self.assertLessEqual(coherent_stream_indicator_value("RSI", "SELL", 100), 45)
        self.assertGreater(coherent_stream_indicator_value("CCI", "BUY", 100), 100)
        self.assertLess(coherent_stream_indicator_value("CCI", "SELL", 100), -100)

    def test_trend_levels_are_on_the_correct_side_of_price(self):
        self.assertLess(coherent_stream_indicator_value("EMA50", "BUY", 100), 100)
        self.assertGreater(coherent_stream_indicator_value("EMA50", "SELL", 100), 100)
        self.assertLess(coherent_stream_indicator_value("PSAR", "BUY", 100), 100)
        self.assertGreater(coherent_stream_indicator_value("PSAR", "SELL", 100), 100)

    def test_macd_and_dmi_direction_is_numeric_and_consistent(self):
        self.assertGreater(coherent_stream_indicator_value("MACD", "BUY", 100)["hist"], 0)
        self.assertLess(coherent_stream_indicator_value("MACD", "SELL", 100)["hist"], 0)
        buy_dmi = coherent_stream_indicator_value("DMI", "BUY", 100)
        sell_dmi = coherent_stream_indicator_value("DMI", "SELL", 100)
        self.assertGreater(buy_dmi["plus_di"], buy_dmi["minus_di"])
        self.assertLess(sell_dmi["plus_di"], sell_dmi["minus_di"])

    def test_atr_and_relative_volume_do_not_vote_on_direction(self):
        self.assertTrue(stream_indicator_is_neutral_only("ATR"))
        self.assertTrue(stream_indicator_is_neutral_only("ADX"))
        self.assertTrue(stream_indicator_is_neutral_only("relative_volume"))
        self.assertFalse(stream_indicator_is_neutral_only("RSI"))

    def test_automatic_distribution_is_stable_and_has_directional_majority(self):
        keys = ["RSI", "MACD", "EMA50", "EMA200", "ADX", "DMI", "ATR", "ICHIMOKU"]
        first = distribute_stream_indicator_signals(keys, "SELL")
        second = distribute_stream_indicator_signals(keys, "SELL")

        self.assertEqual(first, second)
        self.assertGreater(sum(signal == "SELL" for signal in first.values()), len(keys) / 2)
        self.assertEqual(first["ADX"], "NEUTRAL")
        self.assertEqual(first["ATR"], "NEUTRAL")

    def test_stream_prices_are_rounded_to_no_more_than_five_decimals(self):
        ema = coherent_stream_indicator_value("EMA50", "BUY", 1.084321987)
        macd = coherent_stream_indicator_value("MACD", "BUY", 1.084321987)

        self.assertEqual(ema, round(ema, 5))
        self.assertEqual(macd["macd"], round(macd["macd"], 5))


if __name__ == "__main__":
    unittest.main()
