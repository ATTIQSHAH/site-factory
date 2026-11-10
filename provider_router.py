"""Provider fallback routing for text generation and vision review.

Optional providers are activated only when credentials and model IDs are configured.
"""
import os
import time
import requests


def _configured_candidates(task):
    candidates = []
    if os.getenv("OPENROUTER_API_KEY"):
        if task == "visual":
            models = [
                os.getenv("OPENROUTER_VISUAL_MODEL", "google/gemma-4-31b-it:free"),
                os.getenv("OPENROUTER_VISUAL_FALLBACK_MODEL", "dots-studio/dots-3-note-preview:free"),
                os.getenv("OPENROUTER_VISUAL_TERTIARY_MODEL", "google/gemma-4-26b-a4b-it:free"),
                os.getenv("OPENROUTER_VISUAL_QUATERNARY_MODEL", "nvidia/nemotron-3.5-super-vl:free"),
                os.getenv("OPENROUTER_VISUAL_ROUTER_MODEL", "openrouter/free"),
            ]
        else:
            models = [
                (os.getenv("OPENROUTER_DESIGN_MODEL") or "google/gemma-4-31b-it:free"),
                (os.getenv("OPENROUTER_DESIGN_FALLBACK_MODEL") or "openrouter/free"),
            ]
        for model in dict.fromkeys(models):
            candidates.append({
                "provider": "openrouter", "model": model,
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "headers": {"Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                            "Content-Type": "application/json"},
            })

    groq_model = (os.getenv("GROQ_VISUAL_MODEL" if task == "visual" else "GROQ_DESIGN_MODEL") or "qwen/qwen3.8-27b").strip()
    if os.getenv("GROQ_API_KEY") and groq_model:
        candidates.append({
            "provider": "groq", "model": groq_model,
            "url": "https://api.groq.com/openai/v1/chat/completions",
            "headers": {"Authorization": "Bearer " + os.environ["GROQ_API_KEY"],
                        "Content-Type": "application/json"},
        })

    cf_model = (os.getenv("CLOUDFLARE_VISUAL_MODEL" if task == "visual" else "CLOUDFLARE_DESIGN_MODEL") or "@cf/qwen/qwen3.8-27b").strip()
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    if account and token and cf_model:
        candidates.append({
            "provider": "cloudflare", "model": cf_model,
            "url": f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions",
            "headers": {"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        })
    return candidates


def has_credentials(task="visual"):
    return bool(_configured_candidates(task)) or bool(os.getenv("GEMINI_API_KEY"))


def chat_candidates(task, messages, max_tokens=12000, timeout=180, exclude_providers=()):
    """Try compatible providers in order; return content and provider provenance."""
    errors = []
    for candidate in _configured_candidates(task):
        if candidate["provider"] in set(exclude_providers):
            continue
        model = candidate["model"]
        for attempt in range(2):
            try:
                response = requests.post(
                    candidate["url"], headers=candidate["headers"],
                    json={"model": model, "messages": messages,
                          "temperature": 0.2, "max_tokens": max_tokens},
                    timeout=timeout,
                )
                if response.status_code == 429:
                    errors.append(f'{candidate["provider"]}/{model}: HTTP 429 rate limited')
                    break
                if response.status_code in (408, 425) or response.status_code >= 500:
                    if attempt == 0:
                        try: delay = float(response.headers.get("Retry-After", ""))
                        except (TypeError, ValueError): delay = 2
                        time.sleep(min(max(delay, 1), 5))
                        continue
                response.raise_for_status()
                payload = response.json()
                choices = payload.get("choices") or []
                message = choices[0].get("message") if choices else None
                if not isinstance(message, dict):
                    raise ValueError("No assistant message in provider response")
                content = message.get("content")
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") for part in content
                        if isinstance(part, dict) and isinstance(part.get("text"), str)
                    )
                if not isinstance(content, str) or not content.strip():
                    content = message.get("reasoning")
                if not isinstance(content, str) or not content.strip():
                    raise ValueError("Provider returned empty text")
                return {"content": content.strip(), "provider": candidate["provider"], "model": model}
            except Exception as exc:
                errors.append(f'{candidate["provider"]}/{model}: {str(exc)[:180]}')
                break
    raise RuntimeError("No compatible AI provider succeeded: " + " | ".join(errors[-8:]))
