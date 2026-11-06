"""v3: lead CSV -> real extraction (photos, logo, menu incl. AI reading, address, hours) -> themed premium site -> audit -> results CSV."""
import csv, json, os, re, sys, time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import media, artdir, library
from collections import Counter
USED = Counter()
from common import get, ld, audit, ai_about, slug
from business_intel import classify_business
from render3 import build3, niche
OUT, RES = os.getenv("SITES_DIR", "sites"), os.getenv("RESULTS", "results/websites_tab.csv")
BASE, MAXN = os.getenv("BASE_URL", "").rstrip("/"), int(os.getenv("MAX_PER_RUN", "30"))
BAD = re.compile(r"^(add|make it|extra|sub|substitute|no |with |choice of|side of)\b", re.I)
DAY = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*"

def about_from_soup(soup):
    """Extract a source-authored business paragraph while rejecting contact details."""
    candidates = []
    for paragraph in soup.find_all("p"):
        value = re.sub(r"s+", " ", paragraph.get_text(" ", strip=True)).strip()
        if len(value) < 70 or len(value) > 700:
            continue
        if re.search(r"@|\b(?:tel|phone|call|address|directions)\b|\+?\d[\d(). -]{7,}", value, re.I):
            continue
        if re.search(r"\b\d{1,6}\s+\w+\s+(?:street|st|road|rd|avenue|ave|boulevard|blvd)\b", value, re.I):
            continue
        candidates.append(value)
    return max(candidates, key=len, default="")


def select_test_rows(rows, only_website="", limit=30):
    """Test/demo lead selector: exact URL matching, fail closed, always bounded."""
    candidates = [row for row in rows if row.get("Website")]
    if only_website:
        target = only_website.strip().rstrip("/").lower()
        matches = [row for row in candidates if row["Website"].strip().rstrip("/").lower() == target]
        if len(matches) != 1:
            raise ValueError(f"Target website must match exactly one row; found {len(matches)}")
        candidates = matches
    return candidates[:max(0, int(limit))]


def suppress_ambiguous_menu_prices(items):
    """Drop price claims when extraction repeats one price across most products."""
    rows = [dict(item) for item in (items or [])]
    prices = [str(row.get("price", "")).strip() for row in rows if str(row.get("price", "")).strip()]
    if len(prices) >= 3:
        counts = Counter(prices)
        value, count = counts.most_common(1)[0]
        if value and count >= 3 and count / len(prices) >= 0.6:
            return []
    return rows


def select_leads(rows, only_website="", done=None):
    """Select exact target URL when requested; normal runs skip completed leads."""
    completed = done if done is not None else {}
    candidates = [row for row in rows if row.get("Website")]
    if only_website:
        target = only_website.strip().rstrip("/").lower()
        matches = [row for row in candidates if row["Website"].strip().rstrip("/").lower() == target]
        if len(matches) != 1:
            raise ValueError(f"ONLY_WEBSITE must match exactly one lead; found {len(matches)} for {only_website}")
        completed.pop(matches[0]["Website"], None)
        return matches
    return [row for row in candidates if row["Website"] not in completed]
