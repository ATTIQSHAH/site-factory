import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bs4 import BeautifulSoup

from factory3 import address_of, get_menu, location_details
from site_quality import _external_menu_path


class SourceCrawlTests(unittest.TestCase):
    def test_address_parser_accepts_street_and_postal_code_from_contact_copy(self):
        soup = BeautifulSoup(
            "<p>Come visit us at our shop, 1701 West 15th Street, 77008 in the Heights.</p>",
            "html.parser",
        )
        address, city = address_of({}, "Houston", soup)
        self.assertEqual(address, "1701 West 15th Street, 77008")
        self.assertEqual(city, "")

    def test_location_crawler_follows_same_site_contact_link(self):
        home = BeautifulSoup(
            '<a href="https://www.example.com/contact">Contact Us</a>',
            "html.parser",
        )
        response = SimpleNamespace(
            text="<p>Come visit us at our shop, 1701 West 15th Street, 77008 in the Heights.</p>"
        )
        with patch("factory3.get", return_value=response):
            address, _ = location_details(home, "https://example.com/", {}, "Houston")
        self.assertIn("1701 West 15th Street", address)

    def test_menu_extractor_follows_online_order_link_for_structured_products(self):
        home = BeautifulSoup(
            '<a href="https://shop.example.com/">Order online</a>',
            "html.parser",
        )
        product_page = """<script type="application/ld+json">
        {"@type":"Product","name":"Chocolate Chip Cookie","description":"Cookie",
         "offers":{"price":"3.25","priceCurrency":"USD"}}
        </script>"""
        with patch("factory3.get", return_value=SimpleNamespace(text=product_page)):
            items, menu_url, source = get_menu(home, "https://example.com/")
        self.assertEqual(items[0]["name"], "Chocolate Chip Cookie")
        self.assertEqual(menu_url, "https://shop.example.com/")
        self.assertEqual(source, "structured")

    def test_fragment_only_menu_anchor_is_not_a_real_menu_path(self):
        fake = BeautifulSoup('<a href="https://example.com/#menu">Menu</a>', "html.parser")
        real = BeautifulSoup('<a href="https://shop.example.com/">Order online</a>', "html.parser")
        self.assertFalse(_external_menu_path(fake))
        self.assertTrue(_external_menu_path(real))


if __name__ == "__main__":
    unittest.main()
