# Template library
- Templates live in `library/` (one .j2 file each) and are listed in `library/index.json`.
- Each entry: id, direction, types, status (new / approved / rejected), uses, score.
- A template is reused until `uses` reaches TEMPLATE_MAX_USES (default 3). Then a new template is designed automatically.
- Review: open a few sites built with a `new` template (results column `template_id`). Good: edit index.json and change "new" to "approved". Bad: change it to "rejected" and it will never be used again.
- Set the GitHub variable DESIGN_MODE to `library` to switch this on. The Gemini key is required.
