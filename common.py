import json, os, re, requests
from bs4 import BeautifulSoup

PSI, GEM = os.getenv("PAGESPEED_KEY", ""), os.getenv("GEMINI_API_KEY", "")
GEM_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")  # verify current free-tier model name
UA = {"User-Agent": "Mozilla/5.0 (compatible; SolvexaDemoBot/1.0)"}
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
def slug(n): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", n.lower().replace("é","e").replace("ê","e"))).strip("-")
