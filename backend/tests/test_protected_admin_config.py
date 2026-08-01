import os
import unittest
from unittest.mock import patch

from backend.admin_config import env_int_list


class ProtectedAdminConfigTests(unittest.TestCase):
    def test_reads_multiple_unique_owner_ids(self):
        with patch.dict(
            os.environ,
            {"ADMIN_PROTECTED_USER_IDS": "7097261848, 405935431,7097261848"},
        ):
            self.assertEqual(
                env_int_list("ADMIN_PROTECTED_USER_IDS", (1,)),
                [7097261848, 405935431],
            )

    def test_uses_defaults_for_empty_or_invalid_configuration(self):
        with patch.dict(os.environ, {"ADMIN_PROTECTED_USER_IDS": "bad,0,-5"}):
            self.assertEqual(
                env_int_list("ADMIN_PROTECTED_USER_IDS", (7097261848, 405935431)),
                [7097261848, 405935431],
            )


if __name__ == "__main__":
    unittest.main()
