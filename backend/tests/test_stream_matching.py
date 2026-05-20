import unittest

from stream_matching import stream_requested_asset_matches


class StreamRequestedAssetMatchesTest(unittest.TestCase):
    def test_empty_admin_asset_keeps_global_stream_behavior(self):
        self.assertTrue(
            stream_requested_asset_matches(
                {"emulation_symbol": "", "emulation_market": "commodities"},
                "forex",
                "XPT/USD",
            )
        )

    def test_forex_stream_matches_only_configured_gold_symbol(self):
        settings = {"emulation_symbol": "XAU/USD", "emulation_market": "commodities"}

        self.assertTrue(stream_requested_asset_matches(settings, "forex", "XAU/USD"))
        self.assertTrue(stream_requested_asset_matches(settings, "forex", "XAUUSD"))
        self.assertFalse(stream_requested_asset_matches(settings, "forex", "XPT/USD"))
        self.assertFalse(stream_requested_asset_matches(settings, "forex", "XPD/USD"))
        self.assertFalse(stream_requested_asset_matches(settings, "forex", "WTI/USD"))

    def test_binary_stream_also_respects_market_when_present(self):
        settings = {"emulation_symbol": "Netflix OTC", "emulation_market": "stocks"}

        self.assertTrue(stream_requested_asset_matches(settings, "binary", "Netflix OTC", "stocks"))
        self.assertTrue(stream_requested_asset_matches(settings, "binary", "Netflix", "stock"))
        self.assertFalse(stream_requested_asset_matches(settings, "binary", "Netflix OTC", "crypto"))
        self.assertFalse(stream_requested_asset_matches(settings, "binary", "Toncoin OTC", "crypto"))


if __name__ == "__main__":
    unittest.main()
