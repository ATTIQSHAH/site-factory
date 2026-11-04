"""v3: lead CSV -> real extraction (photos, logo, menu incl. AI reading, address, hours) -> themed premium site -> audit -> results CSV."""
import csv, json, os, re, sys, time
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import media, artdir, stock
from collections import Counter
USED = Counter()
from common import get, ld, audit, ai_about, slug
from render3 import build3, niche
from business_intel import classify_business, extract_social_links
OUT, RES = os.getenv("SITES_DIR", "sites"), os.getenv("RESULTS", "results/websites_tab.csv")
BASE, MAXN = os.getenv("BASE_URL", "").rstrip("/"), int(os.getenv("MAX_PER_RUN", "30"))
BAD = re.compile(r"^(add|make it|extra|sub|substitute|no |with |choice of|side of)\b", re.I)
DAY = r"(?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)"
def menu_text(h):
    soup = BeautifulSoup(h, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]): tag.decompose()
    lines = [value.strip() for value in soup.get_text("\n").split("\n") if value.strip()]
    items, current_section, seen = [], "", set()
    for index, line in enumerate(lines):
        match = re.search(r"(\$\s?\d+(?:\.\d{2})?[\s|/$\d.]*)$", line)
        if match:
            name = line[:match.start()].strip(" .-–·$|")
            if name.islower(): name = name.title()
            prices = re.findall(r"\$\s?\d+(?:\.\d{2})?", match.group(1))
            if not name and index:
                name = lines[index - 1].strip(" .-–·$|")
            if name.islower(): name = name.title()
            price = " / ".join(re.sub(r"\s", "", value) for value in prices[:2])
            if 3 <= len(name) <= 80 and len(re.findall(r"[A-Za-z]", name)) >= 3 and not BAD.match(name) and name.lower() not in seen:
                seen.add(name.lower())
                items.append({"section": current_section or "Shop", "name": name, "price": price, "desc": ""})
        elif 2 < len(line) < 30 and not re.search(r"\\d|@|http", line):
            next_is_price = index + 1 < len(lines) and bool(re.fullmatch(r"\\$\\s?\\d+(?:\\.\\d{2})?", lines[index + 1]))
            if not next_is_price:
                current_section = line.title()
    return items[:24] if len(items) >= 5 else []


def product_items_from_html(document):
    """Read verifiable product names, prices and descriptions from JSON-LD or product cards."""
    soup = BeautifulSoup(document or "", "html.parser")
    found, seen = [], set()

    def add(name, price="", currency="", description="", section="Shop"):
        name = re.sub(r"\s+", " ", str(name or "")).strip()
        if name.islower(): name = name.title()
        if not name or len(name) > 100 or name.lower() in seen:
            return
        seen.add(name.lower())
        price_text = f"{currency} {price}".strip() if price else ""
        found.append({
            "section": str(section or "Shop"),
            "name": name,
            "price": price_text,
            "desc": re.sub(r"\s+", " ", str(description or "")).strip()[:180],
        })

    def visit(node):
        if isinstance(node, list):
            for child in node: visit(child)
        elif isinstance(node, dict):
            kind = node.get("@type", [])
            kinds = [kind] if isinstance(kind, str) else kind
            if any(str(value).lower() == "product" for value in kinds):
                offers = node.get("offers") or {}
                if isinstance(offers, list): offers = offers[0] if offers else {}
                add(node.get("name"), offers.get("price") or offers.get("lowPrice") or "",
                    offers.get("priceCurrency") or "", node.get("description") or "",
                    node.get("category") or "Shop")
            for value in node.values():
                if isinstance(value, (dict, list)): visit(value)

    for script in soup.find_all("script", type="application/ld+json"):
        try: visit(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError): continue

    selectors = (
        '[itemtype*="Product"]', '[data-testid*="product-card"]',
        '[class*="product-card"]', '[class*="ProductCard"]',
    )
    for card in soup.select(",".join(selectors)):
        name_node = card.select_one('[itemprop="name"], [class*="product-name"], [class*="ProductName"], h2, h3')
        price_node = card.select_one('[itemprop="price"], [class*="price"], [class*="Price"]')
        if name_node:
            price = (price_node.get("content") or price_node.get_text(" ", strip=True)) if price_node else ""
            currency = price_node.get("data-currency", "") if price_node else ""
            desc_node = card.select_one('[itemprop="description"], [class*="description"], [class*="Description"]')
            add(name_node.get_text(" ", strip=True), price, currency,
                desc_node.get_text(" ", strip=True) if desc_node else "")

    return found[:24]


