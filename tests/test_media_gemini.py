import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image
import media


class MediaGeminiPayloadTests(unittest.TestCase):
    @patch("media.requests.post")
    def test_menu_extraction_uses_current_rest_field_names(self, post):
        post.return_value = SimpleNamespace(json=lambda: {
            "candidates": [{"content": {"parts": [{"text": json.dumps([
                {"name": "Chocolate Chip Cookie", "price": "$3.25"}
            ])}]}}]
        })
        with patch.object(media, "GEM", "test-key"):
            items = media.gemini_menu(b"menu-bytes", "application/pdf")
        body = post.call_args.kwargs["json"]
        self.assertEqual(items[0]["name"], "Chocolate Chip Cookie")
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        part = body["contents"][0]["parts"][1]
        self.assertEqual(part["inlineData"]["mimeType"], "application/pdf")
        self.assertNotIn("inline_data", part)
        self.assertNotIn("response_mime_type", body["generationConfig"])

    @patch("media.requests.post")
    def test_image_label_uses_current_rest_field_names(self, post):
        post.return_value = SimpleNamespace(json=lambda: {
            "candidates": [{"content": {"parts": [{"text": "food"}]}}]
        })
        with patch.object(media, "GEM", "test-key"), patch.object(media.time, "sleep"):
            label = media.label(Image.new("RGB", (80, 80), "white"))
        body = post.call_args.kwargs["json"]
        self.assertEqual(label, "food")
        part = body["contents"][0]["parts"][1]
        self.assertEqual(part["inlineData"]["mimeType"], "image/jpeg")
        self.assertNotIn("inline_data", part)


if __name__ == "__main__":
    unittest.main()
