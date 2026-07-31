import unittest

from stream_indicators import coherent_stream_indicator_value, stream_indicator_is_neutral_only


class StreamIndicatorValuesTest(unittest.TestCase):
    def test_oscillator_values_match_their_signals(self):
        self.assertLess(coherent_stream_indicator_value("RSI", "BUY", 100), 30)
        self.assertGreater(coherent_stream_indicator_value("RSI", "SELL", 100), 70)
        self.assertLess(coherent_stream_indicator_value("CCI", "BUY", 100), -100)
        self.assertGreater(coherent_stream_indicator_value("CCI", "SELL", 100), 100)

    def test_trend_levels_are_on_the_correct_side_of_price(self):
        self.assertLess(coherent_stream_indicator_value("EMA50", "BUY", 100), 100)
        self.assertGreater(coherent_stream_indicator_value("EMA50", "SELL", 100), 100)
        self.assertLess(coherent_stream_indicator_value("PSAR", "BUY", 100), 100)
        self.assertGreater(coherent_stream_indicator_value("PSAR", "SELL", 100), 100)

    def test_macd_and_dmi_direction_is_numeric_and_consistent(self):
        self.assertGreater(coherent_stream_indicator_value("MACD", "BUY", 100)["hist"], 0)
        self.assertLess(coherent_stream_indicator_value("MACD", "SELL", 100)["hist"], 0)
        self.assertGreater(coherent_stream_indicator_value("DMI", "BUY", 100), 0)
        self.assertLess(coherent_stream_indicator_value("DMI", "SELL", 100), 0)

    def test_atr_and_relative_volume_do_not_vote_on_direction(self):
        self.assertTrue(stream_indicator_is_neutral_only("ATR"))
        self.assertTrue(stream_indicator_is_neutral_only("relative_volume"))
        self.assertFalse(stream_indicator_is_neutral_only("RSI"))


if __name__ == "__main__":
    unittest.main()
