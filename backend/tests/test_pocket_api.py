import unittest

from pocket_api import build_pocket_user_info_url, mask_secret


class PocketApiTest(unittest.TestCase):
    def test_builds_signed_user_info_url(self):
        url = build_pocket_user_info_url("797973", "123456", "DhXLWwQTak7ka8Fn6kkf")

        self.assertEqual(
            url,
            "https://pocketpartners.com/api/user-info/797973/123456/cbaf69d09eec8ce37cd44f459632cc59",
        )

    def test_masks_token_with_first_two_and_last_two_chars(self):
        self.assertEqual(mask_secret("DhXLWwQTak7ka8Fn6kkf"), "Dh****************kf")


if __name__ == "__main__":
    unittest.main()
