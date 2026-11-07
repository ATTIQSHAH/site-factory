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
    def test_visual_critique_falls_back_to_second_openrouter_vision_model(self, post):
        rate_limited = SimpleNamespace(
            status_code=429, text="free model rate limit",
        )
        success = SimpleNamespace(
            status_code=200,
            text="",
            json=lambda: {"choices": [{"message": {"content": '{"score": 8.5, "fixes": ["Improve hero crop"]}'}}]},
            raise_for_status=lambda: None,
        )
        post.side_effect = [rate_limited, success]

        env = {
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "OPENROUTER_VISUAL_MODEL": "google/gemma-4-31b-it:free",
            "OPENROUTER_VISUAL_FALLBACK_MODEL": "dots-studio/dots-3-note-preview:free",
        }
        with patch.dict("os.environ", env, clear=False):
            result = artdir.critique([b"fake-image"], "Fluff Bake Bar")

        self.assertEqual(result["score"], 8.5)
        self.assertEqual(result["provider"], "openrouter")
        self.assertEqual(result["model"], "dots-studio/dots-3-note-preview:free")
        self.assertEqual(result["fixes"], ["Improve hero crop"])
        first_body = post.call_args_list[0].kwargs["json"]
        second_body = post.call_args_list[1].kwargs["json"]
        self.assertEqual(first_body["model"], "google/gemma-4-31b-it:free")
        self.assertEqual(second_body["model"], "dots-studio/dots-3-note-preview:free")
        image_part = second_body["messages"][0]["content"][1]
        self.assertEqual(image_part["type"], "image_url")
        self.assertTrue(image_part["image_url"]["url"].startswith("data:image/jpeg;base64,"))
    @patch("artdir.requests.post")
    def test_empty_primary_vision_response_uses_fallback(self, post):
        empty = SimpleNamespace(
            status_code=200, text="",
            json=lambda: {"choices": [{"message": {"content": None, "reasoning": "internal reasoning"}}]},
            raise_for_status=lambda: None,
        )
        success = SimpleNamespace(
            status_code=200, text="",
            json=lambda: {"choices": [{"message": {"content": '{"score": 9, "fixes": []}'}}]},
            raise_for_status=lambda: None,
        )
        post.side_effect = [empty, success]
        env = {
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "OPENROUTER_VISUAL_MODEL": "google/gemma-4-31b-it:free",
            "OPENROUTER_VISUAL_FALLBACK_MODEL": "dots-studio/dots-3-note-preview:free",
            "OPENROUTER_VISUAL_TERTIARY_MODEL": "google/gemma-4-26b-a4b-it:free",
        }
        with patch.dict("os.environ", env, clear=False):
            result = artdir.critique([b"fake-image"], "Fluff Bake Bar")
        self.assertEqual(result["score"], 9)
        self.assertEqual(result["model"], "dots-studio/dots-3-note-preview:free")
        self.assertEqual(post.call_count, 2)



if __name__ == "__main__":
    unittest.main()
