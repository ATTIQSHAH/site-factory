import unittest
from business_intel import classify_business, extract_social_links
from stock import business_category
from bs4 import BeautifulSoup
from factory3 import select_test_rows, hours_of, address_of, product_items_from_html, menu_text


class BusinessIntelligenceTests(unittest.TestCase):
    def test_website_signals_override_ambiguous_name(self):
        kind, query, info = classify_business(
            name="Copper Creek",
            title="Copper Creek Steakhouse",
            description="A classic steakhouse and grill",
            headings=["Prime steaks", "Dinner menu"],
        )
        self.assertEqual(kind, "grill")
        self.assertEqual(query, "grilled food")
        self.assertTrue(info["evidence"])

    def test_bakery_is_not_misclassified_as_cafe_by_coffee_mention(self):
        kind, _, _ = classify_business(
            name="Fluff Bake Bar",
            title="Fluff Bake Bar | Bakery and Patisserie",
            description="Cakes, cookies and pastries baked daily",
            headings=["Our bakery", "Pastries"],
        )
        self.assertEqual(kind, "bakery")

    def test_fluff_bake_bar_name_is_classified_as_bakery(self):
        kind, _, _ = classify_business(name="Fluff Bake Bar")
        self.assertEqual(kind, "bakery")

    def test_menu_supports_fast_food_classification(self):
        kind, _, _ = classify_business(
            name="The Local Kitchen",
            menu_items=[{"name": "Smash burger"}, {"name": "Loaded fries"}],
        )
        self.assertEqual(kind, "fastfood")

    def test_structured_data_is_used_as_evidence(self):
        kind, _, info = classify_business(
            name="A Place",
            schema_types=["CafeOrCoffeeShop"],
        )
        self.assertEqual(kind, "cafe")
        self.assertTrue(any(x["source"] == "structured_data" for x in info["evidence"]))

    def test_stock_category_uses_classifier_when_name_is_generic(self):
        self.assertEqual(business_category("Copper Creek Restaurant", "grill"), "grill")
        self.assertEqual(business_category("Fluff Bake Bar", "bakery"), "bakery")

    def test_social_profiles_are_discovered_from_website_links(self):
        found = extract_social_links([
            "/share?u=https://example.com",
            "https://www.instagram.com/fluffbakebar/",
            "https://m.facebook.com/FluffHouston",
        ], "https://fluffbakebar.com/")
        self.assertEqual(found["instagram"], "https://www.instagram.com/fluffbakebar/")
        self.assertEqual(found["facebook"], "https://m.facebook.com/FluffHouston")

    def test_single_website_selection_is_exact_and_bounded(self):
        rows = [
            {"Name": "Fluff Bake Bar", "Website": "https://fluffbakebar.com/"},
            {"Name": "Other Bakery", "Website": "https://other.example/"},
        ]
        selected = select_test_rows(rows, "https://fluffbakebar.com", limit=15)
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["Name"], "Fluff Bake Bar")

    def test_unknown_target_fails_instead_of_processing_another_lead(self):
        rows = [{"Name": "Other Bakery", "Website": "https://other.example/"}]
        with self.assertRaises(ValueError):
            select_test_rows(rows, "https://fluffbakebar.com", limit=15)

    def test_batch_limit_remains_enforced_without_target(self):
        rows = [{"Website": f"https://shop{i}.example/"} for i in range(4)]
        self.assertEqual(len(select_test_rows(rows, limit=2)), 2)

    def test_abbreviated_weekly_hours_are_parsed(self):
        hours = hours_of({}, "Wednesday - Saturday 10a-7p Sunday 12p-7p")
        self.assertEqual(hours, [
            ("Wednesday to Saturday", "10 AM to 7 PM"),
            ("Sunday", "12 PM to 7 PM"),
        ])
        partial_schema_hours = hours_of(
            {"openingHours": ["Sunday 12:00-19:00"]},
            "Wednesday - Saturday 10a-7p Sunday 12p-7p",
        )
        self.assertEqual(partial_schema_hours, hours)

    def test_full_street_address_is_recovered_when_schema_only_has_city(self):
        soup = BeautifulSoup("<p>Visit us at 1701 West 15th Street Houston, TX 77008</p>", "html.parser")
        address, city = address_of(
            {"address": "Houston TX 77008 United States"},
            soup.get_text(" ", strip=True),
            soup,
        )
        self.assertEqual(address, "1701 West 15th Street, Houston, TX 77008")
        self.assertEqual(city, "Houston")

    def test_storefront_separate_product_and_price_lines_are_combined(self):
        html = (
            "<div>Cookies</div><div>Chocolate Chip Cookie</div><div>$3.25</div>"
            "<div>Fluffernutter Cookie</div><div>$4.00</div>"
            "<div>Unicorn Bait Cookie</div><div>$3.75</div>"
            "<div>Couch Potato Cookie</div><div>$3.50</div>"
            "<div>Brownie Bar</div><div>$4.25</div>"
        )
        items = menu_text(html)
        self.assertEqual(items[0]["name"], "Chocolate Chip Cookie")
        self.assertEqual(items[0]["price"], "$3.25")

    def test_product_json_ld_extracts_real_menu_items_and_prices(self):
        html = """<script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Product","name":"Chocolate Chip Cookie",
         "description":"Chocolate chip cookie","offers":{"price":"3.25","priceCurrency":"USD"}}
        </script>"""
        items = product_items_from_html(html)
        self.assertEqual(items[0]["name"], "Chocolate Chip Cookie")
        self.assertEqual(items[0]["price"], "USD 3.25")

    def test_unknown_business_defaults_safely(self):
        kind, query, info = classify_business(name="Something")
        self.assertEqual(kind, "restaurant")
        self.assertEqual(query, "restaurant interior")
        self.assertEqual(info["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
