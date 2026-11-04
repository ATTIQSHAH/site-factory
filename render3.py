import hashlib, html, os, re, urllib.parse as up
from template_catalog import select as select_template
E = html.escape
PAL = {"cream": ("#f6f1e9", "#ece4d6", "#2a1f17", "#6d5f52", "#8a5a2b", "rgba(42,31,23,.14)"), "espresso": ("#171210", "#211a16", "#f3ebe0", "#b8a999", "#c8a26b", "rgba(255,255,255,.12)"),
 "sage": ("#eef0ea", "#e1e6dc", "#1d2a22", "#55635a", "#3f6b4f", "rgba(29,42,34,.14)"), "noir": ("#0e0e0f", "#17171a", "#f5f1ea", "#b9b2a6", "#d6a85c", "rgba(255,255,255,.12)"),
 "ivory": ("#faf6ef", "#f0e8da", "#241a17", "#6b5b54", "#8c2f2b", "rgba(36,26,23,.14)"), "slate": ("#14191f", "#1d242c", "#eef1f4", "#a5b0bb", "#d38b5d", "rgba(255,255,255,.12)"),
 "blush": ("#fbf1ee", "#f4e2dd", "#3a2224", "#7a5c5e", "#b4505a", "rgba(58,34,36,.14)"), "butter": ("#fff8e6", "#f8ecc8", "#33280f", "#6e6140", "#a6650d", "rgba(51,40,15,.14)"),
 "ember": ("#141010", "#1e1816", "#f6efe9", "#b9aaa0", "#e2552b", "rgba(255,255,255,.12)"), "paprika": ("#fff7ee", "#fbe9d4", "#2b1a10", "#6c5445", "#b83b05", "rgba(43,26,16,.14)")}
THEMES = {"coffee": ["cream", "espresso", "sage"], "cafe": ["sage", "cream", "espresso"], "fastfood": ["ember", "paprika", "slate"], "restaurant": ["noir", "ivory", "slate"], "bakery": ["blush", "butter", "cream"], "grill": ["ember", "paprika", "slate"]}
FONTS = [("Playfair Display", "Inter", "Playfair+Display:wght@500;700&family=Inter:wght@400;500;600"), ("Fraunces", "DM Sans", "Fraunces:wght@500;700&family=DM+Sans:wght@400;500;600"),
         ("DM Serif Display", "Inter", "DM+Serif+Display&family=Inter:wght@400;500;600"), ("Cormorant Garamond", "Inter", "Cormorant+Garamond:wght@600;700&family=Inter:wght@400;500;600")]
def lum(h): h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]; c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]; return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
def cr(a, b): x, y = sorted([lum(a), lum(b)], reverse=True); return (x + .05) / (y + .05)
def mix(a, b, t): a, b = a.lstrip("#"), b.lstrip("#"); return "#" + "".join("%02x" % round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (0, 2, 4))
def safe_acc(acc, bg, ink):
    t = 0
    while cr(acc, bg) < 4.5 and t < 1: t += .1; acc = mix(acc, ink, t)
    return acc
def logo_markup(logo, name, page_bg):
    """Keep transparent logos legible without forcing a mismatched background."""
    if not logo:
        return name
    path, tone = logo
    needs_chip = (tone == "light" and lum(page_bg) > 0.45) or (tone == "dark" and lum(page_bg) < 0.45)
    image = f'<img src="{E(path)}" alt="{name} logo" style="display:block;width:auto;height:auto;max-width:150px;max-height:48px;object-fit:contain;background:transparent;border:0;border-radius:0;padding:0;box-shadow:none">'
    if not needs_chip:
        return image
    chip = "#171210" if tone == "light" else "#ffffff"
    return f'<span class="logo-contrast" style="display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;background:{chip};border-radius:5px">{image}</span>'
def niche(n):
    n = n.lower()
    if re.search(r"coffee|roast|espresso|roastery|cappuccino", n): return "coffee", "coffee shop"
    if re.search(r"cafe|café|bistro|brunch", n): return "cafe", "cafe interior"
    if re.search(r"fast[\s-]?food|burger|hamburger|pizza|pizzeria|fried chicken|wings|taco|trompo|birria|fries|hot ?dog|kebab|shawarma", n): return "fastfood", "fast food"
    if re.search(r"bakery|bread|bake|cake|dessert|cookie|macaron|donut|pastry", n): return "bakery", "bakery pastries"
    if re.search(r"bbq|barbecue|smokehouse|smoke|grill|brew|pub|cantina", n): return "grill", "grilled food"
    return "restaurant", "restaurant interior"
