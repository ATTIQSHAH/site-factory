import unittest
from unittest.mock import Mock

from menu_verification import menu_links, verify_menu_destination


class MenuVerificationTests(unittest.TestCase):
    def test_menu_links_resolve_relative_paths_and_ignore_unrelated_links(self):
        html = """
        <a href="/food">View Menu</a>
        <a href="https://example.com/order">Order online</a>
        <a href="/about">About us</a>
        """
        self.assertEqual(
            menu_links(html, "https://bakery.example/"),
            ["https://bakery.example/food", "https://example.com/order"],
        )

    def test_valid_menu_page_is_verified(self):
        response = Mock()
        response.url = "https://example.com/menu"
        response.headers = {"content-type": "text/html"}
        response.text = """
        <html><head><title>Our Menu</title></head><body>
        <h1>Menu</h1><article class="menu-item"><h2>Chocolate Croissant</h2>
        <span class="price">$4.50</span></article>
        <p>Browse our complete selection of pastries, cakes, cookies and drinks.</p>
        </body></html>
        """
        response.raise_for_status.return_value = None
        session = Mock()
        session.get.return_value = response
        result = verify_menu_destination("https://example.com/menu", session=session)
        self.assertTrue(result["verified"])
        session.get.assert_called_once()

    def test_generic_page_does_not_count_as_a_menu(self):
        response = Mock()
        response.url = "https://example.com/order"
        response.headers = {"content-type": "text/html"}
        response.text = "<html><title>Welcome</title><body>" + ("Welcome to our business. " * 20) + "</body></html>"
        response.raise_for_status.return_value = None
        result = verify_menu_destination("https://example.com/order", session=Mock(get=Mock(return_value=response)))
        self.assertFalse(result["verified"])

    def test_http_failure_does_not_verify_destination(self):
        import requests
        session = Mock()
        session.get.side_effect = requests.Timeout("timed out")
        result = verify_menu_destination("https://example.com/menu", session=session)
        self.assertFalse(result["verified"])
        self.assertIn("timed out", result["reason"])

    def test_pdf_requires_a_real_pdf_signature(self):
        response = Mock()
        response.url = "https://example.com/menu.pdf"
        response.headers = {"content-type": "application/pdf"}
        response.content = b"%PDF-1.7 sample"
        response.raise_for_status.return_value = None
        result = verify_menu_destination("https://example.com/menu.pdf", session=Mock(get=Mock(return_value=response)))
        self.assertTrue(result["verified"])


if __name__ == "__main__":
    unittest.main()
