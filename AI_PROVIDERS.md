# Site Factory AI providers

Site Factory uses AI only where it materially improves a sales-pitch concept website. Deterministic template selection, sample-menu generation, content labels, and browser checks do not require AI.

## Allowed providers
- Gemini Free Tier.
- OpenRouter models explicitly ending in `:free`, or `openrouter/free`.
- Cloudflare Workers AI within the account's free allocation.
- Groq is disabled and must not be configured or used.

## GitHub Actions secrets
Configure secrets under **Settings → Secrets and variables → Actions → Secrets**:
- `GEMINI_API_KEY`
- `OPENROUTER_API_KEY`
- `CLOUDFLARE_ACCOUNT_ID`
- `CLOUDFLARE_AI_API_TOKEN` (Workers AI token)

Never commit API keys or paste them into issues, pull requests, or chat.

## Usage safeguards
- Never select paid OpenRouter models, enable metered Groq, purchase credits, or upgrade plans.
- Prefer deterministic fallback templates when no free design provider is available.
- Sample menus are generated locally and must not invoke AI menu extraction.
- Keep one isolated demo per run. Avoid parallel generation, unnecessary retries, and repeated visual critique calls.
- The final quality gate must fail closed when automated visual review is unavailable or quota-limited.
- Provider free-tier quotas and availability can change; do not assume a configured key means remaining quota is available.
