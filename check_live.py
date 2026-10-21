"""Checks which site_urls are really live on Cloudflare; writes live-only CSVs (batch_N_live.csv + live_leads.csv)."""
import csv, os, requests
RES = os.getenv("RESULTS", "results/websites_tab.csv"); D = os.path.dirname(RES) or "."
def live(u):
    try:
        r = requests.get(u, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        return r.status_code == 200 and 'name="robots" content="noindex,nofollow"' in r.text
    except Exception: return False
rows = list(csv.DictReader(open(RES, encoding="utf-8")))
for r in rows:
    if r.get("site_url") and r.get("live_status") != "live": r["live_status"] = "live" if live(r["site_url"]) else "not_live_yet"
cols = list(dict.fromkeys(["live_status"] + [c for r in rows for c in r]))
def save(p, rs):
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows(rs)
save(RES, rows); save(f"{D}/live_leads.csv", [r for r in rows if r["live_status"] == "live"])
for b in sorted({r.get("batch") or "1" for r in rows}, key=int): save(f"{D}/batch_{b}_live.csv", [r for r in rows if (r.get("batch") or "1") == b and r["live_status"] == "live"])
print(sum(r["live_status"] == "live" for r in rows), "live of", len(rows))
