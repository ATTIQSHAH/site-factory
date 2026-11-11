import unittest
from factory3 import suppress_ambiguous_menu_prices


class MenuPriceSafetyTests(unittest.TestCase):
    def test_repeated_prices_are_removed_but_menu_items_are_kept(self):
        rows = [{"name": f"Item {n}", "price": "$56.00"} for n in range(4)]
        cleaned = suppress_ambiguous_menu_prices(rows)
        self.assertEqual([row["name"] for row in cleaned], [row["name"] for row in rows])
        self.assertTrue(all(row["price"] == "" for row in cleaned))

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


    def test_menu_parser_preserves_price_ranges(self):
        from factory3 import menu_text
        html = """<main>
          <h2>Cakes</h2>
          <p>Birthday Cake $58.00 - $118.00</p>
          <p>Chocolate Chip Cookie $3.25</p>
          <p>Brownie Bar $4.25</p>
          <p>Lemon Tart $5.00</p>
          <p>Smash Cake $28.00</p>
        </main>"""
        items = menu_text(html)
        self.assertGreaterEqual(len(items), 5)
        self.assertEqual(items[0]["price"], "$58.00 - $118.00")

if __name__ == "__main__":
    unittest.main()
