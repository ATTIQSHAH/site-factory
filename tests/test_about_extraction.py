import unittest
from bs4 import BeautifulSoup
from factory3 import about_from_soup

class AboutExtractionTests(unittest.TestCase):
    def test_story_heading_selects_source_authored_paragraph(self):
        soup = BeautifulSoup(
            "<h2>Eat More Sweets</h2><p>Rebecca Masson's confectionaries have become "
            "a sweet staple in Houston. Her style combines French pastry techniques "
            "with nostalgic homemade favorites for local customers.</p>",
            "html.parser",
        )
        self.assertIn("French pastry techniques", about_from_soup(soup))

    def test_contact_details_are_not_used_as_about_copy(self):
        soup = BeautifulSoup(
            "<h2>Visit our shop</h2><p>1701 West 15th Street Houston TX 77008 "
            "(713) 522-1900 eatmoresweets@example.com</p>",
            "html.parser",
        )
        self.assertEqual(about_from_soup(soup), "")

if __name__ == "__main__":
    unittest.main()