def menu_text(h):
    soup = BeautifulSoup(h, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header"]): node.decompose()
    lines = [line.strip() for line in soup.get_text("\n").split("\n") if line.strip()]
    items, section, pending, seen = [], "", None, set()

    def add(name, price):
        clean = re.sub(r"\s+", " ", name).strip(" .-–·$|")
        if 3 <= len(clean) <= 60 and len(re.findall(r"[A-Za-z]", clean)) >= 3 and not BAD.match(clean) and clean.lower() not in seen:
            seen.add(clean.lower())
            items.append({"section": section, "name": clean, "price": price, "desc": ""})

    def price_only(value):
        return bool(re.fullmatch(r"\$\s?\d+(?:\.\d{2})?", value.strip()))

    for index, line in enumerate(lines):
        price_match = re.search(r"(\$\s?\d+(?:\.\d{2})?(?:\s*/\s*\$\s?\d+(?:\.\d{2})?)?)$", line)
        if price_only(line):
            if pending:
                add(pending, re.sub(r"\s+", "", line))
                pending = None
            continue
        if price_match:
            name = line[:price_match.start()].strip()
            prices = re.findall(r"\$\s?\d+(?:\.\d{2})?", price_match.group(1))
            if name:
                add(name, " / ".join(re.sub(r"\s+", "", price) for price in prices[:2]))
            elif pending:
                add(pending, " / ".join(re.sub(r"\s+", "", price) for price in prices[:2]))
                pending = None
            continue
        next_is_price = index + 1 < len(lines) and price_only(lines[index + 1])
        if next_is_price and 3 <= len(line) <= 60:
            pending = line
            continue
        if pending and len(line) > 20 and not re.search(r"[$\d@]|https?://", line):
            pending = None
        if not items and not pending and len(line) <= 30 and not re.search(r"[$\d@]|https?://", line):
            section = line.title()
        elif not pending and len(line) <= 60 and not re.search(r"[$\d@]|https?://", line):
            pending = line
    return items[:24] if len(items) >= 5 else []


def product_items_from_html(document):
    soup = BeautifulSoup(document or "", "html.parser")
    found = []
    def visit(node):
        if isinstance(node, list):
            for child in node: visit(child)
        elif isinstance(node, dict):
            kind = node.get("@type", [])
            kinds = kind if isinstance(kind, list) else [kind]
            if any(str(value).lower() == "product" for value in kinds):
                name = str(node.get("name") or "").strip()
                if name:
                    offers = node.get("offers") or {}
                    if isinstance(offers, list): offers = offers[0] if offers else {}
                    price = str(offers.get("price") or "").strip() if isinstance(offers, dict) else ""
                    currency = str(offers.get("priceCurrency") or "").strip() if isinstance(offers, dict) else ""
                    if price:
                        price = (currency + " " + price).strip()
                    if name.islower(): name = name.title()
                    found.append({"section": "", "name": name, "desc": str(node.get("description") or ""), "price": price})
            if "@graph" in node: visit(node["@graph"])
    for script in soup.find_all("script", type="application/ld+json"):
        try: visit(json.loads(script.string or script.get_text() or ""))
        except Exception: continue
    return found

def get_menu(soup, base):
    link = next((urljoin(base, a["href"]) for a in soup.find_all("a", href=True) if re.search(r"menu", a["href"] + a.get_text(), re.I) and not a["href"].lower().endswith(".pdf") and "order" not in a.get_text().lower()), None)
    pages, items, src = [soup], [], "none"
    if link:
        try:
            r = get(link)
            if getattr(r, "status_code", 200) >= 400:
                link = None
            else:
                items = menu_text(r.text)
                pages.append(BeautifulSoup(r.text, "html.parser"))
        except Exception:
            link = None
        src = "text" if items else ("link" if link else "none")
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
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    short_days = {"mo": "Monday", "tu": "Tuesday", "we": "Wednesday", "th": "Thursday", "fr": "Friday", "sa": "Saturday", "su": "Sunday"}

    def clock(value):
        match = re.fullmatch(r"\s*(\d{1,2})(?::(\d{2}))?\s*([ap])?m?\.?\s*", value, re.I)
        if not match: return value.strip()
        hour, minute, suffix = int(match.group(1)), int(match.group(2) or 0), (match.group(3) or "").lower()
        if suffix:
            period = "AM" if suffix == "a" else "PM"
            hour = hour % 12 or 12
        else:
            period = "PM" if hour >= 12 else "AM"
            hour = hour % 12 or 12
        return f"{hour}{':' + str(minute).zfill(2) if minute else ''} {period}"

    def normalize_label(label):
        raw = re.sub(r"\s+", " ", label.strip()).replace("–", " to ").replace("-", " to ")
        raw = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su)\b", lambda match: short_days[match.group(1).lower()], raw, flags=re.I)
        return raw

    def parse_rows(source):
        parsed = []
        pattern = re.compile(rf"({DAY}(?:\s*(?:-|–|to|through)\s*{DAY})?)\s*[:\-]?\s*(\d{{1,2}}(?::\d{{2}})?\s*[ap]?\.?m?\.?\s*(?:-|–|to)\s*\d{{1,2}}(?::\d{{2}})?\s*[ap]?\.?m?\.?)", re.I)
        for match in pattern.finditer(source or ""):
            label = normalize_label(match.group(1))
            times = re.split(r"\s*(?:-|–|to)\s*", match.group(2), maxsplit=1, flags=re.I)
            if len(times) != 2: continue
            parsed.append((label, f"{clock(times[0])} to {clock(times[1])}"))
        covered, result = set(), []
        for label, value in parsed:
            days = re.findall(r"Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday", label, re.I)
            days = [day.title() for day in days]
            if len(days) >= 2 and " to " in label.lower():
                first, last = day_names.index(days[0]), day_names.index(days[-1])
                expanded = set(day_names[first:last + 1] if first <= last else day_names[first:] + day_names[:last + 1])
            else:
                expanded = set(days)
            if expanded and expanded.intersection(covered): continue
            covered.update(expanded)
            result.append((label, value))
        return result

    visible = parse_rows(text)
    if len(visible) >= 2 and (len(visible) >= 3 or any(" to " in row[0].lower() for row in visible)):
        return visible[:7]
    schema = biz.get("openingHours") or []
    schema = [schema] if isinstance(schema, str) else schema
    schema_rows = parse_rows(" ".join(str(item) for item in schema))
    if len(schema_rows) >= 3 or any(" to " in row[0].lower() for row in schema_rows):
        return schema_rows[:7]
    return visible[:7] if len(visible) >= 3 else []


