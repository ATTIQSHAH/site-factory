import json
import unittest
from unittest.mock import patch, Mock

import provider_router


class ProviderRouterTests(unittest.TestCase):
    def test_only_allowlisted_free_openrouter_models_are_used(self):
        env = {
            "OPENROUTER_API_KEY": "test-key",
            "OPENROUTER_DESIGN_MODELS": "google/gemma-4-31b-it:free,paid/model",
        }
        with patch.dict("os.environ", env, clear=True):
            candidates = provider_router._configured_candidates("design")
        models = [c["model"] for c in candidates if c["provider"] == "openrouter"]
        self.assertIn("google/gemma-4-31b-it:free", models)
        self.assertNotIn("paid/model", models)
        self.assertTrue(all(m.endswith(":free") or m == "openrouter/free" for m in models))

    def test_groq_is_never_configured_even_if_a_key_exists(self):
        with patch.dict("os.environ", {
            "GROQ_API_KEY": "must-not-be-used",
            "GROQ_DESIGN_MODEL": "some-paid-model",
        }, clear=True):
            candidates = provider_router._configured_candidates("design")
        self.assertFalse(any(c["provider"] == "groq" for c in candidates))

    def test_cloudflare_uses_only_free_allowlisted_models(self):
        env = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_AI_API_TOKEN": "cf-token",
            "CLOUDFLARE_DESIGN_MODEL": "@cf/zai-org/glm-4.7-flash",
            "CLOUDFLARE_VISUAL_MODEL": "@cf/meta/llama-3.2-11b-vision-instruct",
        }
        with patch.dict("os.environ", env, clear=True):
            design = provider_router._configured_candidates("design")
            visual = provider_router._configured_candidates("visual")
        self.assertEqual(design[0]["model"], "@cf/zai-org/glm-4.7-flash")
        self.assertEqual(visual[0]["model"], "@cf/meta/llama-3.2-11b-vision-instruct")
        self.assertIn("/accounts/account-id/ai/v1/chat/completions", design[0]["url"])

    @patch("provider_router.requests.post")
    def test_openrouter_429_falls_through_to_cloudflare(self, post):
        limited = Mock(status_code=429, text="rate limited", headers={})
        success = Mock(status_code=200, headers={})
        success.json.return_value = {
            "choices": [{"message": {"content": "<!doctype html><html>ok</html>"}}]
        }
        success.raise_for_status.return_value = None
        post.side_effect = [limited, limited, limited, success]
        env = {
            "OPENROUTER_API_KEY": "or-key",
            "OPENROUTER_DESIGN_MODELS": "google/gemma-4-31b-it:free",
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_AI_API_TOKEN": "cf-token",
            "CLOUDFLARE_DESIGN_MODEL": "@cf/zai-org/glm-4.7-flash",
        }
        with patch.dict("os.environ", env, clear=True):
            result = provider_router.chat_candidates(
                "design", [{"role": "user", "content": "build a page"}]
            )
        self.assertEqual(result["provider"], "cloudflare")
        self.assertEqual(result["model"], "@cf/zai-org/glm-4.7-flash")
        self.assertIn("<html>", result["content"])
        self.assertEqual(post.call_count, 4)

    @patch("provider_router.requests.post")
    def test_invalid_structured_output_moves_to_next_free_model(self, post):
        invalid = Mock(status_code=200, headers={})
        invalid.json.return_value = {"choices": [{"message": {"content": "not json"}}]}
        invalid.raise_for_status.return_value = None
        valid = Mock(status_code=200, headers={})
        valid.json.return_value = {"choices": [{"message": {"content": '{"ok": true}'}}]}
        valid.raise_for_status.return_value = None
        post.side_effect = [invalid, valid]
        env = {
            "OPENROUTER_API_KEY": "or-key",
            "OPENROUTER_DESIGN_MODELS": "google/gemma-4-31b-it:free,dots-studio/dots-3-note-preview:free",
        }
        with patch.dict("os.environ", env, clear=True):
            result = provider_router.chat_candidates(
                "design", [{"role": "user", "content": "test"}],
                validator=json.loads,
            )
        self.assertEqual(result["model"], "dots-studio/dots-3-note-preview:free")
        self.assertEqual(result["validated"], {"ok": True})
        self.assertEqual(post.call_count, 2)


if __name__ == "__main__":
    unittest.main()
