import tempfile
import unittest
from pathlib import Path

from menu_photo import (
    describe_menu_photo,
    detect_menu_photo_format,
    find_custom_menu_photo,
    reset_custom_menu_photo,
    resolve_menu_photo,
    save_custom_menu_photo,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class MenuPhotoStorageTest(unittest.TestCase):
    def test_detects_supported_image_formats_from_bytes(self):
        self.assertEqual(detect_menu_photo_format(b"\xff\xd8\xffpayload"), (".jpg", "image/jpeg"))
        self.assertEqual(
            detect_menu_photo_format(b"\x89PNG\r\n\x1a\npayload"),
            (".png", "image/png"),
        )
        self.assertEqual(
            detect_menu_photo_format(b"RIFF\x00\x00\x00\x00WEBPpayload"),
            (".webp", "image/webp"),
        )
        self.assertIsNone(detect_menu_photo_format(b"not-an-image"))

    def test_custom_image_overrides_default_and_reset_restores_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            default_path = root / "menu.jpg"
            managed_dir = root / "managed"
            default_path.write_bytes(b"\xff\xd8\xffdefault")

            initial_path, initial_source = resolve_menu_photo(str(default_path), str(managed_dir))
            self.assertEqual(initial_path, str(default_path))
            self.assertEqual(initial_source, "default")

            custom_path = save_custom_menu_photo(b"\x89PNG\r\n\x1a\ncustom", str(managed_dir))
            self.assertEqual(Path(custom_path).suffix, ".png")
            self.assertEqual(find_custom_menu_photo(str(managed_dir)), custom_path)
            custom_status = describe_menu_photo(str(default_path), str(managed_dir))
            self.assertEqual(custom_status["source"], "uploaded")
            self.assertTrue(custom_status["preview_url"].startswith("/api/assets/menu-photo?v="))

            webp_path = save_custom_menu_photo(b"RIFF\x00\x00\x00\x00WEBPcustom", str(managed_dir))
            self.assertEqual(Path(webp_path).suffix, ".webp")
            self.assertFalse(Path(custom_path).exists())

            reset_custom_menu_photo(str(managed_dir))
            reset_path, reset_source = resolve_menu_photo(str(default_path), str(managed_dir))
            self.assertEqual(reset_path, str(default_path))
            self.assertEqual(reset_source, "default")

    def test_rejects_unknown_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                save_custom_menu_photo(b"plain text", temp_dir)


class MenuPhotoIntegrationSourceTest(unittest.TestCase):
    def test_backend_exposes_upload_preview_and_reset(self):
        source = (PROJECT_ROOT / "backend/main.py").read_text(encoding="utf-8")

        self.assertIn('@app.get("/api/assets/menu-photo")', source)
        self.assertIn('@app.put("/api/admin/settings/menu-photo")', source)
        self.assertIn('@app.post("/api/admin/settings/menu-photo/reset")', source)
        self.assertIn("clear_menu_photo_file_id_cache()", source)
        self.assertIn('settings["menu_photo"] = get_menu_photo_status()', source)

    def test_admin_ui_has_menu_tab_preview_upload_and_reset_confirmation(self):
        ui = (PROJECT_ROOT / "frontend/src/admin/pages/SettingsPage.jsx").read_text(encoding="utf-8")
        css = (PROJECT_ROOT / "frontend/src/admin/admin.css").read_text(encoding="utf-8")

        self.assertIn("['menu', tr('Bot menu', 'Меню бота')]", ui)
        self.assertIn("/api/admin/settings/menu-photo", ui)
        self.assertIn("/api/admin/settings/menu-photo/reset", ui)
        self.assertIn("setMenuPhotoConfirmOpen(true)", ui)
        self.assertIn("admin-menu-photo-preview", ui)
        self.assertIn(".admin-menu-photo-card", css)
        self.assertIn(".admin-menu-photo-confirm", css)


if __name__ == "__main__":
    unittest.main()
