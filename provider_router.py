"""Provider fallback routing for text generation and vision review.

Gemini is called directly by artdir first. This module routes compatible
OpenAI-style requests through OpenRouter, Groq, and Cloudflare in that order.
Providers are optional: only configured credentials/models are attempted.
"""
import os
import time
import requests


def _model_list(*values):
    result = []
    for value in values:
        for item in str(value or "").replace(";", ",").split(","):
            item = item.strip()
            if item and item not in result:
                result.append(item)
    return result


def _configured_candidates(task):
    candidates = []
    visual = task == "visual"

    # OpenRouter free vision models first for review. The free router is a
    # final option because its selected model can change from request to request.
    if os.getenv("OPENROUTER_API_KEY"):
        if visual:
            models = _model_list(
                os.getenv("OPENROUTER_VISUAL_MODELS"),
                os.getenv("OPENROUTER_VISUAL_MODEL", "nvidia/nemotron-3.5-super-vl:free"),
                os.getenv("OPENROUTER_VISUAL_FALLBACK_MODEL", "dots-studio/dots-3-note-preview:free"),
                os.getenv("OPENROUTER_VISUAL_TERTIARY_MODEL", "google/gemma-4-26b-a4b-it:free"),
                os.getenv("OPENROUTER_VISUAL_QUATERNARY_MODEL"),
                os.getenv("OPENROUTER_VISUAL_ROUTER_MODEL", "openrouter/free"),
            )
        else:
            models = _model_list(
                os.getenv("OPENROUTER_DESIGN_MODELS"),
                os.getenv("OPENROUTER_DESIGN_MODEL", "google/gemma-4-31b-it:free"),
                os.getenv("OPENROUTER_DESIGN_FALLBACK_MODEL", "openrouter/free"),
            )
        for model in models:
            candidates.append({
                "provider": "openrouter", "model": model,
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "headers": {
                    "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                    "Content-Type": "application/json",
                },
            })

    # Qwen 3.8 27B supports both text and image input on Groq. Groq usage is
    # metered by its plan; this is an optional fallback, not an assumed-free API.
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    groq_models = _model_list(
        os.getenv("GROQ_VISUAL_MODELS" if visual else "GROQ_DESIGN_MODELS"),
        os.getenv("GROQ_VISUAL_MODEL" if visual else "GROQ_DESIGN_MODEL", "qwen/qwen3.8-27b"),
    )
    if groq_key:
        for model in groq_models:
            candidates.append({
                "provider": "groq", "model": model,
                "url": "https://api.groq.com/openai/v1/chat/completions",
                "headers": {
                    "Authorization": "Bearer " + groq_key,
                    "Content-Type": "application/json",
                },
            })

    # Cloudflare model IDs differ by task and model capability. Require an
    # explicit model setting; never guess a vision-capable model.
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    cf_models = _model_list(
        os.getenv("CLOUDFLARE_VISUAL_MODELS" if visual else "CLOUDFLARE_DESIGN_MODELS"),
        os.getenv("CLOUDFLARE_VISUAL_MODEL" if visual else "CLOUDFLARE_DESIGN_MODEL"),
    )
    if account and token:
        for model in cf_models:
            candidates.append({
                "provider": "cloudflare", "model": model,
                "url": f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions",
                "headers": {
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                },
            })

    # Keep order while avoiding duplicate provider/model attempts.
    unique = []
    seen = set()
    for candidate in candidates:
        identity = (candidate["provider"], candidate["model"])
        if identity not in seen:
            seen.add(identity)
            unique.append(candidate)
    return unique


def has_credentials(task="visual"):
    return bool(_configured_candidates(task)) or bool(os.getenv("GEMINI_API_KEY"))


def chat_candidates(task, messages, max_tokens=12000, timeout=180,
                    exclude_providers=(), validator=None):
    """Try providers/models in order; optionally validate before accepting output."""
    errors = []
    excluded = set(exclude_providers)
    for candidate in _configured_candidates(task):
        if candidate["provider"] in excluded:
            continue
        model = candidate["model"]
        for attempt in range(2):
            try:
                response = requests.post(
                    candidate["url"], headers=candidate["headers"],
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0 if task == "visual" else 0.2,
                        "max_tokens": max_tokens,
                    },
                    timeout=timeout,
                )
                if response.status_code == 429:
                    errors.append(f'{candidate["provider"]}/{model}: HTTP 429 rate limited')
                    break
                if response.status_code in (408, 425) or response.status_code >= 500:
                    if attempt == 0:
                        try:
                            delay = float(response.headers.get("Retry-After", ""))
                        except (TypeError, ValueError):
                            delay = 2
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
                content = content.strip()
                result = {
                    "content": content,
                    "provider": candidate["provider"],
                    "model": model,
                }
                if validator is not None:
                    result["validated"] = validator(content)
                print(
                    f'AI {task} provider selected: {candidate["provider"]} / {model}',
                    flush=True,
                )
                return result
            except Exception as exc:
                errors.append(f'{candidate["provider"]}/{model}: {str(exc)[:180]}')
                break
    raise RuntimeError("No compatible AI provider succeeded: " + " | ".join(errors[-12:]))
