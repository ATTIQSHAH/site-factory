import unittest
from unittest.mock import patch
from types import SimpleNamespace

import artdir


class GeminiPayloadTests(unittest.TestCase):
    @patch("artdir.requests.post")
    def test_visual_critique_uses_current_gemini_rest_field_names(self, post):
        payload = {
            "candidates": [{
                "content": {
                    "parts": [{"text": '{"score": 8, "fixes": []}'}]
                }
            }]
        }
        post.return_value = SimpleNamespace(
            ok=True,
            status_code=200,
            text="",
            json=lambda: payload,
        )

        with patch.object(artdir, "KEY", "test-key"):
            result = artdir.critique([b"fake-image"], "Fluff Bake Bar")

        body = post.call_args.kwargs["json"]
        self.assertEqual(result["score"], 8)
        self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
        self.assertNotIn("response_mime_type", body["generationConfig"])
        image_part = body["contents"][0]["parts"][1]
        self.assertIn("inlineData", image_part)
        self.assertEqual(image_part["inlineData"]["mimeType"], "image/jpeg")
        self.assertNotIn("inline_data", image_part)


if __name__ == "__main__":
    unittest.main()
