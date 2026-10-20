# Solvexa Site Factory
Lead CSV (needs a `Website` column; `Name`, `Email`, `Phone`, `Instagram`, `Facebook` optional) -> scrape -> demo site -> audit -> `results/websites_tab.csv`.

## Setup (one time, all free)
1. Create a private GitHub repo, push this folder. Put your leads in `leads/input.csv`.
2. Repo Settings > Secrets and variables > Actions: add secrets `PAGESPEED_KEY` (Google Cloud API key, PageSpeed Insights API) and `GEMINI_API_KEY` (Google AI Studio, optional). Add variable `BASE_URL` = your Pages URL (e.g. https://yourproject.pages.dev).
3. Cloudflare Pages > Create project > Connect to Git > this repo. Build command: none. Build output directory: `sites`.
4. Actions tab > nightly-site-factory > Run workflow (or wait for the 21:00 UTC schedule). Each run builds up to 30 new leads and skips ones already done.
5. Import `results/websites_tab.csv` into your message generator / CRM sheet.

## Review before sending
Check rows where `qa_flag` is not `ok` or `fetch_status` starts with `failed`; set `review_status` to approved.
Local run: `pip install -r requirements.txt && python factory.py leads/input.csv`
