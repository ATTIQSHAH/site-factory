"""Lead CSV -> scrape site -> structure -> render demo site -> audit -> results CSV. Usage: python factory.py leads/input.csv"""
import csv, json, os, re, sys, time, requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from render import build, kind, slug
UA = {"User-Agent": "Mozilla/5.0 (compatible; SolvexaDemoBot/1.0)"}
OUT, RES = os.getenv("SITES_DIR", "sites"), os.getenv("RESULTS", "results/websites_tab.csv")
BASE, MAXN = os.getenv("BASE_URL", "").rstrip("/"), int(os.getenv("MAX_PER_RUN", "30"))
PSI, GEM = os.getenv("PAGESPEED_KEY", ""), os.getenv("GEMINI_API_KEY", "")
GEM_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")  # verify current free-tier model name
def get(u):
    r = requests.get(u, headers=UA, timeout=20); r.raise_for_status(); return r
def ld(soup):
    out = []
    for t in soup.find_all("script", type="application/ld+json"):
        try: d = json.loads(t.string or "")
        except Exception: continue
        for x in (d if isinstance(d, list) else d.get("@graph", [d]) if isinstance(d, dict) else []):
            if isinstance(x, dict): out.append(x)
    return [x for x in out if re.search(r"Restaurant|Cafe|Coffee|Bakery|LocalBusiness|FoodEstablishment", json.dumps(x.get("@type", "")))]
def menu_items(url):
    try: s = BeautifulSoup(get(url).text, "html.parser")
    except Exception: return []
    for t in s(["script", "style", "nav", "footer"]): t.decompose()
    lines = [l.strip() for l in s.get_text("\n").split("\n") if l.strip()]; items = []
    for i, l in enumerate(lines):
        m = re.search(r"\$\s?\d+(?:\.\d{2})?\s*$", l)
        if m and len(l) > len(m.group(0)) + 2:
            items.append({"name": l[:m.start()].strip(" .-–·")[:60], "price": m.group(0).replace(" ", "")})
        elif items and not items[-1].get("desc") and re.search(r"\$", lines[i + 1] if i + 1 < len(lines) else "") and 15 < len(l) < 140 and not re.search(r"\$", l):
            pass
    return items[:8]
def extract(url):
    r = get(url); soup = BeautifulSoup(r.text, "html.parser"); base = r.url; d = {"html": r.text}
    meta = lambda p: (soup.find("meta", attrs={"property": p}) or soup.find("meta", attrs={"name": p}) or {}).get("content", "")
    d["about"] = (meta("og:description") or meta("description")).strip()[:300]; d["title"] = (soup.title.string or "").strip() if soup.title else ""
    biz = (ld(soup) or [{}])[0]; a = biz.get("address") if isinstance(biz.get("address"), dict) else {}
    d["address"] = ", ".join(str(a[x]) for x in ("streetAddress", "addressLocality", "addressRegion", "postalCode") if a.get(x))
    oh = biz.get("openingHours"); d["hours"] = " | ".join(oh) if isinstance(oh, list) else (oh or "")
    lg = biz.get("logo"); lg = lg.get("url") if isinstance(lg, dict) else lg
    if not lg:
        for im in soup.find_all("img"):
            if re.search(r"logo", " ".join([*(im.get("class") or []), im.get("id") or "", im.get("alt") or "", im.get("src") or ""]), re.I) and im.get("src"):
                lg = im["src"]; break
    if not lg:
        ic = soup.find("link", rel=lambda v: v and "apple-touch-icon" in v); lg = ic.get("href") if ic else None
    d["logo"] = urljoin(base, lg) if lg else ""
    ph = [meta("og:image")] + [im.get("src") for im in soup.find_all("img") if im.get("src") and re.search(r"hero|banner|gallery|food|slide", im["src"], re.I) and not re.search(r"logo|icon", im["src"], re.I)]
    d["photos"] = [urljoin(base, p) for p in dict.fromkeys(x for x in ph if x)][:3]
    ml = next((urljoin(base, x["href"]) for x in soup.find_all("a", href=True) if re.search(r"menu", x["href"] + x.get_text(), re.I) and not x["href"].lower().endswith(".pdf")), None)
    d["menu"] = menu_items(ml) if ml else []
    d["menu_pdf"] = any(x["href"].lower().endswith(".pdf") and "menu" in x["href"].lower() for x in soup.find_all("a", href=True))
    return d
