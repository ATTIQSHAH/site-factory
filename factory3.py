"""v3: lead CSV -> real extraction (photos, logo, menu incl. AI reading, address, hours) -> themed premium site -> audit -> results CSV."""
import csv, os, re, sys, time, shutil, json
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import media, artdir, library, business_intel
from collections import Counter
USED = Counter()
from common import get, ld, audit, ai_about, slug
from render3 import build3, niche
OUT, RES = os.getenv("SITES_DIR", "sites"), os.getenv("RESULTS", "results/websites_tab.csv")
BASE, MAXN = os.getenv("BASE_URL", "").rstrip("/"), int(os.getenv("MAX_PER_RUN", "30"))
BAD = re.compile(r"^(add|make it|extra|sub|substitute|no |with |choice of|side of)\b", re.I)
DAY = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*"
def select_test_rows(rows, website=None, limit=30):
    """Select a bounded lead set; an explicit website must match exactly once."""
    candidates = [row for row in rows if row.get("Website")]
    if website:
        target = str(website).strip().rstrip("/").lower()
        matches = [row for row in candidates if row.get("Website", "").strip().rstrip("/").lower() == target]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one lead for {target}; found {len(matches)}")
        return matches[:max(1, int(limit))]
    return candidates[:max(0, int(limit))]


def about_from_soup(soup):
    """Extract source-authored story copy while excluding contact and utility text."""
    for paragraph in soup.find_all("p"):
        if paragraph.find_parent(["nav", "footer", "header"]):
            continue
        value = re.sub(r"\s+", " ", paragraph.get_text(" ", strip=True)).strip()
        if len(value) < 65:
            continue
        if re.search(r"@|\b(?:\+?\d[\d(). -]{7,}\d)\b|\b\d{1,6}\s+\w+.*\b(?:street|st|avenue|ave|road|rd|boulevard|blvd)\b", value, re.I):
            continue
        if re.search(r"hours|directions|contact us|visit us|privacy policy|cookie", value, re.I):
            continue
        return value
    return ""


