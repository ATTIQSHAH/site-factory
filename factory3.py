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
def suppress_ambiguous_menu_prices(items):
    """Drop menu cards when a repeated price strongly suggests a parsing error."""
    prices = [str(item.get("price", "")).strip() for item in items if str(item.get("price", "")).strip()]
    if len(prices) >= 3:
        counts = Counter(prices)
        value, count = counts.most_common(1)[0]
        if value and count >= 3 and count / len(prices) >= 0.6:
            return []
    return items


def menu_text(h):
    soup = BeautifulSoup(h, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header"]):
        node.decompose()
    lines = [re.sub(r"\s+", " ", line).strip() for line in soup.get_text("\n").split("\n") if line.strip()]
    items, section, pending = [], "", None

    def add(name, price):
        name = name.strip(" .-–·$|")
        if 3 <= len(name) <= 60 and len(re.findall(r"[A-Za-z]", name)) >= 3 and "$" not in name and not BAD.match(name):
            if _norm_menu_name(name) not in {_norm_menu_name(item["name"]) for item in items}:
                items.append({"section": section, "name": name, "price": price, "desc": ""})

    for line in lines:
        price_match = re.search(r"(\$\s?\d+(?:\.\d{2})?)\s*$", line)
        if price_match:
            price = re.sub(r"\s+", "", price_match.group(1))
            name = line[:price_match.start()].strip()
            if name:
                add(name, price)
            elif pending:
                add(pending, price)
            pending = None
            continue
        if re.fullmatch(r"\$\s?\d+(?:\.\d{2})?", line):
            if pending:
                add(pending, re.sub(r"\s+", "", line))
                pending = None
            continue
        if re.search(r"@|https?://", line) or len(line) > 160:
            continue
        if pending:
            if len(pending.split()) <= 2 and not re.search(r"[.!?]", pending):
                section = pending.title()
            elif items and not items[-1]["desc"] and len(pending) >= 18:
                items[-1]["desc"] = pending
            pending = line
        else:
            pending = line
    if len(items) >= 5:
        return items[:24]
    return []


def _norm_menu_name(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def product_items_from_html(document):
    soup = BeautifulSoup(document or "", "html.parser")
    found = []
    def walk(value):
        if isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            types = value.get("@type", [])
            types = [types] if isinstance(types, str) else types
            if any(str(kind).lower() in {"product", "menuitem"} for kind in types):
                name = str(value.get("name", "")).strip()
                offers = value.get("offers", {})
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                if isinstance(offers, dict):
                    price = str(offers.get("price", "")).strip()
                    currency = str(offers.get("priceCurrency", "")).strip().upper()
                    formatted = (currency + " " if currency else "$") + price if price else ""
                else:
                    formatted = ""
                if name and formatted:
                    found.append({"section": "", "name": name.title(), "price": formatted,
                                  "desc": str(value.get("description", "")).strip()})
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue
    return found


def about_from_soup(soup):
    for paragraph in soup.find_all("p"):
        text = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
        if len(text) < 80 or len(text.split()) < 12:
            continue
        if re.search(r"@|\b(?:tel|phone|call|hours|open daily)\b|\b\d{3}[-.) ]?\d{3}[- ]?\d{4}\b|\b\d{2,5}\s+\w+\s+(?:street|st|avenue|ave|road|rd|boulevard|blvd)\b", text, re.I):
            continue
        return text
    return ""


def select_test_rows(rows, target=None, limit=30):
    valid = [row for row in rows if row.get("Website")]
    if target:
        wanted = target.strip().rstrip("/").lower()
        selected = [row for row in valid if row["Website"].strip().rstrip("/").lower() == wanted]
        if not selected:
            raise ValueError("Requested website was not found in the lead file: " + target)
        return selected[:max(1, int(limit))]
    return valid[:max(0, int(limit))]

def get_menu(soup, base):
    link = next((urljoin(base, a["href"]) for a in soup.find_all("a", href=True) if re.search(r"menu", a["href"] + a.get_text(), re.I) and not a["href"].lower().endswith(".pdf") and "order" not in a.get_text().lower()), None)
    pages = [soup]
    items = product_items_from_html(str(soup))
    src = "structured" if items else "none"
    if link and not items:
        try:
            response = get(link)
            items = product_items_from_html(response.text) or menu_text(response.text)
            pages.append(BeautifulSoup(response.text, "html.parser"))
        except Exception:
            pass
        src = "structured" if items and product_items_from_html(response.text) else ("text" if items else "link")
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
    day_names = {
        "mo":"Monday", "mon":"Monday", "tu":"Tuesday", "tue":"Tuesday", "we":"Wednesday",
        "wed":"Wednesday", "th":"Thursday", "thu":"Thursday", "fr":"Friday", "fri":"Friday",
        "sa":"Saturday", "sat":"Saturday", "su":"Sunday", "sun":"Sunday",
    }
    day_pattern = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
    time_pattern = r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m?\.?"

    def fmt(hour, minute, meridiem):
        h = int(hour)
        suffix = "AM" if meridiem.lower() == "a" else "PM"
        return str(h) + (":" + minute if minute and minute != "00" else "") + " " + suffix

    visible = []
    pattern = re.compile(
        rf"({day_pattern})(?:\s*(?:-|–|to|through)\s*({day_pattern}))?\s*[:\-]?\s*"
        r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m?\.?\s*(?:-|–|to)\s*"
        r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m?\.?", re.I
    )
    for match in pattern.finditer(text or ""):
        start_day = day_names.get(match.group(1)[:3].lower(), match.group(1).title())
        end_day = day_names.get((match.group(2) or match.group(1))[:3].lower(), (match.group(2) or match.group(1)).title())
        start = fmt(match.group(3), match.group(4), match.group(5))
        end = fmt(match.group(6), match.group(7), match.group(8))
        label = start_day if start_day == end_day else start_day + " to " + end_day
        visible.append((label, start + " to " + end))
    if visible:
        ranges = [row for row in visible if " to " in row[0]]
        if ranges:
            order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            covered = set()
            for label, _ in ranges:
                start_day, end_day = label.split(" to ", 1)
                if start_day in order and end_day in order:
                    covered.update(order[order.index(start_day):order.index(end_day) + 1])
            result = list(ranges)
            seen_labels = {row[0] for row in result}
            for row in visible:
                if row[0] not in covered and row[0] not in seen_labels:
                    result.append(row)
                    seen_labels.add(row[0])
            return result[:7]
        result, seen_labels = [], set()
        for row in visible:
            if row[0] not in seen_labels:
                result.append(row)
                seen_labels.add(row[0])
        return result[:7]

    schema = biz.get("openingHours")
    schema = [schema] if isinstance(schema, str) else (schema or [])
    rows = []
    schema_pattern = re.compile(
        rf"({day_pattern})(?:\s*[-–]\s*({day_pattern}))?\s+"
        r"(\d{1,2}:\d{2})\s*[-–]\s*(\d{1,2}:\d{2})", re.I
    )
    for value in schema:
        match = schema_pattern.search(str(value))
        if not match:
            continue
        start_day = day_names.get(match.group(1)[:3].lower(), match.group(1).title())
        end_day = day_names.get((match.group(2) or match.group(1))[:3].lower(), (match.group(2) or match.group(1)).title())
        def clock(value):
            hour, minute = map(int, value.split(":"))
            return fmt(hour % 12 or 12, str(minute).zfill(2), "a" if hour < 12 else "p")
        label = start_day if start_day == end_day else start_day + " to " + end_day
        rows.append((label, clock(match.group(3)) + " to " + clock(match.group(4))))
    return list(dict.fromkeys(rows))[:7] if len(rows) >= 2 else []

def address_of(biz, text, soup=None):
    value = biz.get("address") if isinstance(biz, dict) else None
    if isinstance(value, dict) and value.get("streetAddress"):
        parts = [value.get(key) for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode") if value.get(key)]
        return ", ".join(str(part) for part in parts), value.get("addressLocality", "")
    source = soup.get_text(" ", strip=True) if soup is not None else (text or "")
    pattern = re.compile(
        r"(\d{1,6}\s+[A-Za-z0-9 .'-]+?\b(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way)\b),?\s*"
        r"([A-Za-z .'-]+?),\s*([A-Z]{2})\s+(\d{5})(?:-\d{4})?", re.I
    )
    match = pattern.search(source)
    if match:
        street, city, region, postal = match.groups()
        return f"{street.strip()}, {city.strip()}, {region.upper()} {postal}", city.strip()
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
    biz = (ld(soup) or [{}])[0]; os.makedirs(f"{folder}/img", exist_ok=True)
    name = r.get("Name") or (soup.title.string or "").split("|")[0].strip()
    meta = (soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"}) or {}).get("content", "").strip()
    about = meta if len(meta) >= 60 and not re.search(r"cookie|javascript", meta, re.I) else about_from_soup(soup)
    addr, city = address_of(biz, text, soup)
    items, menu_url, msrc = get_menu(soup, base)
    items = suppress_ambiguous_menu_prices(items)
    title_text = soup.title.get_text(" ", strip=True) if soup.title else ""
    headings = [node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2", "h3"])[:20]]
    schema_types = [value for entry in (ld(soup) or []) for value in (
        entry.get("@type", []) if isinstance(entry.get("@type"), list) else [entry.get("@type", "")]
    ) if value]
    kind, q, classification = classify_business(
        name=name, title=title_text, description=about, headings=headings,
        menu_items=items, schema_types=schema_types
    )
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
    d = {"name": name, "slug": os.path.basename(folder), "phone": r.get("Phone", ""), "email": r.get("Email", ""), "address": addr, "city": city, "hours": hours_of(biz, text), "about": ai_about(name, about) if about else "", "logo": logo,
         "photos": ph, "video": video, "poster": poster, "menu": items, "menu_url": menu_url, "order_url": order, "ig": r.get("Instagram", ""), "fb": r.get("Facebook", ""), "web": u, "kind": kind, "classification": classification}
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
    raw_rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    target = os.getenv("ONLY_WEBSITE", "").strip()
    try:
        rows = select_test_rows(raw_rows, target or None, limit=os.getenv("MAX_PER_RUN", "30"))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    done = {}
    if os.path.exists(RES):
        done = {row["Website"]: row for row in csv.DictReader(open(RES, encoding="utf-8"))}
    if target:
        for key in list(done):
            if key.strip().rstrip('/') == target:
                done.pop(key, None)
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
