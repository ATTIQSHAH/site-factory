import os
import unittest
import render3
from template_catalog import catalogue, select


class TemplateCatalogueTests(unittest.TestCase):
    def test_discovers_fifty_handcrafted_templates(self):
        rows = catalogue()
        self.assertEqual(len(rows), 50)
        self.assertNotIn('premium.html', [row['file'] for row in rows])

    def test_niche_selection_uses_matching_template_family(self):
        expected = {'coffee': 'coffee_', 'cafe': 'cafe_', 'bakery': 'cafe_', 'fastfood': 'fast_', 'grill': None, 'restaurant': 'rest_'}
        for kind, prefix in expected.items():
            filename, metadata = select(kind, name='Test Business')
            self.assertTrue(os.path.isfile(os.path.join('templates', filename)))
            if prefix:
                self.assertTrue(filename.startswith(prefix), (kind, filename))
            else:
                self.assertTrue(filename.startswith(('fast_', 'rest_')), (kind, filename))
            self.assertEqual(metadata['file'], filename)

    def test_logo_background_is_added_only_when_contrast_requires_it(self):
        light = render3.logo_markup(("img/logo.png", "light"), "Brand", "#f6f1e9")
        dark = render3.logo_markup(("img/logo.png", "dark"), "Brand", "#171210")
        visible = render3.logo_markup(("img/logo.png", "dark"), "Brand", "#f6f1e9")
        self.assertIn("background:#171210", light)
        self.assertIn("background:#ffffff", dark)
        self.assertNotIn("logo-contrast", visible)

    def test_every_template_renders_without_unresolved_tokens(self):
        original_selector = render3.select_template
        data = {
            'name': 'Test Business', 'slug': 'test-business', 'phone': '', 'email': '',
            'address': '', 'city': '', 'hours': [], 'about': '', 'logo': None,
            'photos': [], 'video': None, 'poster': None, 'menu': [], 'menu_url': None,
            'order_url': None, 'ig': '', 'fb': '', 'web': 'https://example.com',
            'kind': 'restaurant',
        }
        try:
            for row in catalogue():
                render3.select_template = lambda *args, _row=row, **kwargs: (_row['file'], _row)
                html, info = render3.build3(data)
                self.assertNotRegex(html, r'\{\{[A-Z0-9_]+\}\}', row['file'])
                self.assertNotRegex(html, r'<p[^>]*>\s*</p>', row['file'])
                self.assertRegex(html, r'<meta name="description"', row['file'])
                self.assertRegex(html, r'<meta name="robots"[^>]+noindex', row['file'])
                self.assertNotRegex(html, r'<div class="story-content">\\s*<section', row['file'])
                self.assertNotRegex(html, r'<div class="menu-container">\\s*<section', row['file'])
                self.assertNotRegex(html, r'<div class="gallery-container">\\s*<section', row['file'])
                self.assertNotRegex(html, r'<div class="visit-hours-content">\\s*<section', row['file'])
                ids = {match for match in __import__('re').findall(r'\\bid=["\\']([^"\\']+)', html)}
                anchors = __import__('re').findall(r'href=["\\']#([^"\\']+)', html)
                self.assertFalse([anchor for anchor in anchors if anchor not in ids], row['file'])
                self.assertEqual(info['template_file'], row['file'])
        finally:
            render3.select_template = original_selector


if __name__ == '__main__':
    unittest.main()
