import unittest

try:
    from backend.deposit_access import (
        calculate_deposit_access,
        normalize_country_code,
        normalize_country_rule,
        normalize_deposit_thresholds,
        resolve_deposit_thresholds,
    )
except ModuleNotFoundError:
    from deposit_access import (
        calculate_deposit_access,
        normalize_country_code,
        normalize_country_rule,
        normalize_deposit_thresholds,
        resolve_deposit_thresholds,
    )


class DepositAccessTests(unittest.TestCase):
    def setUp(self):
        self.defaults = {
            "min_deposit_amount": "10",
            "vip_deposit_amount": "30",
            "copy_deposit_amount": "50",
        }
        self.rules = [
            {
                "country_code": "UA",
                "country_name": "Ukraine",
                "min_deposit_amount": "15",
                "vip_deposit_amount": "45",
                "copy_deposit_amount": "75",
            }
        ]

    def test_country_code_is_iso_and_uk_alias_is_normalized(self):
        self.assertEqual(normalize_country_code(" ua "), "UA")
        self.assertEqual(normalize_country_code("UK"), "GB")
        self.assertEqual(normalize_country_code("Ukraine"), "")

    def test_thresholds_are_monotonic(self):
        normalized = normalize_deposit_thresholds("10", "30", "50")
        self.assertEqual(str(normalized["copy_deposit_amount"]), "50.00")
        with self.assertRaisesRegex(ValueError, "VIP threshold"):
            normalize_deposit_thresholds("20", "10", "50")
        with self.assertRaisesRegex(ValueError, "Copy threshold"):
            normalize_deposit_thresholds("10", "50", "40")

    def test_country_rule_validation(self):
        normalized = normalize_country_rule({**self.rules[0], "is_custom": True})
        self.assertEqual(normalized["country_code"], "UA")
        self.assertTrue(normalized["is_custom"])

    def test_aio_geo_selects_country_and_unknown_geo_uses_defaults(self):
        country = resolve_deposit_thresholds(self.defaults, self.rules, "ua")
        self.assertEqual(country["source"], "country")
        self.assertEqual(country["min_deposit_amount"], "15.00")

        fallback = resolve_deposit_thresholds(self.defaults, self.rules, "ZZ")
        self.assertEqual(fallback["source"], "default")
        self.assertEqual(fallback["min_deposit_amount"], "10.00")

    def test_accumulated_deposit_unlocks_each_level_independently(self):
        result = calculate_deposit_access(
            self.defaults,
            "35",
            registered=True,
            deposited=True,
        )
        self.assertEqual(result["deposit_access"], 1)
        self.assertEqual(result["vip_access"], 1)
        self.assertEqual(result["copy_access"], 0)
        self.assertEqual(result["copy_shortage"], "15.00")

    def test_unconfirmed_deposit_does_not_unlock_access(self):
        result = calculate_deposit_access(
            self.defaults,
            "100",
            registered=True,
            deposited=False,
        )
        self.assertEqual(result["deposit_access"], 0)
        self.assertEqual(result["vip_access"], 0)
        self.assertEqual(result["copy_access"], 0)


if __name__ == "__main__":
    unittest.main()
