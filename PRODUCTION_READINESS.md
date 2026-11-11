# Site Factory demo readiness and release policy

## Product purpose
Site Factory generates polished, branded, niche-appropriate **sales-pitch concept websites** for prospective restaurants, cafes, coffee shops, bakeries, and fast-food businesses. These are previews to help win approval, not operational websites. After a prospect approves, the user will confirm business facts and implement operational features manually.

## Content integrity
- Analyze the prospect's public website for business name, niche, logo, brand colours, imagery, visual identity, and readily available factual details.
- Select an appropriate handcrafted template from the template catalogue.
- Exact menu extraction, menu URLs, prices, opening hours, street addresses, ordering links, booking systems, and payment integrations are not prerequisites for generation or review.
- Generate a deterministic, niche-appropriate sample menu without unnecessary AI calls.
- Every sample menu must be visibly labelled as illustrative concept content and state that actual offerings and prices must be confirmed with the business.
- Never present sample items, prices, hours, awards, dietary claims, or business facts as verified.
- Only render contact details, social links, addresses, and hours when supplied by the lead or supported by first-party website evidence.
- Preserve the prospect's logo appearance, ensure suitable contrast, and use high-quality relevant photography.

## Quality gate
A demo passes only when:
- Prospect identity and niche-appropriate template are correct.
- Title, useful meta description, primary heading, and readable copy are present.
- At least five sample menu items and a visible illustrative-content disclaimer are present.
- Visual hierarchy, brand treatment, typography, spacing, and imagery are polished.
- Mobile and desktop checks pass for overflow, broken images, JavaScript errors, repeated images, empty hero copy, and broken navigation anchors.
- Desktop menu layout is usable; mobile and desktop screenshots exist.
- Automated visual review passes. Unavailable/quota-failed visual review is not a pass.
- Deployment is separately verified before claiming a live URL.

Missing real menu data, prices, opening hours, street address, or ordering/booking functionality is not a failure by itself. Missing facts must not be invented.

## Free-tier and safe-run policy
- Use only explicitly free AI models and free-tier allocations.
- Never enable metered/paid Groq or paid OpenRouter models, buy credits, or upgrade provider plans.
- Minimize AI calls; deterministic sample menus must not consume model quota.
- Keep isolated review limited to one prospect per run. Do not launch batches until the isolated demo passes and the user explicitly authorizes a batch.

## Release workflow
1. Run CI (compile, unit tests, template inventory).
2. Run one isolated Fluff Bake Bar concept demo from a clean workspace.
3. Inspect report, screenshots, generated HTML, and artifact evidence.
4. Fix blocking failures and repeat only the isolated demo.
5. Keep PR changes unmerged until the user reviews evidence and explicitly approves merging.
