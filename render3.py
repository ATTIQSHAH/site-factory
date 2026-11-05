import hashlib, html, os, re, urllib.parse as up
from template_catalog import select as select_template
E = html.escape
PAL = {"cream": ("#f6f1e9", "#ece4d6", "#2a1f17", "#6d5f52", "#8a5a2b", "rgba(42,31,23,.14)"), "espresso": ("#171210", "#211a16", "#f3ebe0", "#b8a999", "#c8a26b", "rgba(255,255,255,.12)"),
 "sage": ("#eef0ea", "#e1e6dc", "#1d2a22", "#55635a", "#3f6b4f", "rgba(29,42,34,.14)"), "noir": ("#0e0e0f", "#17171a", "#f5f1ea", "#b9b2a6", "#d6a85c", "rgba(255,255,255,.12)"),
 "ivory": ("#faf6ef", "#f0e8da", "#241a17", "#6b5b54", "#8c2f2b", "rgba(36,26,23,.14)"), "slate": ("#14191f", "#1d242c", "#eef1f4", "#a5b0bb", "#d38b5d", "rgba(255,255,255,.12)"),
 "blush": ("#fbf1ee", "#f4e2dd", "#3a2224", "#7a5c5e", "#b4505a", "rgba(58,34,36,.14)"), "butter": ("#fff8e6", "#f8ecc8", "#33280f", "#6e6140", "#a6650d", "rgba(51,40,15,.14)"),
 "ember": ("#141010", "#1e1816", "#f6efe9", "#b9aaa0", "#e2552b", "rgba(255,255,255,.12)"), "paprika": ("#fff7ee", "#fbe9d4", "#2b1a10", "#6c5445", "#b83b05", "rgba(43,26,16,.14)")}
THEMES = {"coffee": ["cream", "espresso", "sage"], "restaurant": ["noir", "ivory", "slate"], "bakery": ["blush", "butter", "cream"], "grill": ["ember", "paprika", "slate"]}
FONTS = [("Playfair Display", "Inter", "Playfair+Display:wght@500;700&family=Inter:wght@400;500;600"), ("Fraunces", "DM Sans", "Fraunces:wght@500;700&family=DM+Sans:wght@400;500;600"),
         ("DM Serif Display", "Inter", "DM+Serif+Display&family=Inter:wght@400;500;600"), ("Cormorant Garamond", "Inter", "Cormorant+Garamond:wght@600;700&family=Inter:wght@400;500;600")]
def lum(h): h = h.lstrip("#"); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]; c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]; return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
def cr(a, b): x, y = sorted([lum(a), lum(b)], reverse=True); return (x + .05) / (y + .05)
def mix(a, b, t): a, b = a.lstrip("#"), b.lstrip("#"); return "#" + "".join("%02x" % round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (0, 2, 4))
def safe_acc(acc, bg, ink):
    t = 0
    while cr(acc, bg) < 4.5 and t < 1: t += .1; acc = mix(acc, ink, t)
    return acc
def niche(n):
    n = n.lower()
    if re.search(r"coffee|cafe|café|roast|espresso", n): return "coffee", "coffee shop"
    if re.search(r"bakery|bread|bake|cake|dessert|cookie|macaron|donut|pastry", n): return "bakery", "bakery pastries"
    if re.search(r"bbq|barbecue|smokehouse|smoke|burger|pizza|pizzeria|taco|trompo|birria|grill|brew|pub|cantina", n): return "grill", "grilled food"
    return "restaurant", "restaurant interior"
def logo_markup(logo, name, background):
    if not logo:
        return E(name)
    path, tone = logo
    bg = None
    if tone == "light" and lum(background) > 0.45:
        bg = "#171210"
    elif tone == "dark" and lum(background) < 0.18:
        bg = "#ffffff"
    style = (' style="background:' + bg + ';padding:6px 10px;border-radius:6px"') if bg else ""
    return '<img src="' + E(path) + '" alt="' + E(name) + '"' + style + '>'


