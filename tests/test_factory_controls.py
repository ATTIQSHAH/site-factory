import unittest
from factory3 import select_leads, concept_menu


class LeadTargetingTests(unittest.TestCase):
    def test_concept_menu_is_deterministic_unpriced_and_niche_appropriate(self):
        coffee = concept_menu("coffee")
        self.assertGreaterEqual(len(coffee), 5)
        self.assertTrue(all(item["is_illustrative"] and item["price"] == "" for item in coffee))
        self.assertTrue(any("Latte" in item["name"] or "Espresso" in item["name"] for item in coffee))
        self.assertEqual(coffee, concept_menu("coffee"))

    def setUp(self):
        self.rows = [
            {"Name": "Copper Creek Restaurant", "Website": "https://coppercreek.example/"},
            {"Name": "Fluff Bake Bar", "Website": "https://fluffbakebar.com/"},
        ]

    def test_exact_target_is_selected_even_if_previously_processed(self):
        done = {"https://fluffbakebar.com/": {"review_status": "pending"}}
        selected = select_leads(self.rows, "https://fluffbakebar.com", done)
        self.assertEqual([row["Name"] for row in selected], ["Fluff Bake Bar"])
        self.assertNotIn("https://fluffbakebar.com/", done)

    def test_target_must_match_exactly_one_lead(self):
        with self.assertRaises(ValueError):
            select_leads(self.rows, "https://missing.example/")

    def test_normal_batch_skips_completed_leads(self):
        done = {"https://coppercreek.example/": {"review_status": "pending"}}
        selected = select_leads(self.rows, done=done)
        self.assertEqual([row["Name"] for row in selected], ["Fluff Bake Bar"])


if __name__ == "__main__":
    unittest.main()
