"""Verify deployment AND deterministic page quality; only ready pages are marked live."""
import csv, os, requests
from site_quality import assess_html

RES = os.getenv("RESULTS", "results/websites_tab.csv")
D = os.path.dirname(RES) or "."


def inspect(url, row):
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code != 200:
            return "not_live_yet", {"score": 0, "status": "not_live", "issues": [f"HTTP {response.status_code}"]}
        quality = assess_html(response.text, row.get("Name", ""), row.get("Phone", ""))
        return ("live" if quality["passed"] else "needs_review"), quality
    except Exception as exc:
        return "not_live_yet", {"score": 0, "status": "not_live", "issues": [str(exc)[:160]]}


rows = list(csv.DictReader(open(RES, encoding="utf-8-sig")))
for row in rows:
    url = row.get("site_url", "").strip()
    if not url:
        continue
    status, quality = inspect(url, row)
    row["live_status"] = status
    row["quality_score"] = str(quality["score"])
    row["quality_status"] = quality["status"]
    row["quality_issues"] = " | ".join(quality["issues"])

cols = list(dict.fromkeys([*("live_status", "quality_score", "quality_status", "quality_issues")] + [c for r in rows for c in r]))


def save(path, selected):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=cols, restval="")
        writer.writeheader()
        writer.writerows(selected)


save(RES, rows)
save(f"{D}/live_leads.csv", [r for r in rows if r.get("live_status") == "live"])
for batch in sorted({r.get("batch") or "1" for r in rows}, key=int):
    save(f"{D}/batch_{batch}_live.csv", [
        r for r in rows if (r.get("batch") or "1") == batch and r.get("live_status") == "live"
    ])
ready = sum(r.get("live_status") == "live" for r in rows)
review = sum(r.get("live_status") == "needs_review" for r in rows)
print(f"{ready} quality-approved live, {review} need review, {len(rows) - ready - review} not live")