def safe_http_url(value):
    parsed = up.urlsplit(str(value or "").strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        return ""
    return str(value).strip()


def safe_social_url(value, domain):
    raw = str(value or "").strip()
    if not raw:
        return ""
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw.lstrip("/")
    parsed = up.urlsplit(raw)
    if parsed.scheme.lower() not in ("http", "https") or parsed.hostname not in (domain, "www." + domain):
        return ""
    return raw


def build3(d):
    """d keys: name, slug, phone, email, address, city, hours(list of (day,time)), about, logo(file,tone), photos(list of rel paths), video, poster, menu(list), menu_url, order_url, ig, fb, web, kind"""
    menu_url = safe_http_url(d.get("menu_url"))
    order_url = safe_http_url(d.get("order_url"))
    ig = safe_social_url(d.get("ig"), "instagram.com")
    fb = safe_social_url(d.get("fb"), "facebook.com")
    template_file, template_meta = select_template(d["kind"], name=d["name"], about=d.get("about", ""), menu=d.get("menu", []))
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", template_file)
    if not os.path.isfile(template_path):
        template_file = "premium.html"
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", template_file)
        template_meta = {"id": "premium", "family": "fallback", "style": "Premium fallback", "file": template_file}
    t = open(template_path, encoding="utf-8").read()
    seed = int(hashlib.md5(d["slug"].encode()).hexdigest()[:8], 16)
    theme_kind = {"cafe": "coffee", "fastfood": "grill"}.get(d["kind"], d["kind"])
    palette = THEMES.get(theme_kind, THEMES["restaurant"])
    th = palette[seed % len(palette)]
    bg, bg2, ink, mut, acc, line = PAL[th]
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
    if not short:
        short = "Explore the menu, contact details and visit information for " + d["name"] + "."
    rest = ab[len(short):].strip() if ab.startswith(short) else ab
    rest = rest if len(rest) >= 40 else ""
    fi = [x for x in [("Find us", d["address"]) if d["address"] else None, ("Call", d["phone"]) if d["phone"] else None, ("Open", d["hours"][0][0] + " " + d["hours"][0][1]) if d["hours"] else None] if x]
    show_story = bool(rest or fi); para = f'<p class="lead">{E(rest)}</p>' if rest else ""
    about_anchor = "story" if template_file == "premium.html" else "about"
    secs = [(about_anchor, "About")] if show_story else []
    has_menu = bool(d["menu"] or menu_url); secs += [("menu", "Menu")] if has_menu else []; secs += [("gallery", "Gallery")] if len(ph) >= 4 else []; secs += [("visit", "Visit")]
    lg = logo_markup(d.get("logo"), d["name"], bg)
    chips = "".join(f'<span class="chip">{E(c)}</span>' for c in [d.get("city"), d["hours"][0][0] + " " + d["hours"][0][1] if d["hours"] else None] if c)
    story = menu = gal = ""
    if show_story:
        facts = "".join(f'<div class="fact"><b>{E(a)}</b><span>{E(b)}</span></div>' for a, b in fi)
        img = f'<div class="imgf rv"><img src="{E(ph[1] if len(ph) > 1 else ph[0])}" alt="{n}"></div>' if ph else ""
        story = f'<section id="story"><div class="wrap two {"flip" if seed % 2 else ""}"><div class="rv"><span class="eyebrow">About</span><h2>{"Our story" if rest else "The essentials"}</h2>{para}<div class="facts">{facts}</div></div>{img}</div></section>'
    if d["menu"]:
        out, cur = "", None
        for i in d["menu"]:
            s = i.get("section") or "Menu"
            if s != cur: out += f"<h3>{E(s)}</h3>"; cur = s
            out += f'<div class="it"><div><span>{E(i["name"])}</span><span>{E(i.get("price") or "")}</span></div>' + (f'<small>{E(i["desc"])}</small>' if i.get("desc") else "") + "</div>"
        link = f'<a class="btn s" href="{E(menu_url)}" target="_blank" rel="noopener">Full menu</a>' if menu_url else ""
        menu = f'<section class="alt" id="menu"><div class="wrap"><div class="rv"><span class="eyebrow">Menu</span><h2>From the kitchen</h2></div><div class="menu rv">{out}</div>{link}</div></section>'
    elif menu_url:
        bgi = f"style=\"background-image:url('{E(ph[-1])}')\"" if ph else ""; nc = "" if ph else " nophoto"
        menu = f'<section class="alt" id="menu"><div class="wrap"><div class="rv"><span class="eyebrow">Menu</span><h2>See what is cooking</h2></div><div class="mcta rv{nc}" {bgi}>{"" if ph else "<p class=lead style=position:relative;z-index:2;margin:0 0 18px>Full menu and prices are on their website.</p>"}<a class="btn p" href="{E(menu_url)}" target="_blank" rel="noopener">View the full menu</a></div></div></section>'
    gallery_photos = ph[4:6] if hero == "type" else ph[2:6]
    if len(gallery_photos) >= 2:
        gal = '<section id="gallery"><div class="wrap"><div class="rv"><span class="eyebrow">Gallery</span><h2>A closer look</h2></div><div class="gal rv">' + "".join(f'<img src="{E(p)}" alt="" loading="lazy">' for p in gallery_photos) + "</div></div></section>"
    hrs = "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td></tr>" for a, b in d["hours"])
    left = (f'<p class="lead">{E(d["address"])}</p>' if d["address"] else "") + (f'<table class="hours">{hrs}</table>' if hrs else "") + f'<a class="btn p" href="tel:{tel}">Call now</a>' + (f'<a class="btn s" href="{dirn}" target="_blank" rel="noopener">Get directions</a>' if d["address"] else "") + (f'<a class="btn s" href="mailto:{E(d["email"])}">Email</a>' if d["email"] else "")
    right = f'<iframe class="map rv" loading="lazy" src="https://www.google.com/maps?q={q}&output=embed"></iframe>' if d["address"] else ""
    visit = f'<section class="alt" id="visit"><div class="wrap {"two" if right else ""}"><div class="rv"><span class="eyebrow">Visit</span><h2>Plan your visit</h2>{left}</div>{right}</div></section>'
    if template_file == "premium.html":
        order = f'<div class="band"><div class="wrap"><h2>Order ahead</h2><a class="btn" href="{E(order_url)}" target="_blank" rel="noopener">Order online</a></div></div>' if order_url else ""
    else:
        target_url = order_url or menu_url
        action_label = "Order online" if order_url else "View the menu"
        order = ('<div class="cta-hub"><h2>Ready to explore the menu?</h2><p>Check current offerings and ordering details directly with ' + n + '.</p><a class="btn-main" href="' + E(target_url) + '" target="_blank" rel="noopener">' + action_label + '</a></div>') if target_url else ""
    soc = "".join(f'<a href="{E(u)}" target="_blank" rel="noopener">{l}</a>' for l, u in [("Instagram", ig), ("Facebook", fb)] if u)
    vid = f'<video autoplay muted loop playsinline poster="{E(d.get("poster") or "")}"><source src="{E(d["video"])}" type="video/mp4"></video>' if d.get("video") and hero == "full" else ""
    if template_file != "premium.html":
        story = '<p>' + E(ab) + '</p>' if ab else ""
        if d.get("menu"):
            parts = ['<div class="menu-layout">']
            current_section = None
            for item in d["menu"]:
                section = item.get("section") or "Menu"
                if section != current_section:
                    parts.append('<h3 class="menu-section-title">' + E(section) + '</h3>')
                    current_section = section
                price = '<span class="menu-item-price-tag">' + E(item.get("price", "")) + '</span>' if item.get("price") else ""
                details = '<p class="menu-item-details">' + E(item.get("desc", "")) + '</p>' if item.get("desc") else ""
                parts.append('<article class="menu-card"><div class="menu-card-top"><span class="menu-item-title">' + E(item["name"]) + '</span>' + price + '</div>' + details + '</article>')
            parts.append("</div>")
            menu = "".join(parts)
        elif menu_url:
            menu = '<a class="btn-main" href="' + E(menu_url) + '" target="_blank" rel="noopener">View the full menu</a>'
        else:
            menu = ""
        gal = '<div class="gallery-showcase">' + "".join(
            '<div class="gallery-item"><img src="' + E(photo) + '" alt="' + E(d["name"]) + '"></div>'
            for photo in (ph[4:6] if hero == "type" else ph[2:6])
        ) + '</div>' if len(ph) >= 4 else ""
        visit_parts = []
        if d["hours"]:
            visit_parts.append('<table class="hours-list"><tbody>' + "".join(
                '<tr><td>' + E(day) + '</td><td>' + E(hours) + '</td></tr>' for day, hours in d["hours"]
            ) + '</tbody></table>')
        if d.get("address"):
            visit_parts.append('<p class="visit-address">' + E(d["address"]) + '</p>')
        visit = "".join(visit_parts)
    rep = {"NAME": n, "FONTLINK": "https://fonts.googleapis.com/css2?family=" + f[2] + "&display=swap", "BG": bg, "BG2": bg2, "INK": ink, "MUT": mut, "ACC": acc, "ACCINK": accink, "LINE": line, "DISP": f[0], "BODY": f[1], "RAD": ["999px", "6px", "0"][seed % 3],
           "HERO": hero, "LOGO": lg, "NAV": "".join(f'<li><a href="#{a}">{b}</a></li>' for a, b in secs), "TEL": tel, "PHONE": E(d["phone"] or ""), "HEROIMG": E(ph[0]) if ph else "", "VIDEO": vid, "EYEBROW": E(" · ".join(x for x in [d["kind"].title() if d["kind"] != "grill" else "Kitchen", d.get("city")] if x)),
           "ABOUT_SHORT": E(short), "CTA1": "menu" if has_menu else "visit", "CTA1T": "See the menu" if has_menu else "Visit us", "CHIPS": chips,
           "STRIP": "".join(f'<img src="{E(p)}" alt="">' for p in ph[2:4]) if hero == "type" else "", "STORY": story, "MENU": menu, "GALLERY": gal, "VISIT": visit, "ORDER": order, "SOCIALS": soc, "DIR": dirn,
           "HERO_NOTE": '<div class="bento-quote-frame"><strong>Menu & visit details</strong><p>Use the links below to plan your visit.</p></div>',
           "STORY_PHOTO": ('<div class="story-photo-frame"><img src="' + E(ph[1]) + '" alt="' + n + '"></div>') if len(ph) > 1 else "",
           "MENU_INTRO": E("Featured items from the published menu.") if d.get("menu") else E("Explore the full menu and current ordering options."),
           "MAP_FRAME": ('<div class="map-frame" style="display:flex;align-items:center;justify-content:center;text-align:center;padding:2rem;background:var(--bg2)"><div><span class="section-tag">Find us</span><p>' + E(d["city"] or d["address"]) + '</p><a class="btn-main" href="' + E(dirn) + '" target="_blank" rel="noopener">Open in Maps</a></div></div>') if d.get("address") else ""}
    for k, v in rep.items():
        t = t.replace("{{%s}}" % k, v)
    # Optional template-specific fields absent from the selected design are omitted.
    while "{{" in t:
        start = t.find("{{")
        end = t.find("}}", start)
        if end < 0:
            break
        t = t[:start] + t[end + 2:]
    # Remove template marketing claims that cannot be proven from the business source.
    for claim in ("Michelin Guide 2026 · Tasting Menu", "36-Hour Fermentation · Stone Ground",
                  "Fresh Batch Roasted & Baked Daily", "Walk-ins always welcome.",
                  "Honoring genuine ingredients, slow preparation, and neighborly warmth.",
                  "Prepared fresh daily with seasonal harvests and time-honored recipes.",
                  "A glimpse into our kitchen, dining room, and daily creations."):
        t = t.replace(claim, "")
    description = E((d.get("about") or "").strip()[:155]) or E(
        "Explore contact details, location, menu and visit information for " + d["name"] + ".")
    if 'name="description"' not in t.lower() and "name='description'" not in t.lower():
        t = t.replace("</title>", '</title><meta name="description" content="' + description + '">', 1)
    if 'name="robots"' not in t.lower() and "name='robots'" not in t.lower():
        t = t.replace("</head>", '<meta name="robots" content="noindex,nofollow"></head>', 1)
    responsive_css = """
html, body { width: 100%; max-width: 100%; overflow-x: hidden; }
*, *::before, *::after { min-width: 0; }
img, video, iframe, table { max-width: 100%; }
body { overflow-wrap: anywhere; }
@media (max-width: 900px) {
  .hero { width: 100%; max-width: 100%; grid-template-columns: minmax(0, 1fr); padding: 4.5rem 1rem 2rem; gap: 1rem; }
  .hero > *, .bento-hero-left, .bento-hero-right { width: 100%; max-width: 100%; min-width: 0; }
  .bento-hero-left { padding: 1.5rem; }
  .nav-container { width: 100%; max-width: 100%; min-width: 0; flex-wrap: wrap; padding: .8rem 1rem; gap: .5rem; }
  .nav-brand { min-width: 0; max-width: 100%; flex: 1 1 180px; gap: .4rem; }
  .nav-brand img { max-width: 110px; max-height: 50px; width: auto; height: auto; }
  .nav-cta { font-size: .78rem; padding: .5rem .7rem; white-space: nowrap; }
  section { width: 100%; max-width: 100%; padding-left: 1rem; padding-right: 1rem; }
  .story-card-grid, .visit-hub { width: 100%; max-width: 100%; min-width: 0; grid-template-columns: minmax(0, 1fr); padding: 1.25rem; gap: 1.5rem; }
  .story-card-grid > *, .visit-hub > *, .section-header { min-width: 0; max-width: 100%; }
  .menu-layout, .gallery-showcase { grid-template-columns: minmax(0, 1fr); }
  .strip { width: 100%; max-width: 100%; grid-template-columns: minmax(0, 1fr); padding-left: 1rem; padding-right: 1rem; }
  .map-frame { width: 100%; max-width: 100%; min-width: 0; }
}
@media (max-width: 768px) {
  body .m { display: none !important; }
  body.has-scrolled .m { display: flex !important; left: 0; right: 0; bottom: 0; }
}
"""
    t = t.replace("</style>", responsive_css + "</style>", 1)
    assert not re.search(r"\{\{[A-Z0-9_]+\}\}", t), "Unresolved template token in " + template_file
    t = re.sub(r'<p([^>]*)>\s*</p>', '', t, flags=re.I)
    if template_file != "premium.html":
        if not ab:
            t = re.sub(r'<section[^>]+id="about"[^>]*>[\s\S]*?</section>', '', t, count=1)
        if not has_menu:
            t = re.sub(r'<section[^>]+id="menu"[^>]*>[\s\S]*?</section>', '', t, count=1)
        if not gal:
            t = re.sub(r'<section[^>]+id="gallery"[^>]*>[\s\S]*?</section>', '', t, count=1)
        if not d["hours"]:
            t = t.replace("Service Hours", "Contact & Location")
    t = t.replace("Daily Bake Schedule", "View details").replace("Direct Line", "Call the business")
    t = t.replace("Experience seasonal ingredients and dedicated hospitality curated every morning.", "Explore the menu and visit information below.")
    if template_file != "premium.html":
        if len(ph) > 1:
            t = re.sub(r'(<div class="story-photo-frame">\s*<img src=")[^"]+(")', lambda match: match.group(1) + E(ph[1]) + match.group(2), t, count=1)
        else:
            t = re.sub(r'<div class="story-photo-frame">[\s\S]*?</div>', '', t, count=1)
        if not ph:
            t = re.sub(r'<div class="bento-img-frame">[\s\S]*?</div>', '', t, count=1)
        t = re.sub(r'<img([^>]+)src=""([^>]*)>', '', t, flags=re.I)
    t = t.replace("</body>", '<script>(function(){var update=function(){document.body.classList.toggle("has-scrolled",window.scrollY>180);};window.addEventListener("scroll",update,{passive:true});update();})();</script></body>', 1)
    return t, {"theme": th, "hero": hero, "template_file": template_file,
               "template_id": template_meta.get("id", ""), "template_status": "selected"}
