"""v3: lead CSV -> real extraction (photos, logo, menu incl. AI reading, address, hours) -> themed premium site -> audit -> results CSV."""
import csv, os, re, sys, time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import media, artdir
from collections import Counter
USED = Counter()
from common import get, ld, audit, ai_about, slug
from render3 import build3, niche
OUT, RES = os.getenv("SITES_DIR", "sites"), os.getenv("RESULTS", "results/websites_tab.csv")
BASE, MAXN = os.getenv("BASE_URL", "").rstrip("/"), int(os.getenv("MAX_PER_RUN", "30"))
BAD = re.compile(r"^(add|make it|extra|sub|substitute|no |with |choice of|side of)\b", re.I)
DAY = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*"
def menu_text(h):
    s = BeautifulSoup(h, "html.parser")
    for t in s(["script", "style", "nav", "footer", "header"]): t.decompose()
    items, cur, seen = [], "", set()
    for l in [x.strip() for x in s.get_text("\n").split("\n") if x.strip()]:
        m = re.search(r"(\$\s?\d+(?:\.\d{2})?[\s|/$\d.]*)$", l)
        if m:
            nm = l[:m.start()].strip(" .-–·$|"); pr = " / ".join(re.sub(r"\s", "", p) for p in re.findall(r"\$\s?\d+(?:\.\d{2})?", m.group(1))[:2])
            if 3 <= len(nm) <= 60 and len(re.findall(r"[A-Za-z]", nm)) >= 3 and "$" not in nm and not BAD.match(nm) and nm.lower() not in seen: seen.add(nm.lower()); items.append({"section": cur, "name": nm, "price": pr, "desc": ""})
        elif 2 < len(l) < 30 and not re.search(r"\d|@|http", l): cur = l.title()
        elif items and not items[-1]["desc"] and 15 < len(l) < 160 and "$" not in l: items[-1]["desc"] = l
    return items[:24] if len(items) >= 5 else []
def get_menu(soup, base):
    link = next((urljoin(base, a["href"]) for a in soup.find_all("a", href=True) if re.search(r"menu", a["href"] + a.get_text(), re.I) and not a["href"].lower().endswith(".pdf") and "order" not in a.get_text().lower()), None)
    pages, items, src = [soup], [], "none"
    if link:
        try: r = get(link); items = menu_text(r.text); pages.append(BeautifulSoup(r.text, "html.parser"))
        except Exception: pass
        src = "text" if items else "link"
    if not items:
        pdfs = list(dict.fromkeys(urljoin(base, a["href"]) for p in pages for a in p.find_all("a", href=True) if a["href"].lower().split("?")[0].endswith(".pdf") and "menu" in a["href"].lower()))
        imgs = list(dict.fromkeys(urljoin(base, i.get("src")) for p in pages for i in p.find_all("img") if i.get("src") and re.search(r"menu", i["src"] + (i.get("alt") or ""), re.I) and re.search(r"\.(jpe?g|png|webp)", i["src"], re.I)))
        for u, mime in [(x, "application/pdf") for x in pdfs[:2]] + [(x, "image/jpeg") for x in imgs[:2]]:
            data, ct = media.dl(u); items = media.gemini_menu(data, "application/pdf" if mime == "application/pdf" else (ct.split(";")[0] or mime))
            if len(items) >= 5: src = "ai"; link = link or u; break
            items = []
        if not items and pdfs and not link: link, src = pdfs[0], "link"
    return items, link, src
