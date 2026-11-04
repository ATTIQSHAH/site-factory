import unittest
from business_intel import classify_business


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

    def test_unknown_business_defaults_safely(self):
        kind, query, info = classify_business(name="Something")
        self.assertEqual(kind, "restaurant")
        self.assertEqual(query, "restaurant interior")
        self.assertEqual(info["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
