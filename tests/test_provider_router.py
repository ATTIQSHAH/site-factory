import unittest
from unittest.mock import patch, Mock

import provider_router


class ProviderRouterTests(unittest.TestCase):
    def test_groq_is_enabled_only_with_key_and_model(self):
        with patch.dict("os.environ", {
            "GROQ_API_KEY": "test-key",
            "GROQ_DESIGN_MODEL": "llama-3.3-70b-versatile",
        }, clear=True):
            candidates = provider_router._configured_candidates("design")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["provider"], "groq")
        self.assertEqual(candidates[0]["model"], "llama-3.3-70b-versatile")

    @patch("provider_router.requests.post")
    def test_router_moves_from_openrouter_429_to_groq(self, post):
        limited = Mock(status_code=429, text="rate limited", headers={})
        success = Mock(status_code=200, headers={})
        success.json.return_value = {
            "choices": [{"message": {"content": "<!doctype html><html>ok</html>"}}]
        }
        success.raise_for_status.return_value = None
        post.side_effect = [limited, success]
        env = {
            "OPENROUTER_API_KEY": "or-key",
            "OPENROUTER_DESIGN_MODEL": "model-a:free",
            "OPENROUTER_DESIGN_FALLBACK_MODEL": "model-b:free",
            "GROQ_API_KEY": "groq-key",
            "GROQ_DESIGN_MODEL": "qwen/qwen3.8-27b",
        }
        with patch.dict("os.environ", env, clear=True):
            result = provider_router.chat_candidates(
                "design", [{"role": "user", "content": "build a page"}]
            )
        self.assertEqual(result["provider"], "groq")
        self.assertEqual(result["model"], "qwen/qwen3.8-27b")
        self.assertIn("<html>", result["content"])
        self.assertEqual(post.call_count, 2)

    def test_cloudflare_requires_account_token_and_task_model(self):
        env = {
            "CLOUDFLARE_ACCOUNT_ID": "account-id",
            "CLOUDFLARE_API_TOKEN": "cf-token",
            "CLOUDFLARE_VISUAL_MODEL": "@cf/meta/llama-4-scout-17b-16e-instruct",
        }
        with patch.dict("os.environ", env, clear=True):
            candidates = provider_router._configured_candidates("visual")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["provider"], "cloudflare")
        self.assertIn("/accounts/account-id/ai/v1/chat/completions", candidates[0]["url"])


if __name__ == "__main__":
    unittest.main()
