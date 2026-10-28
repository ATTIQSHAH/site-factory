import hashlib, html, os, re, urllib.parse as up
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
def build3(d):
    """d keys: name, slug, phone, email, address, city, hours(list of (day,time)), about, logo(file,tone), photos(list of rel paths), video, poster, menu(list), menu_url, order_url, ig, fb, web, kind"""
    t = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "premium.html"), encoding="utf-8").read()
    seed = int(hashlib.md5(d["slug"].encode()).hexdigest()[:8], 16); th = THEMES[d["kind"]][seed % 3]; bg, bg2, ink, mut, acc, line = PAL[th]
    acc = safe_acc(acc, bg, ink); accink = "#111111" if cr(acc, "#111111") >= cr(acc, "#ffffff") else "#ffffff"
    f = FONTS[(seed // 3) % 4]; ph = d["photos"]; hero = ["full", "split", "type"][(seed // 12) % 3]
    if hero != "type" and not ph and not d.get("video"): hero = "type"
    if hero == "type" and len(ph) < 3: hero = "full" if (ph or d.get("video")) else "type"
    n, tel = E(d["name"]), re.sub(r"[^0-9+]", "", d["phone"] or "")
    tel = ("+1" + tel) if tel and not tel.startswith("+") and len(tel) == 10 else tel
    q = up.quote(d["address"] or d["name"]); dirn = f"https://www.google.com/maps/search/?api=1&query={q}"
    ab = re.sub(r"[\s.\u2026]*(\.\.\.|\u2026)\s*$", "", (d.get("about") or "").strip()).strip()
    m = re.match(r"(.{40,150}?[.!?])(\s|$)", ab); short = m.group(1) if m else (ab if len(ab) <= 150 else ab[:150].rsplit(" ", 1)[0])
    rest = ab[len(short):].strip() if ab.startswith(short) else ab
    rest = rest if len(rest) >= 40 else ""
    fi = [x for x in [("Find us", d["address"]) if d["address"] else None, ("Call", d["phone"]) if d["phone"] else None, ("Open", d["hours"][0][0] + " " + d["hours"][0][1]) if d["hours"] else None] if x]
    show_story = bool(rest or fi); para = f'<p class="lead">{E(rest)}</p>' if rest else ""
    secs = [("story", "About")] if show_story else []
    has_menu = bool(d["menu"] or d.get("menu_url")); secs += [("menu", "Menu")] if has_menu else []; secs += [("gallery", "Gallery")] if len(ph) >= 4 else []; secs += [("visit", "Visit")]
    lg = f'<img src="{E(d["logo"][0])}" alt="{n}" class="{"pill" if d["logo"][1] == "light" else "pillw"}">' if d.get("logo") else n
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
        link = f'<a class="btn s" href="{E(d["menu_url"])}" target="_blank" rel="noopener">Full menu</a>' if d.get("menu_url") else ""
        menu = f'<section class="alt" id="menu"><div class="wrap"><div class="rv"><span class="eyebrow">Menu</span><h2>From the kitchen</h2></div><div class="menu rv">{out}</div>{link}</div></section>'
    elif d.get("menu_url"):
        bgi = f"style=\"background-image:url('{E(ph[-1])}')\"" if ph else ""; nc = "" if ph else " nophoto"
        menu = f'<section class="alt" id="menu"><div class="wrap"><div class="rv"><span class="eyebrow">Menu</span><h2>See what is cooking</h2></div><div class="mcta rv{nc}" {bgi}>{"" if ph else "<p class=lead style=position:relative;z-index:2;margin:0 0 18px>Full menu and prices are on their website.</p>"}<a class="btn p" href="{E(d["menu_url"])}" target="_blank" rel="noopener">View the full menu</a></div></div></section>'
    if len(ph) >= 4: gal = '<section id="gallery"><div class="wrap"><div class="rv"><span class="eyebrow">Gallery</span><h2>A closer look</h2></div><div class="gal rv">' + "".join(f'<img src="{E(p)}" alt="" loading="lazy">' for p in ph[:4]) + "</div></div></section>"
    hrs = "".join(f"<tr><td>{E(a)}</td><td>{E(b)}</td></tr>" for a, b in d["hours"])
    left = (f'<p class="lead">{E(d["address"])}</p>' if d["address"] else "") + (f'<table class="hours">{hrs}</table>' if hrs else "") + f'<a class="btn p" href="tel:{tel}">Call now</a>' + (f'<a class="btn s" href="{dirn}" target="_blank" rel="noopener">Get directions</a>' if d["address"] else "") + (f'<a class="btn s" href="mailto:{E(d["email"])}">Email</a>' if d["email"] else "")
    right = f'<iframe class="map rv" loading="lazy" src="https://www.google.com/maps?q={q}&output=embed"></iframe>' if d["address"] else ""
    visit = f'<section class="alt" id="visit"><div class="wrap {"two" if right else ""}"><div class="rv"><span class="eyebrow">Visit</span><h2>Plan your visit</h2>{left}</div>{right}</div></section>'
    order = f'<div class="band"><div class="wrap"><h2>Order ahead</h2><a class="btn" href="{E(d["order_url"])}" target="_blank" rel="noopener">Order online</a></div></div>' if d.get("order_url") else ""
    soc = "".join(f'<a href="{E(u)}" target="_blank" rel="noopener">{l}</a>' for l, u in [("Instagram", d.get("ig")), ("Facebook", d.get("fb"))] if u)
    vid = f'<video autoplay muted loop playsinline poster="{E(d.get("poster") or "")}"><source src="{E(d["video"])}" type="video/mp4"></video>' if d.get("video") and hero == "full" else ""
    rep = {"NAME": n, "FONTLINK": "https://fonts.googleapis.com/css2?family=" + f[2] + "&display=swap", "BG": bg, "BG2": bg2, "INK": ink, "MUT": mut, "ACC": acc, "ACCINK": accink, "LINE": line, "DISP": f[0], "BODY": f[1], "RAD": ["999px", "6px", "0"][seed % 3],
           "HERO": hero, "LOGO": lg, "NAV": "".join(f'<li><a href="#{a}">{b}</a></li>' for a, b in secs), "TEL": tel, "PHONE": E(d["phone"] or ""), "HEROIMG": E(ph[0]) if ph else "", "VIDEO": vid, "EYEBROW": E(" · ".join(x for x in [d["kind"].title() if d["kind"] != "grill" else "Kitchen", d.get("city")] if x)),
           "ABOUT_SHORT": E(short), "CTA1": "menu" if has_menu else "visit", "CTA1T": "See the menu" if has_menu else "Visit us", "CHIPS": chips,
           "STRIP": "".join(f'<img src="{E(p)}" alt="">' for p in ph[1:4]) if hero == "type" else "", "STORY": story, "MENU": menu, "GALLERY": gal, "VISIT": visit, "ORDER": order, "SOCIALS": soc, "DIR": dirn}
    for k, v in rep.items(): t = t.replace("{{%s}}" % k, v)
    assert not re.search(r"\{\{\w+\}\}", t); return t, {"theme": th, "hero": hero}
