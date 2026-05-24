import unittest

from market_symbol_mapping import get_twelvedata_symbol_candidates, has_explicit_twelvedata_mapping


class MarketSymbolMappingTest(unittest.TestCase):
    def test_requested_stock_mappings(self):
        self.assertEqual(get_twelvedata_symbol_candidates("Apple OTC")[0], ("AAPL", None))
        self.assertEqual(get_twelvedata_symbol_candidates("Tesla OTC")[0], ("TSLA", None))
        self.assertEqual(get_twelvedata_symbol_candidates("NVIDIA OTC")[0], ("NVDA", None))
        self.assertEqual(get_twelvedata_symbol_candidates("Johnson & Johnson OTC")[0], ("JNJ", None))
        self.assertEqual(get_twelvedata_symbol_candidates("VIX OTC")[0], ("VIXY", None))

    def test_requested_commodity_mappings(self):
        self.assertEqual(get_twelvedata_symbol_candidates("Natural Gas")[0], ("BOIL", None))
        self.assertEqual(get_twelvedata_symbol_candidates("W_1")[0], ("WEAT", None))
        self.assertEqual(get_twelvedata_symbol_candidates("C_1")[0], ("CORN", "NYSE"))
        self.assertEqual(get_twelvedata_symbol_candidates("S_1")[0], ("SOYB", "NYSE"))
        self.assertEqual(get_twelvedata_symbol_candidates("CT1")[0], ("COTN", "LSE"))
        self.assertEqual(get_twelvedata_symbol_candidates("SB1")[0], ("SUGA", "LSE"))
        self.assertEqual(get_twelvedata_symbol_candidates("KC1")[0], ("COFF", "LSE"))
        self.assertEqual(get_twelvedata_symbol_candidates("CC1")[0], ("CC1", None))

    def test_explicit_mapping_does_not_treat_plain_forex_pairs_as_mapped(self):
        self.assertTrue(has_explicit_twelvedata_mapping("Apple OTC"))
        self.assertFalse(has_explicit_twelvedata_mapping("EUR/USD"))


if __name__ == "__main__":
    unittest.main()
