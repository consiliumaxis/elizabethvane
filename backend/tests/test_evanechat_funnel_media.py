import importlib.util
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = PROJECT_ROOT / "services/evanechat_bot/service/funnel_media.py"
SPEC = importlib.util.spec_from_file_location("evanechat_funnel_media", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EvanechatFunnelMediaTest(unittest.TestCase):
    def test_splits_video_note_tag_from_text(self):
        self.assertEqual(
            MODULE.split_funnel_reply("Перед кружком\n[SEND:W2.5]\nКоротко о кружке"),
            ("w2.5", "Перед кружком", "Коротко о кружке"),
        )

    def test_only_first_video_note_is_selected(self):
        self.assertEqual(
            MODULE.split_funnel_reply("[SEND:a1]\nТекст\n[SEND:a2]"),
            ("a1", "", "Текст"),
        )

    def test_plain_reply_is_unchanged(self):
        self.assertEqual(MODULE.split_funnel_reply("Обычный ответ"), (None, "Обычный ответ", ""))


if __name__ == "__main__":
    unittest.main()