def ai_about(name, facts):
    if not GEM or not facts: return facts
    try:
        p = f"Write a warm 2-sentence About blurb for {name}. Use ONLY these facts, invent nothing: {facts}. Return plain text."
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEM_MODEL}:generateContent?key={GEM}", json={"contents": [{"parts": [{"text": p}]}]}, timeout=30)
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception: return facts
def audit(url, html):
    s = BeautifulSoup(html, "html.parser"); low = html.lower(); iss, fix = [], []
    perf = seo = ""
    try:
        q = requests.get("https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params={"url": url, "strategy": "mobile", "category": ["performance", "seo"], **({"key": PSI} if PSI else {})}, timeout=90).json()["lighthouseResult"]["categories"]
        perf, seo = round(q["performance"]["score"] * 100), round(q["seo"]["score"] * 100)
        if perf < 60: iss.append(f"Slow on mobile (speed score {perf}/100)"); fix.append("Lightweight, fast-loading pages")
    except Exception: pass
    if not s.find("meta", attrs={"name": "viewport"}): iss.append("Not set up for mobile screens"); fix.append("Fully mobile-friendly layout")
    if not url.startswith("https"): iss.append("Not served over HTTPS"); fix.append("Secure HTTPS hosting")
    if not s.find("meta", attrs={"name": "description"}): iss.append("Missing search description"); fix.append("Search-friendly title and description")
    if "tel:" not in low: iss.append("No tap-to-call button for phone orders"); fix.append("One-tap Call and Email buttons")
    if not re.search(r"order|doordash|ubereats|toasttab|opentable|reserv", low): iss.append("No clear online ordering or reservation path"); fix.append("Prominent contact and menu sections")
    if not s.find("script", type="application/ld+json"): iss.append("No structured business data for Google"); 
    return perf, seo, iss[:4], fix[:4]
def main(src):
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig"))); done = {}
    if os.path.exists(RES): done = {r["Website"]: r for r in csv.DictReader(open(RES, encoding="utf-8"))}
    new = [r for r in rows if r.get("Website") and r["Website"] not in done][:MAXN]; os.makedirs(OUT, exist_ok=True); used = {r["site_path"] for r in done.values()}
    for r in new:
        res = dict(r); u = r["Website"].strip()
        try:
            d = extract(u); res["fetch_status"] = "ok"
            nm = r.get("Name") or d["title"].split("|")[0].strip(); r["Name"] = nm; k = kind(nm)
            r.update({x: d[x] for x in ("logo", "photos", "menu", "address", "hours")}); r["about"] = ai_about(nm, d["about"])
            s = slug(nm); n = 2; base_s = s
            while f"/{s}/" in used: s = f"{base_s}-{n}"; n += 1
            used.add(f"/{s}/"); os.makedirs(f"{OUT}/{s}", exist_ok=True); open(f"{OUT}/{s}/index.html", "w", encoding="utf-8").write(build(r, k))
            perf, seo, iss, fix = audit(u, d["html"])
            res.update({"template": k, "site_path": f"/{s}/", "site_url": f"{BASE}/{s}/" if BASE else "", "audit_perf": perf, "audit_seo": seo, "audit_issues": " | ".join(iss), "improvements_made": " | ".join(fix),
                        "logo_found": bool(d["logo"]), "menu_found": len(d["menu"]) >= 3, "menu_pdf_only": d["menu_pdf"] and len(d["menu"]) < 3, "address_found": bool(d["address"]), "photos_found": len(d["photos"]),
                        "qa_flag": "check: no logo/photos" if not d["logo"] and not d["photos"] else ("check: no menu" if len(d["menu"]) < 3 else "ok")})
        except Exception as ex: res.update({"fetch_status": f"failed: {str(ex)[:80]}", "qa_flag": "needs manual build"})
        res.update({"review_status": "pending", "email_status": ""}); done[u] = res; time.sleep(2); print(res.get("Name", u), res["fetch_status"])
    allr = list(done.values()); cols = list(dict.fromkeys(c for r in allr for c in r)); os.makedirs(os.path.dirname(RES) or ".", exist_ok=True)
    with open(RES, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows(allr)
if __name__ == "__main__": main(sys.argv[1])
