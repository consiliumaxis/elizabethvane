import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class FrontendNewsBlocksTest(unittest.TestCase):
    def test_forex_result_renders_news_block(self):
        source = (PROJECT_ROOT / "frontend/src/components/forex/ForexAnalysisSettings.jsx").read_text(encoding="utf-8")

        self.assertIn("news-filter-block", source)
        self.assertIn("NewsModal", source)
        self.assertIn("getFilteredNewsStatus", source)

    def test_binary_result_renders_news_block(self):
        source = (PROJECT_ROOT / "frontend/src/components/binary/BinarySignalSettings.jsx").read_text(encoding="utf-8")

        self.assertIn("news-filter-block", source)
        self.assertIn("NewsModal", source)
        self.assertIn("getFilteredNewsStatus", source)


if __name__ == "__main__":
    unittest.main()
