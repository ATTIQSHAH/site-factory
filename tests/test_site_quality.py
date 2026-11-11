import unittest
from site_quality import assess_html


def cards(count=6):
    return "".join(f'<article class="menu-card"><span class="menu-item-title">Sample item {n}</span></article>' for n in range(count))


BASE = """<!doctype html><html><head><title>Fluff Bake Bar</title>
<meta name="description" content="A polished concept preview for Fluff Bake Bar, featuring an illustrative sample menu and business information.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"></head><body>
<header><h1>Fluff Bake Bar</h1><a href="#menu">Menu</a><a href="tel:+17135221900">Call</a></header>
<main><section id="menu"><div class="concept-menu-disclaimer">Concept preview — illustrative menu ideas only; confirm actual offerings and prices with the business.</div>
<div class="menu-layout">{}</div></section><p>{}</p></main></body></html>"""


class SiteQualityTests(unittest.TestCase):
    def test_complete_concept_page_passes(self):
        result = assess_html(BASE.format(cards(), "Fresh pastries and cakes. " * 20),
                             business_name="Fluff Bake Bar", phone="(713) 522-1900")
        self.assertTrue(result["passed"], result["issues"])
        self.assertTrue(result["menu_is_illustrative"])
        self.assertEqual(result["menu_item_count"], 6)

    def test_missing_content_fails_gate(self):
        result = assess_html("<html><body><h1>Fluff Bake Bar</h1></body></html>",
                             business_name="Fluff Bake Bar")
        self.assertFalse(result["passed"])

    def test_unresolved_placeholders_fail_gate(self):
        html = BASE.format(cards(), "{{BUSINESS_ADDRESS}}")
        result = assess_html(html, business_name="Fluff Bake Bar")
        self.assertFalse(result["passed"])
        self.assertTrue(any("placeholder" in issue for issue in result["issues"]))

    def test_unlabelled_sample_menu_fails_gate(self):
        html = BASE.format(cards(), "Fresh pastries and cakes. " * 20).replace(
            '<div class="concept-menu-disclaimer">Concept preview — illustrative menu ideas only; confirm actual offerings and prices with the business.</div>', "")
        result = assess_html(html, business_name="Fluff Bake Bar")
        self.assertFalse(result["passed"])
        self.assertTrue(any("not clearly labelled" in issue for issue in result["issues"]))

    def test_too_few_sample_items_fails_gate(self):
        result = assess_html(BASE.format(cards(3), "Fresh pastries and cakes. " * 20),
                             business_name="Fluff Bake Bar")
        self.assertFalse(result["passed"])
        self.assertTrue(any("fewer than five" in issue for issue in result["issues"]))

    def test_wrong_business_heading_is_blocking(self):
        html = BASE.format(cards(), "Fresh pastries and cakes. " * 20).replace(
            "<h1>Fluff Bake Bar</h1>", "<h1>Another Restaurant</h1>")
        result = assess_html(html, business_name="Fluff Bake Bar")
        self.assertFalse(result["passed"])
        self.assertTrue(any("does not exactly match" in issue for issue in result["issues"]))

    def test_missing_phone_is_not_a_failure_when_not_supplied(self):
        result = assess_html(BASE.format(cards(), "Fresh pastries and cakes. " * 20),
                             business_name="Fluff Bake Bar", phone="")
        self.assertTrue(result["passed"], result["issues"])


if __name__ == "__main__":
    unittest.main()
