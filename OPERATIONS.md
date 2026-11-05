# Site Factory Operations

## What the factory is intended to produce

The factory reads business leads, classifies each business using its website content and structured data, selects a matching niche design from the 50-template catalogue, and renders a responsive demo page. The `templates/premium.html` renderer remains the generic fallback.

Business facts must come from the business website, structured data, or supplied lead record. Missing menu items, prices, hours, awards, reviews, and other claims must be omitted rather than guessed. Menu cards are only rendered from extracted source data; a verified external menu/order destination is an acceptable alternative.

## Local setup

1. Use Python 3.12.
2. Create a virtual environment and install the pinned dependencies:

   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

3. Copy `.env.example` to `.env` and set only the integrations you intend to use. Never commit real API keys.

## Controlled single-lead generation

Run a single known lead without processing other rows:

```bash
ONLY_WEBSITE=https://fluffbakebar.com MAX_PER_RUN=1 python factory3.py leads/input.csv
python review_site.py --site sites/fluff-bake-bar --report-dir review/fluff-bake-bar --business "Fluff Bake Bar" --phone "(713) 522-1900" --source-website https://fluffbakebar.com/
```

If the source exposes opening hours, add `--require-hours`. The isolated GitHub Actions workflow does this for Fluff Bake Bar, clears stale output before generation, and uploads the HTML, screenshots, and JSON review report as an artifact.

## Release gates

Do not enable batch generation until all of these are true:

- The isolated demo generated the exact requested lead from a clean workspace.
- CI passes compilation, unit tests, and the 50-template inventory check.
- The generated page has a source-backed menu with at least three distinct items, or a real external menu/order/reservation destination.
- Source-provided opening hours appear in the page; missing hours are never invented.
- The page has the expected phone link and a real street address when required for the business.
- Mobile and desktop browser checks pass with no broken images, JavaScript errors, horizontal overflow, repeated images, dead internal anchors, or overlapping mobile controls.
- Visual review passes. A missing key, quota error, or unavailable visual reviewer is not an approval.

## Batch publishing safety

The nightly workflow has no cron schedule. It is manual-only and has two independent release controls:

1. The workflow-dispatch input `confirm_batch` must be explicitly set to `YES`.
2. The repository variable `BATCH_ENABLED` must be set to `true`.

Keep `BATCH_ENABLED` unset or false until the isolated demo is inspected and approved. The workflow reviews every site in the latest batch before it pushes generated output. A failed review blocks the publish steps.

## GitHub configuration

Store credentials as Actions secrets, not repository files:

- `GEMINI_API_KEY`
- `PEXELS_API_KEY` (optional)
- `PAGESPEED_KEY` (optional)

Use repository variables for non-secret configuration such as `BASE_URL`, `AI_DESIGN`, and the release guard `BATCH_ENABLED`.

Generated demos include a no-index directive and a visible demo disclaimer. Treat them as private sales previews, not approved production websites for the business owner.
