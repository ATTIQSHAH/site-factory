import unittest
from unittest.mock import patch
from types import SimpleNamespace

import media


class GeminiRetryTests(unittest.TestCase):
    def test_rate_limit_retries_with_bounded_backoff(self):
        limited = SimpleNamespace(status_code=429, headers={}, text="quota exhausted")
        success = SimpleNamespace(
            status_code=200,
            headers={},
            text="",
            raise_for_status=lambda: None,
            json=lambda: {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        )
        with patch("media.requests.post", side_effect=[limited, success]) as post, patch("media.time.sleep") as sleep:
            result = media._gemini_response({"contents": []}, 10)
        self.assertEqual(result["candidates"][0]["content"]["parts"][0]["text"], "ok")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_persistent_quota_failure_is_reported_after_three_attempts(self):
        limited = SimpleNamespace(status_code=429, headers={}, text="daily quota exhausted")
        with patch("media.requests.post", return_value=limited) as post, patch("media.time.sleep"):
            with self.assertRaisesRegex(RuntimeError, "HTTP 429"):
                media._gemini_response({"contents": []}, 10)
        self.assertEqual(post.call_count, 3)


if __name__ == "__main__":
    unittest.main()
