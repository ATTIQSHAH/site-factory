import unittest
from business_intel import classify_business, extract_social_links
from stock import business_category


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

    def test_unknown_business_defaults_safely(self):
        kind, query, info = classify_business(name="Something")
        self.assertEqual(kind, "restaurant")
        self.assertEqual(query, "restaurant interior")
        self.assertEqual(info["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