def address_of(biz, text, soup=None):
    value = biz.get("address") if isinstance(biz, dict) else None
    if isinstance(value, dict) and value.get("streetAddress"):
        parts = [value.get(key) for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode")]
        return ", ".join(str(part) for part in parts if part), value.get("addressLocality", "")
    source = (soup.get_text(" ", strip=True) + " " if soup else "") + (text or "")
    pattern = re.compile(r"(\d{1,6}\s+(?:[A-Za-z0-9.'#-]+\s+){1,8}(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Hwy|Highway|Pkwy|Way)\.?)\s*,?\s*([A-Za-z .]+?)\s*,?\s*([A-Z]{2})\s*(\d{5}(?:-\d{4})?)\b")
    match = pattern.search(source)
    if match:
        street, city, state, postal = match.groups()
        city = re.sub(r"\s+", " ", city).strip(" ,")
        return f"{street.strip()}, {city}, {state} {postal}", city
    return "", ""

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
    structured = [item for item in (ld(soup) or []) if isinstance(item, dict)]
    biz = max(structured, key=lambda item: sum(bool(item.get(key)) for key in ("address", "openingHours", "telephone", "logo")), default={})
    os.makedirs(f"{folder}/img", exist_ok=True)
    name = r.get("Name") or biz.get("name") or (soup.title.get_text(" ", strip=True) if soup.title else "").split("|")[0].strip()
    meta = (soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"}) or {}).get("content", "").strip()
    about = meta if len(meta) >= 60 and not re.search(r"cookie|javascript", meta, re.I) else ""
    headings = [node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2", "h3"])]
    schema_types = []
    for node in structured:
        value = node.get("@type", [])
        schema_types.extend(value if isinstance(value, list) else [value])
    addr, city = address_of(biz, text); items, menu_url, msrc = get_menu(soup, base)
    items = suppress_ambiguous_menu_prices(items)
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    niche_kind, q, classification = classify_business(name, title, about, headings, items, schema_types)
    kind = {"cafe": "coffee", "fastfood": "grill"}.get(niche_kind, niche_kind)
    if os.getenv("DESIGN_MODE") == "library" and artdir.KEY: kind = library.classify(name, about, items, kind)
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
    d = {"name": name, "slug": os.path.basename(folder), "phone": r.get("Phone") or biz.get("telephone", ""), "email": r.get("Email") or biz.get("email", ""), "address": addr, "city": city, "hours": hours_of(biz, text), "about": ai_about(name, about) if about else "", "logo": logo,
         "photos": ph, "video": video, "poster": poster, "menu": items, "menu_url": menu_url, "order_url": order, "ig": r.get("Instagram", ""), "fb": r.get("Facebook", ""), "web": u, "kind": kind, "niche": niche_kind, "classification": classification}
    if os.getenv("DESIGN_MODE") == "library" and artdir.KEY: html, info = library.make_site(d, OUT, d["slug"], kind, build3)
    elif os.getenv("AI_DESIGN") == "1" and artdir.KEY:
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
    candidates = select_leads(rows, os.getenv("ONLY_WEBSITE", ""), done)
    for r in candidates[:int(os.getenv("MAX_PER_RUN", "30"))]:
        res = dict(r); name = r.get("Name") or r["Website"]; s = slug(name); k = 2; b0 = s
        while f"/{s}/" in used: s = f"{b0}-{k}"; k += 1
        used.add(f"/{s}/")
        try:
            d, info, msrc, own, qa, html = process(r, f"{OUT}/{s}"); perf, seo, iss, fix = audit(r["Website"], get(r["Website"]).text)
            res.update({"fetch_status": "ok", "template": d["kind"], "theme": info["theme"], "hero_style": info["hero"], "site_path": f"/{s}/", "site_url": f"{BASE}/{s}/" if BASE else "", "audit_perf": perf, "audit_seo": seo,
                        "audit_issues": " | ".join(iss), "improvements_made": " | ".join(fix + ["Premium redesign with real photos and clear menu"]), "menu_source": msrc, "own_photos": own, "logo_found": bool(d["logo"]), "address_found": bool(d["address"]), "qa_flag": qa, "ai_score": info.get("ai_score", ""), "template_id": info.get("template_id", ""), "template_status": info.get("template_status", ""), "pitch_grade": d["grade"], "pitch_points": d["pts"]})
        except Exception as ex: res.update({"fetch_status": f"failed: {str(ex)[:80]}", "qa_flag": "needs manual build"})
        res.update({"review_status": "pending", "email_status": "", "batch": str(n_b), "live_status": ""}); done[r["Website"]] = res; batch.append(res); print(name, res["fetch_status"], res.get("qa_flag")); time.sleep(2)
    allr = list(done.values()); cols = list(dict.fromkeys(c for r in allr for c in r)); d = os.path.dirname(RES) or "."; os.makedirs(d, exist_ok=True)
    with open(RES, "w", newline="", encoding="utf-8") as fh: w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows(allr)
    for b in sorted({r["batch"] for r in allr}, key=int):
        p = f"{d}/batch_{b}.csv"
        if not os.path.exists(p) or (batch and int(b) == n_b):
            with open(p, "w", newline="", encoding="utf-8") as fh: w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows([r for r in allr if r["batch"] == b])
if __name__ == "__main__": main(sys.argv[1])
