# Site Factory AI providers

Site Factory can use different providers for design generation and screenshot review. Configure only the providers you want to enable; missing providers are skipped automatically.

## Provider order

- Design generation: Gemini, OpenRouter, Groq, Cloudflare Workers AI.
- Screenshot review: Gemini Vision, configured OpenRouter vision models, Groq Vision, Cloudflare vision.
- Publishing remains blocked unless deterministic checks and a real visual review pass.

## GitHub Actions secrets

Add these under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Required values |
| --- | --- |
| `GEMINI_API_KEY` | Existing Google AI Studio key |
| `OPENROUTER_API_KEY` | Existing OpenRouter key |
| `GROQ_API_KEY` | Optional Groq API key |
| `CLOUDFLARE_ACCOUNT_ID` | Optional Cloudflare account ID |
| `CLOUDFLARE_API_TOKEN` | Optional Workers AI API token |

Never commit API keys or paste them into issues, pull requests, or chat.

## Default models

Model IDs can be overridden with repository Actions variables. The defaults are:

- OpenRouter design: `google/gemma-4-31b-it:free`, then `openrouter/free`.
- Groq design and vision: `qwen/qwen3.8-27b`.
- Cloudflare design and vision: `@cf/qwen/qwen3.8-27b`.

Groq and Cloudflare providers are skipped unless their credentials are present. The workflow passes optional model variables through; blank values use the defaults above.

## Cloudflare token

Use the Cloudflare dashboard's **Workers AI → Use REST API → Create a Workers AI API Token** flow. If creating a custom token, Cloudflare's REST API guide specifies Workers AI Read and Workers AI Edit permissions. Store the token as `CLOUDFLARE_API_TOKEN` and the account ID as `CLOUDFLARE_ACCOUNT_ID`.

## Limits and failure behavior

Free tiers and model availability are subject to provider-specific quotas, rate limits, and capacity. A 429 response is treated as a provider failure and the router moves on; it does not imply unlimited free capacity. Empty or malformed output is rejected. If every design provider fails, the existing deterministic template fallback remains available. If every visual provider fails, the quality gate blocks publishing.