def hours_of(biz, text):
    oh = biz.get("openingHours"); oh = [oh] if isinstance(oh, str) else (oh or []); rows = []
    for x in oh:
        m = re.match(r"([A-Za-z,\- ]+?)\s+(\d{1,2}:\d{2}-\d{1,2}:\d{2})", x)
        if m: rows.append((re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su)\b", lambda k: {"Mo": "Mon", "Tu": "Tue", "We": "Wed", "Th": "Thu", "Fr": "Fri", "Sa": "Sat", "Su": "Sun"}[k.group(1)], m.group(1).strip()).replace("-", " to "), m.group(2).replace("-", " to ")))
    def t12(x): return re.sub(r"\b(\d{1,2}):(\d{2})\b", lambda k: (str(int(k.group(1)) % 12 or 12) + ("" if k.group(2) == "00" else ":" + k.group(2)) + (" AM" if int(k.group(1)) < 12 else " PM")), x)
    rows = [(a, t12(b)) for a, b in rows]
    if rows: return rows[:7] if (len(rows) >= 3 or any(" to " in r[0] for r in rows)) else []
    for m in re.finditer(rf"({DAY}(?:\s*(?:-|–|to|through)\s*{DAY})?)\s*[:\-]?\s*(\d{{1,2}}(?::\d{{2}})?\s*[ap]\.?m\.?\s*(?:-|–|to)\s*\d{{1,2}}(?::\d{{2}})?\s*[ap]\.?m\.?)", text, re.I):
        rows.append((m.group(1).strip().title(), re.sub(r"\s*(-|–)\s*", " to ", m.group(2).strip())))
        if len(rows) == 7: break
    rows = list(dict.fromkeys(rows))
    return rows if len(rows) >= 3 or any(" to " in r[0] or "–" in r[0] or "-" in r[0] for r in rows) else []  # hide fragments, never show wrong hours
def address_of(biz, text):
    a = biz.get("address") if isinstance(biz.get("address"), dict) else {}
    if a.get("streetAddress"): return ", ".join(str(a[x]) for x in ("streetAddress", "addressLocality", "addressRegion", "postalCode") if a.get(x)), a.get("addressLocality", "")
    m = re.search(r"(\d{2,5}\s+[A-Za-z0-9.\s]{3,40}?\s(?:St|Street|Ave|Avenue|Blvd|Rd|Road|Dr|Drive|Ln|Lane|Hwy|Pkwy|Way)\b\.?,?\s*(?:Suite|Ste|#)?\s*\w*,?\s*([A-Za-z .]+),\s*[A-Z]{2}\s*\d{5})", text)
    return (re.sub(r"\s+", " ", m.group(1)), m.group(2).strip()) if m else ("", "")
def photos_of(soup, base, folder):
    c = []
    for m in soup.find_all("meta", attrs={"property": re.compile("og:image|twitter:image")}): c.append(m.get("content"))
    for i in soup.find_all(["img", "source"]):
        for k in ("src", "data-src", "data-lazy-src"):
            if i.get(k): c.append(i[k])
        if i.get("srcset"): c.append(i["srcset"].split(",")[-1].strip().split(" ")[0])
    c += re.findall(r"url\(['\"]?([^'\")]+)", str(soup)[:400000])
    urls = [urljoin(base, u) for u in dict.fromkeys(x for x in c if x) if not re.search(r"logo|icon|sprite|avatar|favicon|\.svg|\.gif|pixel|spacer", u, re.I) and re.search(r"\.(jpe?g|png|webp)|image", u, re.I)]
    good, hashes = [], []
    for u in urls[:20]:
        b, _ = media.dl(u); im = media.photo(b) if b else None
        if im is None: continue
        h = media.ahash(im)
        if any(sum(x != y for x, y in zip(h, o)) <= 5 for o in hashes): continue
        lb = media.label(im); hashes.append(h)
        if lb not in ("graphic", "logo"): good.append((lb, im))
    pr = {"food": 0, "interior": 1, "exterior": 2, "drink": 3, "": 4, "people": 6}; good.sort(key=lambda x: (pr.get(x[0], 5), -x[1].width * x[1].height))
    ppl = [x for x in good if x[0] == "people"]; good = [x[1] for x in good if x[0] != "people"] + [x[1] for x in ppl[:1]]; out = []
    for n, im in enumerate(good[:8]): media.save(im, f"{folder}/img/p{n}.jpg"); out.append(f"img/p{n}.jpg")
    return out
def process(r, folder):
    u = r["Website"].strip(); resp = get(u); soup = BeautifulSoup(resp.text, "html.parser"); base = resp.url; text = soup.get_text("\n")
    biz = (ld(soup) or [{}])[0]; os.makedirs(f"{folder}/img", exist_ok=True)
    name = r.get("Name") or (soup.title.string or "").split("|")[0].strip(); kind, q = niche(name)
    meta = (soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"}) or {}).get("content", "").strip()
    about = meta if len(meta) >= 60 and not re.search(r"cookie|javascript", meta, re.I) else ""
    addr, city = address_of(biz, text); items, menu_url, msrc = get_menu(soup, base)
    lg = biz.get("logo"); lg = lg.get("url") if isinstance(lg, dict) else lg
    if not lg:
        lg = next((i["src"] for i in soup.find_all("img") if i.get("src") and re.search("logo", " ".join([*(i.get("class") or []), i.get("id") or "", i.get("alt") or "", i["src"]]), re.I)), None)
    logo = None
    if lg:
        b, _ = media.dl(urljoin(base, lg)); tone = media.logo(b, f"{folder}/img/logo.png") if b else None; logo = ("img/logo.png", tone) if tone else None
    ph = photos_of(soup, base, folder); own = len(ph); video = poster = None
    if media.PEX:
        for n, link in enumerate(media.pexels_photos(q, 8 - len(ph) if len(ph) < 8 else 0)):
            if len(ph) >= 6: break
            b, _ = media.dl(link); im = media.photo(b) if b else None
            if im: media.save(im, f"{folder}/img/s{n}.jpg"); ph.append(f"img/s{n}.jpg")
        video, poster = media.pexels_video(q)
    seed = sum(map(ord, os.path.basename(folder))); lib = f"{OUT}/_stock/{kind}"
    if os.path.isdir(lib):
        pics = sorted(f for f in os.listdir(lib) if re.search(r"\.(jpe?g|png|webp)$", f, re.I)); vids = sorted(f for f in os.listdir(lib) if f.lower().endswith(".mp4"))
        for n in range(len(pics)):
            if len(ph) >= 6: break
            ph.append(f"/_stock/{kind}/{pics[(seed + n) % len(pics)]}")
        if vids and not video: video = f"/_stock/{kind}/{vids[seed % len(vids)]}"
    order = next((urljoin(base, a["href"]) for a in soup.find_all("a", href=True) if re.search(r"toasttab|doordash|ubereats|chownow|olo\.com|square\.site|clover\.com|order\.|/order", a["href"], re.I)), None)
    d = {"name": name, "slug": os.path.basename(folder), "phone": r.get("Phone", ""), "email": r.get("Email", ""), "address": addr, "city": city, "hours": hours_of(biz, text), "about": ai_about(name, about) if about else "", "logo": logo,
         "photos": ph, "video": video, "poster": poster, "menu": items, "menu_url": menu_url, "order_url": order, "ig": r.get("Instagram", ""), "fb": r.get("Facebook", ""), "web": u, "kind": kind}
    if os.getenv("AI_DESIGN") == "1" and artdir.KEY:
        html, info = artdir.make_site(d, OUT, d["slug"], artdir.pick(kind, USED), build3)
        if info["theme"] in artdir.DIRS: USED[info["theme"]] += 1
    else: html, info = build3(d)
    open(f"{folder}/index.html", "w", encoding="utf-8").write(html)
    pts = (2 if own >= 4 else 1 if own >= 2 else 0) + (2 if len(items) >= 5 else 0) + (1 if addr else 0) + (1 if d["hours"] else 0) + (1 if logo else 0) + (1 if len(about) >= 60 else 0)
    d["grade"] = "A" if pts >= 6 else "B" if pts >= 4 else "C"; d["pts"] = pts
    flags = [x for x, bad in [("no own photos", own < 3), ("no menu", msrc in ("none", "link") and not items), ("no address", not addr), ("no logo", not logo)] if bad]
    return d, info, msrc, own, "ok" if not flags else "check: " + ", ".join(flags), html
def main(src):
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig"))); done = {}
    if os.path.exists(RES): done = {r["Website"]: r for r in csv.DictReader(open(RES, encoding="utf-8"))}
    for r in done.values(): r["batch"] = r.get("batch") or "1"
    USED.update(r.get("theme") for r in done.values() if r.get("theme") in artdir.DIRS)
    n_b = max([int(r["batch"]) for r in done.values()] or [0]) + 1; batch = []; used = {r.get("site_path") for r in done.values()}
    for r in [x for x in rows if x.get("Website") and x["Website"] not in done][:int(os.getenv("MAX_PER_RUN", "30"))]:
        res = dict(r); name = r.get("Name") or r["Website"]; s = slug(name); k = 2; b0 = s
        while f"/{s}/" in used: s = f"{b0}-{k}"; k += 1
        used.add(f"/{s}/")
        try:
            d, info, msrc, own, qa, html = process(r, f"{OUT}/{s}"); perf, seo, iss, fix = audit(r["Website"], get(r["Website"]).text)
            res.update({"fetch_status": "ok", "template": d["kind"], "theme": info["theme"], "hero_style": info["hero"], "site_path": f"/{s}/", "site_url": f"{BASE}/{s}/" if BASE else "", "audit_perf": perf, "audit_seo": seo,
                        "audit_issues": " | ".join(iss), "improvements_made": " | ".join(fix + ["Premium redesign with real photos and clear menu"]), "menu_source": msrc, "own_photos": own, "logo_found": bool(d["logo"]), "address_found": bool(d["address"]), "qa_flag": qa, "ai_score": info.get("ai_score", ""), "pitch_grade": d["grade"], "pitch_points": d["pts"]})
        except Exception as ex: res.update({"fetch_status": f"failed: {str(ex)[:80]}", "qa_flag": "needs manual build"})
        res.update({"review_status": "pending", "email_status": "", "batch": str(n_b), "live_status": ""}); done[r["Website"]] = res; batch.append(res); print(name, res["fetch_status"], res.get("qa_flag")); time.sleep(2)
    allr = list(done.values()); cols = list(dict.fromkeys(c for r in allr for c in r)); d = os.path.dirname(RES) or "."; os.makedirs(d, exist_ok=True)
    with open(RES, "w", newline="", encoding="utf-8") as fh: w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows(allr)
    for b in sorted({r["batch"] for r in allr}, key=int):
        p = f"{d}/batch_{b}.csv"
        if not os.path.exists(p) or (batch and int(b) == n_b):
            with open(p, "w", newline="", encoding="utf-8") as fh: w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows([r for r in allr if r["batch"] == b])
if __name__ == "__main__": main(sys.argv[1])
