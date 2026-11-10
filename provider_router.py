"""Strictly free provider routing for text generation and vision review.

Gemini is called directly by artdir first. Fallbacks are limited to:
- OpenRouter model IDs ending in :free or openrouter/free
- Cloudflare Workers AI models explicitly approved for Workers Free

Metered providers (including Groq) are intentionally not supported here.
"""
import os
import time
import requests

OPENROUTER_FREE_MODELS = {
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "dots-studio/dots-3-note-preview:free",
    "nvidia/nemotron-3.5-super-vl:free",
    "openrouter/free",
}
CLOUDFLARE_FREE_TEXT_MODELS = {
    "@cf/zai-org/glm-4.7-flash",
}
CLOUDFLARE_FREE_VISION_MODELS = {
    "@cf/meta/llama-3.2-11b-vision-instruct",
}


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

    # Enforce free variants even if repository variables are accidentally set
    # to paid model IDs. openrouter/free is the free-model selector.
    if os.getenv("OPENROUTER_API_KEY"):
        defaults = (
            [
                "nvidia/nemotron-3.5-super-vl:free",
                "dots-studio/dots-3-note-preview:free",
                "google/gemma-4-26b-a4b-it:free",
                "openrouter/free",
            ] if visual else [
                "google/gemma-4-31b-it:free",
                "dots-studio/dots-3-note-preview:free",
                "openrouter/free",
            ]
        )
        configured = _model_list(
            os.getenv("OPENROUTER_VISUAL_MODELS" if visual else "OPENROUTER_DESIGN_MODELS"),
            *defaults,
        )
        for model in configured:
            if model not in OPENROUTER_FREE_MODELS:
                print(f"Skipping non-approved/non-free OpenRouter model: {model}", flush=True)
                continue
            candidates.append({
                "provider": "openrouter", "model": model,
                "url": "https://openrouter.ai/api/v1/chat/completions",
                "headers": {
                    "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
                    "Content-Type": "application/json",
                },
            })

    # Cloudflare model IDs are allowlisted by task. This prevents accidental
    # use of models requiring paid billing. Workers Free enforces its daily
    # 10,000-Neuron allocation server-side.
    account = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
    token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    allowed = CLOUDFLARE_FREE_VISION_MODELS if visual else CLOUDFLARE_FREE_TEXT_MODELS
    configured = _model_list(
        os.getenv("CLOUDFLARE_VISUAL_MODELS" if visual else "CLOUDFLARE_DESIGN_MODELS"),
        os.getenv(
            "CLOUDFLARE_VISUAL_MODEL" if visual else "CLOUDFLARE_DESIGN_MODEL",
            "@cf/meta/llama-3.2-11b-vision-instruct" if visual else "@cf/zai-org/glm-4.7-flash",
        ),
    )
    if account and token:
        for model in configured:
            if model not in allowed:
                print(f"Skipping Cloudflare model not approved for free tier/task: {model}", flush=True)
                continue
            candidates.append({
                "provider": "cloudflare", "model": model,
                "url": f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions",
                "headers": {
                    "Authorization": "Bearer " + token,
                    "Content-Type": "application/json",
                },
            })

    unique, seen = [], set()
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
    """Try approved free providers/models in order; validate before accepting."""
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
                result = {"content": content, "provider": candidate["provider"], "model": model}
                if validator is not None:
                    result["validated"] = validator(content)
                print(f'AI {task} provider selected: {candidate["provider"]} / {model}', flush=True)
                return result
            except Exception as exc:
                errors.append(f'{candidate["provider"]}/{model}: {str(exc)[:180]}')
                break
    raise RuntimeError("No configured free AI provider succeeded: " + " | ".join(errors[-12:]))
