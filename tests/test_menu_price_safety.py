import unittest
from factory3 import suppress_ambiguous_menu_prices

class MenuPriceSafetyTests(unittest.TestCase):
    def test_repeated_prices_are_suppressed(self):
        rows = [{'price': '$56.00'} for _ in range(4)]
        self.assertEqual(suppress_ambiguous_menu_prices(rows), [])

if __name__ == '__main__':
    unittest.main()