def rendered_store_html(url):
    """Use a real browser only as a fallback for JS-rendered online storefronts."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try: page.wait_for_load_state("networkidle", timeout=8000)
            except Exception: pass
            page.wait_for_timeout(1200)
            document = page.content()
            browser.close()
            return document
    except Exception as exc:
        print("  rendered store fallback failed:", str(exc)[:160])
        return ""


def get_menu(soup, base, order_url=None):
    link = next((urljoin(base, a["href"]) for a in soup.find_all("a", href=True)
                 if re.search(r"menu", a["href"] + a.get_text(), re.I)
                 and not a["href"].lower().endswith(".pdf")
                 and "order" not in a.get_text().lower()), None)
    pages, items, src = [soup], [], "none"
    if link:
        try:
            response = get(link)
            items = product_items_from_html(response.text) or menu_text(response.text)
            pages.append(BeautifulSoup(response.text, "html.parser"))
        except Exception:
            pass
        src = "structured_menu" if items and items[0].get("price") else ("text" if items else "link")

    if not items and order_url:
        candidates = [order_url]
        parsed_order = urlparse(order_url)
        if (parsed_order.hostname or "").lower().endswith("square.site") and not parsed_order.path.rstrip("/").endswith("/s/shop"):
            candidates.append(urljoin(order_url.rstrip("/") + "/", "s/shop"))
        for candidate in dict.fromkeys(candidates):
            document = ""
            try:
                response = get(candidate)
                document = response.text
                print(f"  online store fetched: {candidate} ({response.status_code}, {len(document)} chars)")
            except Exception as exc:
                print(f"  online store request failed: {candidate} ({str(exc)[:100]})")
            page_items = product_items_from_html(document) or menu_text(document) if document else []
            if not page_items and (parsed_order.hostname or "").lower().endswith("square.site"):
                document = rendered_store_html(candidate)
                page_items = product_items_from_html(document) or menu_text(document) if document else []
            if document:
                pages.append(BeautifulSoup(document, "html.parser"))
            if page_items:
                items, link, src = page_items, candidate, "online_store"
                print(f"  extracted {len(items)} online-store products")
                break

    if not items:
        pdfs = list(dict.fromkeys(urljoin(base, a["href"]) for page in pages
                    for a in page.find_all("a", href=True)
                    if a["href"].lower().split("?")[0].endswith(".pdf") and "menu" in a["href"].lower()))
        imgs = list(dict.fromkeys(urljoin(base, image.get("src")) for page in pages
                    for image in page.find_all("img") if image.get("src")
                    and re.search(r"menu", image["src"] + (image.get("alt") or ""), re.I)
                    and re.search(r"\.(jpe?g|png|webp)", image["src"], re.I)))
        for url, mime in [(value, "application/pdf") for value in pdfs[:2]] + [(value, "image/jpeg") for value in imgs[:2]]:
            data, content_type = media.dl(url)
            items = media.gemini_menu(data, "application/pdf" if mime == "application/pdf" else (content_type.split(";")[0] or mime))
            if len(items) >= 5:
                src = "ai"; link = link or url; break
            items = []
        if not items and pdfs and not link: link, src = pdfs[0], "link"
    return items[:24], link, src
def hours_of(biz, text):
    opening = biz.get("openingHours")
    opening = [opening] if isinstance(opening, str) else (opening or [])
    rows = []
    for value in opening:
        match = re.match(r"([A-Za-z,\- ]+?)\s+(\d{1,2}:\d{2}-\d{1,2}:\d{2})", value)
        if match:
            day = re.sub(r"\b(Mo|Tu|We|Th|Fr|Sa|Su)\b",
                         lambda found: {"Mo":"Mon","Tu":"Tue","We":"Wed","Th":"Thu","Fr":"Fri","Sa":"Sat","Su":"Sun"}[found.group(1)],
                         match.group(1).strip()).replace("-", " to ")
            start, finish = match.group(2).split("-")
            def clock(part):
                hour, minute = map(int, part.split(":"))
                suffix = "AM" if hour < 12 else "PM"
                return f"{hour % 12 or 12}{':' + str(minute).zfill(2) if minute else ''} {suffix}"
            rows.append((day, f"{clock(start)} to {clock(finish)}"))
    range_rows = [row for row in rows if " to " in row[0]]
    if range_rows:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        abbreviations = {day[:3].lower(): day for day in day_names}
        covered, selected_single_days = set(), set()
        for day, _ in range_rows:
            parts = [part.strip() for part in day.split(" to ", 1)]
            if len(parts) == 2:
                first = abbreviations.get(parts[0][:3].lower())
                last = abbreviations.get(parts[1][:3].lower())
                if first and last:
                    a, b = day_names.index(first), day_names.index(last)
                    covered.update(day_names[a:b + 1] if a <= b else day_names[a:] + day_names[:b + 1])
        single_rows = []
        for day, time in rows:
            if " to " in day:
                continue
            normalized = abbreviations.get(day[:3].lower())
            if normalized and normalized not in covered and normalized not in selected_single_days:
                single_rows.append((normalized, time))
                selected_single_days.add(normalized)
        return (range_rows + single_rows)[:7]
    if len(rows) >= 3:
        return rows[:7]
    rows = []

    time_range = r"(\d{1,2}(?::\d{2})?\s*[ap]\.?m?\.?)\s*(?:-|–|to)\s*(\d{1,2}(?::\d{2})?\s*[ap]\.?m?\.?)"
    pattern = rf"({DAY}(?:\s*(?:-|–|to|through)\s*{DAY})?)\s*[:\-]?\s*{time_range}"
    def normalize_time(value):
        match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap])\.?m?\.?", value.strip(), re.I)
        if not match: return value.strip()
        hour, minute, meridiem = int(match.group(1)), match.group(2), match.group(3).upper()
        hour = hour % 12
        display = hour if meridiem == "A" else hour + 12
        shown_hour = display % 12 or 12
        return f"{shown_hour}{':' + minute if minute else ''} {'AM' if meridiem == 'A' else 'PM'}"

    for match in re.finditer(pattern, text, re.I):
        day = re.sub(r"\s*(?:-|–|through)\s*", " to ", match.group(1).strip())
        day = re.sub(r"\bto\b", "to", day, flags=re.I)
        day = day.title().replace(" To ", " to ")
        rows.append((day, f"{normalize_time(match.group(2))} to {normalize_time(match.group(3))}"))
        if len(rows) == 7: break
    rows = list(dict.fromkeys(rows))
    range_rows = [row for row in rows if re.search(r"\bto\b", row[0], re.I)]
    if range_rows:
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        abbreviations = {day[:3].lower(): day for day in day_names}
        covered, selected_single_days = set(), set()
        for day, _ in range_rows:
            parts = re.split(r"\s+to\s+", day, maxsplit=1, flags=re.I)
            if len(parts) == 2:
                first = abbreviations.get(parts[0][:3].lower())
                last = abbreviations.get(parts[1][:3].lower())
                if first and last:
                    a, b = day_names.index(first), day_names.index(last)
                    covered.update(day_names[a:b + 1] if a <= b else day_names[a:] + day_names[:b + 1])
        singles = []
        for day, time in rows:
            if re.search(r"\bto\b", day, re.I):
                continue
            normalized = abbreviations.get(day[:3].lower())
            if normalized and normalized not in covered and normalized not in selected_single_days:
                singles.append((normalized, time))
                selected_single_days.add(normalized)
        return (range_rows + singles)[:7]
    unique = []
    seen_days = set()
    for day, time in rows:
        normalized = day
        if normalized not in seen_days:
            unique.append((normalized, time))
            seen_days.add(normalized)
    return unique if len(unique) >= 3 else []


def address_of(biz, text, soup=None):
    raw = biz.get("address")
    address = raw if isinstance(raw, dict) else {}
    city = str(address.get("addressLocality") or "")
    parts = [address.get(key) for key in ("streetAddress", "addressLocality", "addressRegion", "postalCode", "addressCountry")]
    structured = ", ".join(str(part).strip() for part in parts if part)
    if address.get("streetAddress"):
        return re.sub(r"\s+", " ", structured).strip(), city

    fallback = re.sub(r"\s+", " ", raw).strip() if isinstance(raw, str) else structured
    if soup is not None:
        node = soup.find("address")
        if node:
            candidate = re.sub(r"\s+", " ", node.get_text(" ", strip=True))
            if re.search(r"\b\d{1,6}\s+.+\b(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way)\b", candidate, re.I):
                return candidate, city

    searchable = re.sub(r"\s+", " ", text or "")
    match = re.search(
        r"(?P<street>\b\d{1,6}\s+(?:[A-Za-z0-9.'#-]+\s+){1,8}(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Hwy|Pkwy|Parkway|Way)\b\.?)\s*,?\s*(?P<city>[A-Za-z .'-]+),\s*(?P<region>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)",
        searchable,
    )
    if match:
        full = f"{match.group('street')}, {match.group('city').strip()}, {match.group('region')} {match.group('zip')}"
        return full, match.group("city").strip()
    return fallback, city


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
    name = r.get("Name") or ((soup.title.get_text(" ", strip=True) if soup.title else "") .split("|")[0].strip() or u)
    page_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    meta = (soup.find("meta", attrs={"property": "og:description"}) or soup.find("meta", attrs={"name": "description"}) or {}).get("content", "").strip()
    about = meta if len(meta) >= 60 and not re.search(r"cookie|javascript", meta, re.I) else ""
    addr, city = address_of(biz, text, soup)
    city = "".join(ch for ch in str(city or "") if ch.isalpha() or ch in " .-'’").strip()
    if sum(ch.isalpha() for ch in city) < 3: city = ""
    order = next((urljoin(base, a["href"]) for a in soup.find_all("a", href=True)
                  if re.search(r"toasttab|doordash|ubereats|chownow|olo\.com|square\.site|clover\.com|order\.|/order", a["href"], re.I)), None)
    items, menu_url, msrc = get_menu(soup, base, order)
    hours = hours_of(biz, text)
    if not hours or not items or not addr:
        rendered = rendered_store_html(base)
        if rendered:
            rendered_soup = BeautifulSoup(rendered, "html.parser")
            rendered_text = rendered_soup.get_text("\n")
            if not addr:
                addr, city = address_of(biz, rendered_text, rendered_soup)
            if not hours:
                hours = hours_of(biz, rendered_text)
            if not items:
                browser_items, browser_menu_url, browser_source = get_menu(rendered_soup, base, order)
                if browser_items:
                    items, menu_url, msrc = browser_items, browser_menu_url or menu_url, browser_source
            if not about:
                rendered_meta = (rendered_soup.find("meta", attrs={"property": "og:description"}) or rendered_soup.find("meta", attrs={"name": "description"}) or {}).get("content", "").strip()
                if len(rendered_meta) >= 60 and not re.search(r"cookie|javascript", rendered_meta, re.I):
                    about = rendered_meta
    city = "".join(ch for ch in str(city or "") if ch.isalpha() or ch in " .-'’").strip()
    if sum(ch.isalpha() for ch in city) < 3: city = ""
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])[:30]]
    kind, q, classification = classify_business(name, page_title, about, headings, items, biz.get("@type", []))
    socials = extract_social_links((a.get("href") for a in soup.find_all("a", href=True)), base)
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
    stock_ph = stock.select_stock(f"{OUT}/_stock", name, kind, folder, ph, limit=max(0, 6 - len(ph)))
    ph.extend(stock_ph)
    if stock_ph:
        print(f"  stock imagery: {len(stock_ph)} illustrative image(s) selected for {kind}")
    order = next((urljoin(base, a["href"]) for a in soup.find_all("a", href=True) if re.search(r"toasttab|doordash|ubereats|chownow|olo\.com|square\.site|clover\.com|order\.|/order", a["href"], re.I)), None)
    d = {"name": name, "slug": os.path.basename(folder), "phone": r.get("Phone", ""), "email": r.get("Email", ""), "address": addr, "city": city, "hours": hours, "about": ai_about(name, about) if about else "", "logo": logo,
         "photos": ph, "own_photos": ph[:own], "stock_photos": stock_ph, "has_stock_photos": bool(stock_ph), "video": video, "poster": poster, "menu": items, "menu_url": menu_url, "order_url": order, "ig": r.get("Instagram") or socials.get("instagram", ""), "fb": r.get("Facebook") or socials.get("facebook", ""), "web": u, "kind": kind, "subcategory": classification["subcategory"], "classification_confidence": classification["confidence"], "classification_evidence": classification["evidence"]}
    if os.getenv("AI_DESIGN") == "1" and artdir.KEY:
        html, info = artdir.make_site(d, OUT, d["slug"], artdir.pick(kind, USED), build3)
        if info["theme"] in artdir.DIRS: USED[info["theme"]] += 1
    else: html, info = build3(d)
    open(f"{folder}/index.html", "w", encoding="utf-8").write(html)
    pts = (2 if own >= 4 else 1 if own >= 2 else 0) + (2 if len(items) >= 5 else 0) + (1 if addr else 0) + (1 if d["hours"] else 0) + (1 if logo else 0) + (1 if len(about) >= 60 else 0)
    d["grade"] = "A" if pts >= 6 else "B" if pts >= 4 else "C"; d["pts"] = pts
    flags = [x for x, bad in [("no own photos", own < 3), ("no menu", msrc in ("none", "link") and not items), ("no address", not addr), ("no logo", not logo)] if bad]
    return d, info, msrc, own, "ok" if not flags else "check: " + ", ".join(flags), html
def select_test_rows(rows, only_website="", limit=30):
    """Select a deterministic bounded set; an explicit URL must match exactly."""
    selected = [r for r in rows if r.get("Website", "").strip()]
    target = (only_website or "").strip().rstrip("/")
    if target:
        selected = [r for r in selected if r.get("Website", "").strip().rstrip("/") == target]
        if not selected:
            raise ValueError(f"ONLY_WEBSITE did not exactly match a Website in the lead CSV: {target}")
        return selected[:1]
    return selected[:max(1, int(limit))]


def main(src):
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig"))); done = {}
    if os.path.exists(RES): done = {r["Website"]: r for r in csv.DictReader(open(RES, encoding="utf-8"))}
    for r in done.values(): r["batch"] = r.get("batch") or "1"
    USED.update(r.get("theme") for r in done.values() if r.get("theme") in artdir.DIRS)
    n_b = max([int(r["batch"]) for r in done.values()] or [0]) + 1; batch = []; used = {r.get("site_path") for r in done.values()}
    candidates = [x for x in rows if x.get("Website") and x["Website"] not in done]
    selected = select_test_rows(candidates, os.getenv("ONLY_WEBSITE", ""), int(os.getenv("MAX_PER_RUN", "30")))
    for r in selected:
        res = dict(r); name = r.get("Name") or r["Website"]; s = slug(name); k = 2; b0 = s
        while f"/{s}/" in used: s = f"{b0}-{k}"; k += 1
        used.add(f"/{s}/")
        try:
            d, info, msrc, own, qa, html = process(r, f"{OUT}/{s}"); perf, seo, iss, fix = audit(r["Website"], get(r["Website"]).text)
            res.update({"fetch_status": "ok", "template": info.get("template_file") or info.get("template") or d["kind"], "business_niche": d["kind"], "business_subcategory": d.get("subcategory", d["kind"]), "classification_confidence": d.get("classification_confidence", 0), "classification_evidence": json.dumps(d.get("classification_evidence", []), ensure_ascii=False), "theme": info["theme"], "hero_style": info["hero"], "site_path": f"/{s}/", "site_url": f"{BASE}/{s}/" if BASE else "", "audit_perf": perf, "audit_seo": seo,
                        "audit_issues": " | ".join(iss), "improvements_made": " | ".join(fix + ["Premium redesign with real photos and clear menu"]), "menu_source": msrc, "own_photos": own, "logo_found": bool(d["logo"]), "address_found": bool(d["address"]), "qa_flag": qa, "ai_score": info.get("ai_score", ""), "ai_error": info.get("ai_error", ""), "pitch_grade": d["grade"], "pitch_points": d["pts"]})
        except Exception as ex: res.update({"fetch_status": f"failed: {str(ex)[:80]}", "qa_flag": "needs manual build"})
        res.update({"review_status": "pending", "email_status": "", "batch": str(n_b), "live_status": ""}); done[r["Website"]] = res; batch.append(res); print(name, res["fetch_status"], res.get("qa_flag")); time.sleep(2)
    allr = list(done.values()); cols = list(dict.fromkeys(c for r in allr for c in r)); d = os.path.dirname(RES) or "."; os.makedirs(d, exist_ok=True)
    with open(RES, "w", newline="", encoding="utf-8") as fh: w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows(allr)
    for b in sorted({r["batch"] for r in allr}, key=int):
        p = f"{d}/batch_{b}.csv"
        if not os.path.exists(p) or (batch and int(b) == n_b):
            with open(p, "w", newline="", encoding="utf-8") as fh: w = csv.DictWriter(fh, fieldnames=cols, restval=""); w.writeheader(); w.writerows([r for r in allr if r["batch"] == b])
if __name__ == "__main__": main(sys.argv[1])
