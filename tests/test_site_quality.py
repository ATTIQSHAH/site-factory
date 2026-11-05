import unittest
from site_quality import assess_html


BASE = """<!doctype html><html><head><title>Fluff Bake Bar</title>
<meta name="description" content="A bakery serving pastries, cakes and cookies made fresh every day.">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex,nofollow"></head><body>
<header><h1>Fluff Bake Bar</h1><a href="https://example.com/menu">Menu</a><a href="tel:+17135221900">Call</a></header>
<main id="menu"><p>{}</p></main></body></html>"""


class SiteQualityTests(unittest.TestCase):
    def test_complete_page_passes(self):
        result = assess_html(BASE.format("Fresh pastries and cakes. " * 20),
                             business_name="Fluff Bake Bar", phone="(713) 522-1900")
        self.assertTrue(result["passed"], result["issues"])
        self.assertEqual(result["status"], "ready")

    def test_http_200_is_not_enough_when_content_is_missing(self):
        result = assess_html("<html><body><h1>Fluff Bake Bar</h1></body></html>",
                             business_name="Fluff Bake Bar")
        self.assertFalse(result["passed"])
        self.assertEqual(result["status"], "needs_review")

    def test_unresolved_placeholders_fail_gate(self):
        result = assess_html(BASE.format("Fresh pastries. " * 30).replace(
            "</main>", "{{BUSINESS_ADDRESS}}</main>"),
            business_name="Fluff Bake Bar")
        self.assertFalse(result["passed"])
        self.assertTrue(any("placeholder" in x for x in result["issues"]))

    def test_empty_hero_and_junk_location_are_rejected(self):
        html = BASE.format("Fresh pastries and cakes. " * 20).replace(
            '<meta name="description" content="A bakery serving pastries, cakes and cookies made fresh every day.">', ""
        ).replace("<h1>Fluff Bake Bar</h1>", '<h1>Fluff Bake Bar</h1>').replace("</header>", '</header><section class="hero"><p></p><span class="chip">n</span></section>')
        result = assess_html(html, business_name="Fluff Bake Bar", phone="(713) 522-1900")
        self.assertFalse(result["passed"])
        self.assertTrue(any("empty description" in x for x in result["issues"]))
        self.assertTrue(any("one-character" in x for x in result["issues"]))

    def test_missing_expected_phone_is_flagged(self):
        result = assess_html(BASE.format("Fresh pastries and cakes. " * 20).replace(
            "tel:+17135221900", "tel:+10000000000"),
            business_name="Fluff Bake Bar", phone="(713) 522-1900")
        self.assertTrue(any("phone number missing" in x for x in result["issues"]))
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