def product_items_from_html(document):
    """Read only Product records from JSON-LD; never infer a product or price."""
    soup = BeautifulSoup(document or "", "html.parser")
    found = []
    def visit(value):
        if isinstance(value, list):
            for item in value: visit(item)
        elif isinstance(value, dict):
            kinds = value.get("@type", [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            if any(str(kind).lower() == "product" for kind in kinds) and value.get("name"):
                name = re.sub(r"\s+", " ", str(value["name"])).strip()
                if name.islower(): name = name.title()
                offers = value.get("offers", {})
                if isinstance(offers, list): offers = offers[0] if offers else {}
                price, currency = (offers.get("price"), offers.get("priceCurrency")) if isinstance(offers, dict) else (None, None)
                found.append({"section": "Menu", "name": name,
                              "price": (f"{currency} {price}" if currency and price else str(price or "")),
                              "desc": str(value.get("description") or "")})
            for key, item in value.items():
                if key in ("@graph", "itemListElement"): visit(item)
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try: visit(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError): continue
    unique, seen = [], set()
    for item in found:
        key = item["name"].casefold()
        if key not in seen: unique.append(item); seen.add(key)
    return unique[:40]


def menu_text(h, min_items=1):
    soup = BeautifulSoup(h, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header"]): node.decompose()
    items, section, seen, pending = [], "", set(), None
    lines = [line.strip() for line in soup.get_text("\n").split("\n") if line.strip()]
    price_only = re.compile(r"^\$\s?\d+(?:\.\d{2})?$")
    for line in lines:
        price_match = re.search(r"(\$\s?\d+(?:\.\d{2})?)(?:\s*/\s*(\$\s?\d+(?:\.\d{2})?))?$", line)
        if price_only.fullmatch(line):
            price = re.sub(r"\s+", "", line)
            if pending:
                if pending.casefold() not in seen:
                    items.append({"section": section, "name": pending, "price": price, "desc": ""})
                    seen.add(pending.casefold())
                pending = None
            elif items and not items[-1]["price"]:
                items[-1]["price"] = price
            continue
        if price_match:
            name = line[:price_match.start()].strip(" .-–·$|")
            price = " / ".join(re.sub(r"\s+", "", value) for value in price_match.groups() if value)
            if 3 <= len(name) <= 60 and len(re.findall(r"[A-Za-z]", name)) >= 3 and not BAD.match(name):
                if name.casefold() not in seen:
                    items.append({"section": section, "name": name, "price": price, "desc": ""})
                    seen.add(name.casefold())
            continue
        if (len(line.split()) == 1 or re.fullmatch(r"(cookies|pastries|cakes|desserts|drinks|beverages|breakfast|lunch|dinner|specials|sides|appetizers|entrees|mains|sandwiches|coffee|tea|ice cream)", line, re.I)) and not re.search(r"\d|@|http", line):
            if pending and pending.casefold() not in seen:
                items.append({"section": section, "name": pending, "price": "", "desc": ""})
                seen.add(pending.casefold())
            pending = None
            section = line.title()
        elif len(line) <= 60 and len(re.findall(r"[A-Za-z]", line)) >= 5 and not re.search(r"@|http", line):
            if pending and pending.casefold() not in seen:
                items.append({"section": section, "name": pending, "price": "", "desc": ""})
                seen.add(pending.casefold())
            pending = line
        elif items and not items[-1]["desc"] and 15 < len(line) < 160 and "$" not in line:
            items[-1]["desc"] = line
    if pending and pending.casefold() not in seen:
        items.append({"section": section, "name": pending, "price": "", "desc": ""})
    return items[:24] if len(items) >= min_items else []


def get_menu(soup, base):
    links = []
    for anchor in soup.find_all("a", href=True):
        href, label = anchor["href"], anchor.get_text(" ", strip=True)
        if re.search(r"menu", href + " " + label, re.I) or re.search(r"order online|online ordering", label, re.I):
            absolute = urljoin(base, href)
            if absolute not in links: links.append(absolute)
    link = links[0] if links else None
    pages, items, source = [soup], [], "none"
    if link:
        try:
            response = get(link)
            structured = product_items_from_html(response.text)
            if structured:
                items, source = structured, "structured"
            else:
                items = menu_text(response.text, min_items=5)
                source = "text" if items else "link"
            pages.append(BeautifulSoup(response.text, "html.parser"))
        except Exception:
            source = "link"
    if not items:
        items = product_items_from_html(str(soup))
        if items: source = "structured"
    if not items:
        pdfs = list(dict.fromkeys(urljoin(base, a["href"]) for page in pages for a in page.find_all("a", href=True)
                                  if a["href"].lower().split("?")[0].endswith(".pdf") and "menu" in a["href"].lower()))
        imgs = list(dict.fromkeys(urljoin(base, image.get("src")) for page in pages for image in page.find_all("img")
                                  if image.get("src") and re.search(r"menu", image["src"] + (image.get("alt") or ""), re.I)
                                  and re.search(r"\.(jpe?g|png|webp)", image["src"], re.I)))
        for url, mime in [(value, "application/pdf") for value in pdfs[:2]] + [(value, "image/jpeg") for value in imgs[:2]]:
            data, content_type = media.dl(url)
            extracted = media.gemini_menu(data, mime if mime == "application/pdf" else (content_type.split(";")[0] or mime))
            if len(extracted) >= 5:
                items, source, link = extracted, "ai", link or url
                break
        if not items and pdfs and not link:
            link, source = pdfs[0], "link"
    return items, link, source


def hours_of(biz, text):
    """Prefer source-published weekly ranges; ignore conflicting individual fragments."""
    day = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
    clock = r"(\d{1,2}(?::\d{2})?\s*(?:a|p|am|pm)?)"
    def fmt(value):
        value = re.sub(r"\s+", "", value.lower()).replace(".", "")
        match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm|a|p)?", value)
        if not match: return value
        hour, minute, suffix = int(match.group(1)), int(match.group(2) or 0), match.group(3)
        if suffix:
            meridiem = "AM" if suffix in ("a", "am") else "PM"
            return f"{hour} {meridiem}" if minute == 0 else f"{hour}:{minute:02d} {meridiem}"
        return f"{hour % 12 or 12}{':' + match.group(2) if minute else ''} {'AM' if hour < 12 else 'PM'}"
    def parse(source):
        pattern = re.compile(rf"({day})(?:\s*(?:-|–|to|through)\s*({day}))?\s*[:,-]?\s*{clock}\s*(?:-|–|to)\s*{clock}", re.I)
        rows = []
        day_names = {"Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday", "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"}
        for match in pattern.finditer(source or ""):
            first_raw, last_raw = match.group(1).title(), (match.group(2) or "").title()
            first, last = day_names.get(first_raw, first_raw), day_names.get(last_raw, last_raw)
            label = f"{first} to {last}" if last else first
            rows.append((label, f"{fmt(match.group(3))} to {fmt(match.group(4))}"))
        return list(dict.fromkeys(rows))

    def merge_ranges(rows):
        ranges = [row for row in rows if " to " in row[0]]
        if not ranges:
            return rows[:7]
        week = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        covered = set()
        for label, _ in ranges:
            if " to " not in label:
                continue
            first, last = label.split(" to ", 1)
            if first not in week or last not in week:
                continue
            start, end = week.index(first), week.index(last)
            covered.update(week[start:end + 1] if start <= end else week[start:] + week[:end + 1])
        ranges.extend(row for row in rows if row[0] in week and row[0] not in covered)
        return ranges[:7]

    visible = parse(text)
    if visible:
        return merge_ranges(visible)
    schema = biz.get("openingHours") or []
    schema = [schema] if isinstance(schema, str) else schema
    parsed = []
    for entry in schema:
        parsed.extend(parse(str(entry)))
    return merge_ranges(parsed) if parsed else []


def address_of(biz, text, soup=None):
    """Prefer structured street address, then recover a street/postal address from contact copy."""
    address = biz.get("address") if isinstance(biz.get("address"), dict) else {}
    if address.get("streetAddress"):
        parts = [address.get(key) for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode") if address.get(key)]
        return ", ".join(str(part) for part in parts), str(address.get("addressLocality") or "")
    source = soup.get_text(" ", strip=True) if soup is not None else str(text or "")
    pattern = re.compile(
        r"\b(?P<street>\d{1,6}\s+[A-Za-z0-9 .'-]{2,70}?\b(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Hwy|Pkwy|Way)\b\.?)"
        r"\s*,?\s*(?:(?P<city>[A-Za-z .'-]{2,35}),\s*)?(?:(?P<state>[A-Z]{2})\s*)?(?P<zip>\d{5}(?:-\d{4})?)\b"
    )
    match = pattern.search(source)
    if match:
        street = re.sub(r"\s+", " ", match.group("street")).strip()
        city, state, postal = match.group("city"), match.group("state"), match.group("zip")
        tail = ", ".join(part for part in (city, (state + " " if state else "") + postal) if part)
        return street + (", " + tail if tail else ""), (city or "").strip()
    return "", ""


def location_details(home_soup, base_url, biz, city):
    """Follow one same-site contact/location link when schema lacks a street address."""
    source = home_soup.get_text(" ", strip=True)
    address, found_city = address_of(biz, source, home_soup)
    if address:
        return address, found_city or city
    base_host = (urlparse(base_url).hostname or "").lower().removeprefix("www.")
    for anchor in home_soup.find_all("a", href=True):
        if not re.search(r"contact|location|visit|find-us", anchor.get_text(" ", strip=True) + " " + anchor["href"], re.I):
            continue
        target = urljoin(base_url, anchor["href"])
        host = (urlparse(target).hostname or "").lower().removeprefix("www.")
        if host != base_host:
            continue
        try:
            response = get(target)
            page = BeautifulSoup(response.text, "html.parser")
            address, found_city = address_of(biz, page.get_text(" ", strip=True), page)
            if address:
                return address, found_city or city
        except Exception:
            continue
    return "", city or ""


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
def suppress_ambiguous_menu_prices(rows):
    """Remove prices that are clearly unreliable because nearly every item has the same price."""
    rows = [dict(item) for item in (rows or [])]
    prices = [re.sub(r"\s+", "", str(item.get("price", ""))).lower() for item in rows]
    prices = [price for price in prices if price]
    if len(prices) >= 3:
        counts = Counter(prices)
        value, count = counts.most_common(1)[0]
        if count >= 3 and count / len(prices) >= 0.8:
            if count == len(prices):
                return []
            for item in rows:
                if re.sub(r"\s+", "", str(item.get("price", ""))).lower() == value:
                    item["price"] = ""
    return rows


def process(r, folder):
    u = r["Website"].strip(); resp = get(u); soup = BeautifulSoup(resp.text, "html.parser"); base = resp.url; text = soup.get_text("\n")
    biz = (ld(soup) or [{}])[0]; os.makedirs(f"{folder}/img", exist_ok=True)
    name = r.get("Name") or (soup.title.string or "").split("|")[0].strip(); kind, q = niche(name)
    meta = (soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"}) or {}).get("content", "").strip()
    about = meta if len(meta) >= 60 and not re.search(r"cookie|javascript", meta, re.I) else about_from_soup(soup)
    addr, city = address_of(biz, text, soup)
    if not addr: addr, city = location_details(soup, base, biz, city)
    items, menu_url, msrc = get_menu(soup, base)
    items = suppress_ambiguous_menu_prices(items)
    headings = [node.get_text(" ", strip=True) for node in soup.find_all(["h1", "h2", "h3"])[:30]]
    schema_types = [biz.get("@type", [])] if biz.get("@type") else []
    kind, q, classification = business_intel.classify_business(
        name=name, title=soup.title.get_text(" ", strip=True) if soup.title else "",
        description=about, headings=headings, menu_items=items, schema_types=schema_types
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
         "photos": ph, "video": video, "poster": poster, "menu": items, "menu_url": menu_url, "order_url": order, "ig": r.get("Instagram", ""), "fb": r.get("Facebook", ""), "web": u, "kind": kind}
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
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    only_website = os.getenv("ONLY_WEBSITE", "").strip().rstrip("/").lower()
    if only_website:
        matches = [row for row in rows if row.get("Website", "").strip().rstrip("/").lower() == only_website]
        if len(matches) != 1:
            raise SystemExit(f"ONLY_WEBSITE must match exactly one lead; found {len(matches)} for {only_website}")
        rows = matches
    done = {}
    if os.path.exists(RES): done = {r["Website"]: r for r in csv.DictReader(open(RES, encoding="utf-8"))}
    for r in done.values(): r["batch"] = r.get("batch") or "1"
    if only_website:
        done.pop(rows[0]["Website"], None)
    USED.update(r.get("theme") for r in done.values() if r.get("theme") in artdir.DIRS)
    n_b = max([int(r["batch"]) for r in done.values()] or [0]) + 1; batch = []; used = {r.get("site_path") for r in done.values()}
    for r in [x for x in rows if x.get("Website") and x["Website"] not in done][:int(os.getenv("MAX_PER_RUN", "30"))]:
        res = dict(r); name = r.get("Name") or r["Website"]; s = slug(name); k = 2; b0 = s
        while f"/{s}/" in used: s = f"{b0}-{k}"; k += 1
        used.add(f"/{s}/")
        try:
            if only_website:
                shutil.rmtree(f"{OUT}/{s}", ignore_errors=True)
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