def build3(d):
    """d keys: name, slug, phone, email, address, city, hours(list of (day,time)), about, logo(file,tone), photos(list of rel paths), video, poster, menu(list), menu_url, order_url, ig, fb, web, kind"""
    template_file, template_meta = select_template(d.get("kind", "restaurant"), d.get("name", ""), d.get("about", ""), d.get("menu", []))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", template_file), encoding="utf-8") as template_handle:
        t = template_handle.read()
    seed = int(hashlib.md5(d["slug"].encode()).hexdigest()[:8], 16); th = THEMES[d["kind"]][seed % 3]; bg, bg2, ink, mut, acc, line = PAL[th]
    acc = safe_acc(acc, bg, ink); accink = "#111111" if cr(acc, "#111111") >= cr(acc, "#ffffff") else "#ffffff"
    f = FONTS[(seed // 3) % 4]; ph = d["photos"]; hero = ["full", "split", "type"][(seed // 12) % 3]
    if hero != "type" and not ph and not d.get("video"): hero = "type"
    if hero == "type" and len(ph) < 3: hero = "full" if (ph or d.get("video")) else "type"
    n, tel = E(d["name"]), re.sub(r"[^0-9+]", "", d["phone"] or "")
    tel = ("+1" + tel) if tel and not tel.startswith("+") and len(tel) == 10 else tel
    q = up.quote(d["address"] or d["name"]); dirn = f"https://www.google.com/maps/search/?api=1&query={q}"
    raw = (d.get("about") or "").strip(); trunc = bool(re.search(r"(\.\.\.|\u2026)\s*$", raw)) or (len(raw) >= 140 and raw[-1:] not in ".!?")
    ab = re.sub(r"[\s.\u2026]*(\.\.\.|\u2026)\s*$", "", raw).strip()
    if ab and ab[-1] not in ".!?" and trunc:
        cut = max(ab.rfind(". "), ab.rfind("! "), ab.rfind("? "))
        if cut >= 60: ab = ab[:cut + 1]
        else:
            w = ab.split()
            if len(w) > 6 and not raw.endswith(("...", "\u2026")): w = w[:-1]
            while len(w) > 6 and w[-1].lower().strip(",") in {"and", "with", "or", "of", "the", "a", "an", "to", "in", "for", "by", "as", "&", "at", "on"}: w = w[:-1]
            ab = " ".join(w).rstrip(" ,;:-") + "."
    m = re.match(r"(.{40,150}?[.!?])(\s|$)", ab); short = m.group(1) if m else (ab if len(ab) <= 150 else ab[:150].rsplit(" ", 1)[0])
    rest = ab[len(short):].strip() if ab.startswith(short) else ab
    rest = rest if len(rest) >= 40 else ""
    fi = [x for x in [("Find us", d["address"]) if d["address"] else None, ("Call", d["phone"]) if d["phone"] else None, ("Open", d["hours"][0][0] + " " + d["hours"][0][1]) if d["hours"] else None] if x]
    show_story = bool(rest or fi); para = f'<p class="lead">{E(rest)}</p>' if rest else ""
    secs = [("story", "About")] if show_story else []
    has_menu = bool(d["menu"] or d.get("menu_url")); secs += [("menu", "Menu")] if has_menu else []; secs += [("gallery", "Gallery")] if len(ph) >= 4 else []; secs += [("visit", "Visit")]
    lg = logo_markup(d.get("logo"), n, bg)
    chips = "".join(f'<span class="chip">{E(c)}</span>' for c in [d.get("city"), d["hours"][0][0] + " " + d["hours"][0][1] if d["hours"] else None] if c)
    story = menu = gal = ""
    if show_story:
        facts = "".join(f'<div class="fact"><b>{E(label)}</b><span>{E(value)}</span></div>' for label, value in fi)
        story = (f'<p class="story-copy">{E(rest)}</p>' if rest else "") + (f'<div class="facts">{facts}</div>' if facts else "")
    if d["menu"]:
        cards, current_section = [], None
        for item in d["menu"]:
            section_name = item.get("section") or "Menu"
            if section_name != current_section:
                cards.append(f'<h3 class="menu-section-title">{E(section_name)}</h3>')
                current_section = section_name
            details = f'<p class="menu-item-details">{E(item.get("desc") or "")}</p>' if item.get("desc") else ""
            cards.append(
                '<article class="menu-card"><div class="menu-card-top">'
                f'<span class="menu-item-title">{E(item["name"])}</span>'
                f'<span class="menu-item-price-tag">{E(item.get("price") or "")}</span>'
                f'</div>{details}</article>'
            )
        menu = '<div class="menu-layout">' + "".join(cards) + "</div>"
    if d.get("menu_url"):
        menu += f'<p class="menu-link"><a class="btn-main" href="{E(d["menu_url"])}" target="_blank" rel="noopener">View the full menu</a></p>'
    if len(ph) >= 4:
        gal = '<div class="gallery-showcase">' + "".join(
            f'<figure class="gallery-item"><img src="{E(p)}" alt="{E(d["name"])} photo" loading="lazy"></figure>'
            for p in ph[:6]
        ) + "</div>"
    hrs = "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td></tr>" for a, b in d["hours"])
    hours_table = f'<table class="hours-list"><tbody>{hrs}</tbody></table>' if hrs else ""
    contact = (f'<p class="visit-address">{E(d["address"])}</p>' if d.get("address") else "")
    contact += f'<p><a class="btn-alt" href="tel:{tel}">Call {E(d["phone"])}</a></p>' if d.get("phone") else ""
    contact += f'<p><a class="btn-alt" href="mailto:{E(d["email"])}">Email</a></p>' if d.get("email") else ""
    visit = hours_table + contact
    order = f'<div class="band"><div class="wrap"><h2>Order ahead</h2><a class="btn" href="{E(d["order_url"])}" target="_blank" rel="noopener">Order online</a></div></div>' if d.get("order_url") else ""
    soc = "".join(f'<a href="{E(u)}" target="_blank" rel="noopener">{l}</a>' for l, u in [("Instagram", d.get("ig")), ("Facebook", d.get("fb"))] if u)
    vid = f'<video autoplay muted loop playsinline poster="{E(d.get("poster") or "")}"><source src="{E(d["video"])}" type="video/mp4"></video>' if d.get("video") and hero == "full" else ""
    rep = {"NAME": n, "FONTLINK": "https://fonts.googleapis.com/css2?family=" + f[2] + "&display=swap", "BG": bg, "BG2": bg2, "INK": ink, "MUT": mut, "ACC": acc, "ACCINK": accink, "LINE": line, "DISP": f[0], "BODY": f[1], "RAD": ["999px", "6px", "0"][seed % 3],
           "HERO": hero, "LOGO": lg, "NAV": "".join(f'<li><a href="#{a}">{b}</a></li>' for a, b in secs), "TEL": tel, "PHONE": E(d["phone"] or ""), "HEROIMG": E(ph[0]) if ph else "", "VIDEO": vid, "EYEBROW": E(" · ".join(x for x in [d["kind"].title() if d["kind"] != "grill" else "Kitchen", d.get("city")] if x)),
           "ABOUT_SHORT": E(short), "CTA1": "menu" if has_menu else "visit", "CTA1T": "View menu" if has_menu else "Visit", "CHIPS": chips,
           "HERO_NOTE": f'<div class="bento-quote-frame"><div style="font-weight:700;font-size:1.1rem;margin-bottom:.4rem;font-family:var(--disp)">{E(n)}</div><div style="color:var(--mut);font-size:.95rem">{E(short)}</div></div>' if short else "", "MENU_INTRO": "View the published menu." if d.get("menu_url") else "",
           "STRIP": "".join(f'<img src="{E(p)}" alt="">' for p in ph[1:4]) if hero == "type" else "", "STORY": story, "MENU": menu, "GALLERY": gal, "VISIT": visit, "ORDER": order, "SOCIALS": soc, "DIR": dirn, "STOCK_NOTE": '<p class="stock-note">Some imagery is illustrative stock photography.</p>' if d.get("has_stock_photos") else ""}
    for k, v in rep.items(): t = t.replace("{{%s}}" % k, v)
    if not has_menu:
        t = re.sub(r'<section\b(?=[^>]*\bid=["\']menu["\'])[^>]*>.*?</section>', "", t, flags=re.I | re.S)
    if len(ph) < 4:
        t = re.sub(r'<section\b(?=[^>]*\bid=["\']gallery["\'])[^>]*>.*?</section>', "", t, flags=re.I | re.S)
    t = re.sub(r"<p\b[^>]*>\s*</p>", "", t, flags=re.I)
    if not re.search(r'<meta[^>]+name=["\']robots["\']', t, re.I):
        t = re.sub(r"</head\s*>", '<meta name="robots" content="noindex,nofollow">\n</head>', t, count=1, flags=re.I)
    safety_css = "<style>html,body{max-width:100%;overflow-x:clip}*,*::before,*::after{min-width:0}img,video,iframe{max-width:100%}.menu-layout,.gallery-showcase{grid-template-columns:repeat(auto-fit,minmax(min(100%,16rem),1fr))}.story-content,.visit-hub,.story-card-grid{min-width:0}.facts{display:grid;gap:.7rem;margin-top:1.2rem}.fact{display:flex;gap:.6rem;flex-wrap:wrap}.menu-section-title{grid-column:1/-1;margin-top:1rem}.menu-link{margin-top:1.5rem}</style>"
    t = re.sub(r"</head\s*>", safety_css + "</head>", t, count=1, flags=re.I)
    if not re.search(r"<meta[^>]+name=['\"]description['\"]", t, re.I):
        description = (short or "").strip()
        if has_menu:
            description = (description + " " if description else "") + f"View the menu and visit information for {d['name']} on this website."
        elif d.get("address") or d.get("phone"):
            description = (description + " " if description else "") + f"Find contact and visit information for {d['name']} on this website."
        else:
            description = f"Website concept for {d['name']}."
        t = re.sub(r"</title\s*>", lambda m: m.group(0) + f'<meta name="description" content="{E(description)}">', t, count=1, flags=re.I)
    assert not re.search(r"\{\{\w+\}\}", t); return t, {"theme": th, "hero": hero, "template": template_meta["id"], "template_file": template_file}
