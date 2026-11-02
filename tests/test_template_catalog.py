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
                self.assertEqual(info['template_file'], row['file'])
        finally:
            render3.select_template = original_selector


if __name__ == '__main__':
    unittest.main()
