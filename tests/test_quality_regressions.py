import unittest
from site_quality import assess_html

BASE = """<!doctype html><html><head><title>Fluff Bake Bar</title>
<meta name="description" content="A bakery serving pastries, cakes and cookies made fresh every day.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"></head><body>
<h1>Fluff Bake Bar</h1><main id="menu"><p>{}</p></main></body></html>"""

class QualityRegressionTests(unittest.TestCase):
    def test_duplicate_menu_names_and_uniform_prices_are_blocking(self):
        cards = """<section id="menu"><h2>Menu</h2><div class="menu-layout">
        <h3 class="menu-section-title">Apple Pie</h3>
        <article class="menu-card"><span class="menu-item-title">Apple Pie</span><span class="menu-item-price-tag">$56.00</span></article>
        <article class="menu-card"><span class="menu-item-title">Pumpkin Pie</span><span class="menu-item-price-tag">$56.00</span></article>
        <article class="menu-card"><span class="menu-item-title">Apple Pie</span><span class="menu-item-price-tag">$56.00</span></article>
        </div></section>"""
        html = BASE.format("Fresh pastries and cakes. " * 20).replace("</main>", cards + "</main>")
        result = assess_html(html, "Fluff Bake Bar", "(713) 522-1900")
        self.assertFalse(result["passed"])
        self.assertTrue(any("duplicate product" in x for x in result["issues"]))
        self.assertTrue(any("repeats a product" in x for x in result["issues"]))
        self.assertTrue(any("prices suspiciously repeat" in x for x in result["issues"]))

    def test_about_section_needs_real_story_copy(self):
        about = '<section id="about"><div class="facts"><div class="fact">123 Main Street</div></div></section>'
        html = BASE.format("Fresh pastries and cakes. " * 20).replace("</main>", about + "</main>")
        result = assess_html(html, "Fluff Bake Bar", "(713) 522-1900")
        self.assertFalse(result["passed"])
        self.assertTrue(any("no business story" in x for x in result["issues"]))

    def test_hero_and_story_must_not_reuse_same_image(self):
        sections = '<section class="hero"><img src="hero.jpg"></section><section id="about"><div class="story-photo-frame"><img src="hero.jpg"></div></section>'
        html = BASE.format("Fresh pastries and cakes. " * 20).replace("</main>", sections + "</main>")
        result = assess_html(html, "Fluff Bake Bar", "(713) 522-1900")
        self.assertFalse(result["passed"])
        self.assertTrue(any("hero image repeated" in x for x in result["issues"]))

if __name__ == "__main__":
    unittest.main()
