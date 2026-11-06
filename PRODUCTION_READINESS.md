# Production readiness and release policy

## Current status

This repository is under hardening. It is not approved for unattended batch generation or public production publishing until the isolated Fluff Bake Bar review passes from a clean run.

## Release requirements

- The lead selector must honor `ONLY_WEBSITE` as an exact URL match and fail closed if zero or multiple leads match.
- The 50 handcrafted niche templates must be selected through the catalogue, with `premium.html` retained as a fallback.
- Business classification must combine the website title, description, headings, structured data, and extracted menu evidence. The classification and chosen template must be recorded in results.
- Menu items and prices must be source-backed. Suspicious repeated prices are suppressed; an external menu/order destination is acceptable when item extraction is unavailable.
- Opening hours must only be rendered when reliably extracted. Missing hours are reported, never invented.
- A generated page must have a real menu/order/reservation path, valid click-to-call contact, source-backed business identity, and no unresolved placeholders.
- Mobile and desktop browser checks must pass for overflow, broken images, JS errors, repeated imagery, broken internal anchors, and CTA overlap.
- Visual-review API errors, including quota exhaustion, are a failed/unavailable review—not a pass. Human review is required when automated visual review cannot run.
- The isolated demo must regenerate from a clean directory and its report must identify the exact business and source URL.
- Nightly/batch scheduling stays disabled until the isolated demo passes all deterministic and visual gates.

## Operating model

1. Run CI (compile, unit tests, and template inventory).
2. Run the isolated Fluff Bake Bar workflow from a clean workspace.
3. Inspect the generated screenshots, HTML, source evidence, and JSON report.
4. Fix every blocking failure and repeat the isolated run.
5. Only after an explicit PASS, consider enabling batch generation behind a separate approval step.
