import unittest
from factory3 import suppress_ambiguous_menu_prices


class MenuPriceSafetyTests(unittest.TestCase):
    def test_repeated_prices_are_suppressed(self):
        rows = [{"name": f"Item {n}", "price": "$56.00"} for n in range(4)]
        self.assertEqual(suppress_ambiguous_menu_prices(rows), [])

    def test_distinct_prices_are_preserved(self):
        rows = [
            {"name": "Croissant", "price": "$4.00"},
            {"name": "Cake", "price": "$7.50"},
            {"name": "Cookie", "price": "$3.25"},
        ]
        self.assertEqual(suppress_ambiguous_menu_prices(rows), rows)

    def test_unpriced_items_are_preserved(self):
        rows = [{"name": "Croissant", "price": ""}, {"name": "Cake", "price": ""}]
        self.assertEqual(suppress_ambiguous_menu_prices(rows), rows)


if __name__ == "__main__":
    unittest.main()
