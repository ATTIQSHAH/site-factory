import unittest
from unittest.mock import patch
from types import SimpleNamespace

import artdir


class GeminiPayloadTests(unittest.TestCase):
    @patch("artdir.requests.post")
    def test_gem_retries_transient_service_unavailable(self, post):
        unavailable = SimpleNamespace(
            ok=False, status_code=503, text="high demand", headers={},
            json=lambda: {"error": {"message": "high demand"}},
        )
        success = SimpleNamespace(
            ok=True, status_code=200, text="", headers={},
            json=lambda: {"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}]},
        )
        post.side_effect = [unavailable, success]
        with patch.object(artdir, "KEY", "test-key"), patch.object(artdir.time, "sleep"):
            result = artdir.gem([{"text": "test"}], js=True)
        self.assertEqual(result, {"ok": True})
        self.assertEqual(post.call_count, 2)

    @patch("artdir.requests.post")
    def test_quota_exhausted_429_is_not_retried(self, post):
        exhausted = SimpleNamespace(
            ok=False, status_code=429, text="quota exhausted", headers={},
            json=lambda: {"error": {"message": "quota exhausted", "details": []}},
        )
        post.return_value = exhausted
        with patch.object(artdir, "KEY", "test-key"), patch.object(artdir.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "Gemini HTTP 429"):
                artdir.gem([{"text": "test"}], js=True)
        self.assertEqual(post.call_count, 1)

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
