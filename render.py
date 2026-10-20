import csv, re, sys, os, html
from urllib.parse import urlparse
U = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates") + "/"
TPL = {"coffee": U+"coffee.html", "restaurant": U+"resturent.html", "fastfood": U+"FastFood.html"}
IMG = lambda i, w=800: f"https://images.unsplash.com/photo-{i}?q=80&w={w}&auto=format&fit=crop"
# Only image IDs taken from the uploaded templates (known good)
ABOUT = {"coffee": "1447933601403-0c666c7d248c", "restaurant": "1556742026-121376e409c7"}
CARDS = {"restaurant": ["1559847844-5315695dadae", "1553621042-f6e147245715", "1544025162-d76694265947"],
         "pizza": ["1513104890138-7c749659a591", "1574071318508-1cdbab80d002"],
         "burger": ["1568901346375-23c9450c58cd"], "coffee": []}
TITLES = ["Signature Plates", "Chef's Favourites", "House Specials"]
CTA = {"coffee": "Contact", "restaurant": "Contact Us", "fastfood": "Order / Contact"}
COPY = {"coffee": ("Coffee & Café", "A warm place for great coffee, fresh bakes and good company."),
        "restaurant": ("Dining", "Good food, a welcoming table and a menu made to be shared."),
        "fastfood": ("Fresh • Fast", "Made fresh, served hot, ready when you are.")}
def kind(n):
    n = n.lower()
    if re.search(r"pizza|pizzeria|burger", n): return "fastfood"
    if re.search(r"coffee|cafe|café|bakery|bread|bake|cakes|dessert|cookie|macaron", n): return "coffee"
    return "restaurant"
def sub(n): return "burger" if "burger" in n.lower() else "pizza"
def slug(n): return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", n.lower().replace("é","e").replace("ê","e"))).strip("-")
OVR = """<style>
header{background:#fff!important;backdrop-filter:none!important}
.logo,.nav-links a{color:#1d1d1d!important}.logo span{color:#1d1d1d!important}
.btn-outline{background:#fff!important;color:#1d1d1d!important;border:2px solid #1d1d1d!important}
.btn-outline:hover{background:#1d1d1d!important;color:#fff!important}
.hero .btn-outline{border-color:#fff!important}
.menu-img img{width:100%;height:100%;object-fit:cover}.menu-img{background:#d9d2c5}
.hero{background-color:#222!important;box-shadow:inset 0 0 0 3000px rgba(0,0,0,.55)!important}.hero::before,.hero::after{display:none!important}
.hero h1,.hero p{color:#fff!important}.hero-badge{background:#fff!important;color:#1d1d1d!important;border:none!important;padding:6px 14px;display:inline-block}
.contact-details a{color:#1d1d1d!important;text-decoration:underline}
.demo-bar{position:fixed;left:0;right:0;bottom:0;background:#111;color:#fff;padding:9px 14px;text-align:center;font:14px/1.3 sans-serif;z-index:3000}
body{padding-bottom:40px}.cbtn{margin:6px 8px 0 0;padding:12px 24px!important;font-size:.95rem!important;display:inline-block}
</style>"""
def build(r, k):
    e = html.escape; n = e(r["Name"].strip()); ph = r["Phone"].strip(); em = r["Email"].strip()
    ig, fb, web = r["Instagram"].strip(), r["Facebook"].strip(), r["Website"].strip()
    B = "" if k == "restaurant" else "btn "
    ph0 = (r.get("photos") or [None])[0]; lg = f'<img src="{e(r["logo"])}" alt="{n}" style="height:46px;width:auto;max-width:220px;object-fit:contain" onerror="this.outerHTML=\'{n}\'">' if r.get("logo") else None
    badge, tag = COPY[k]
    t = open(TPL[k], encoding="utf-8-sig").read().replace("\r", "")
    head = t[:t.find("<body")]
    head = re.sub(r"<title>.*?</title>", f"<title>{n} | Demo Website</title>", head, flags=re.S)
    hero_bg = f"<style>.hero{{background-image:url('{ph0}')!important;background-size:cover!important;background-position:center!important}}</style>" if ph0 else ""
    head = head.replace("</head>", '<meta name="robots" content="noindex,nofollow">' + OVR + hero_bg + "\n</head>") if "</head>" in head else head + OVR + hero_bg + "</head>"
    links = [("#home", "Home")] + ([("#about", "About")] if k != "fastfood" else []) + [("#menu", "Menu"), ("#contact", "Contact")]
    nav = "".join(f'<li><a href="{h}">{l}</a></li>' for h, l in links)
    mark = f'<div class="logo-mark">{n[0]}</div>' if k == "fastfood" else ""
    wrap = {"coffee": "nav-wrapper", "restaurant": "container nav-wrapper", "fastfood": "nav-wrapper container"}[k]
    cta_cls = {"coffee": "btn btn-outline nav-cta", "restaurant": "reservation-btn", "fastfood": "btn btn-primary"}[k]
    hdr = (f'<header id="mainHeader"><div class="{wrap}"><a href="#home" class="logo">{lg or mark + n}</a>'
           f'<ul class="nav-links" id="navLinks">{nav}</ul><a href="#contact" class="{cta_cls}">{CTA[k]}</a>'
           '<div class="mobile-toggle" id="mobileToggle"><span></span><span></span><span></span></div></div></header>')
    pc = "btn-primary" if k != "fastfood" else "btn-dark"
    hero = (f'<section class="hero" id="home"><div class="hero-content"><div class="hero-badge">{badge}</div><h1>Welcome to {n}</h1><p>{tag}</p>'
            f'<div class="hero-actions"><a href="#menu" class="{B}btn-primary">View Menu</a><a href="#contact" class="{B}btn-outline">Get in Touch</a></div></div></section>')
    about = ""
    if k != "fastfood":
        g = "heritage-grid" if k == "coffee" else "about-grid"
        about = (f'<section class="{"heritage" if k=="coffee" else "about"}" id="about"><div class="container"><div class="section-header"><span class="eyebrow">About Us</span><h2>Our Story</h2></div>'
                 f'<div class="{g}"><div class="heritage-text"><h3>{n}</h3><p>{e(r.get("about") or "A local favourite, ready to welcome you.")}</p>'
                 f'<a href="#contact" class="{B}btn-outline" style="margin-top:24px;">Contact Us</a></div><div class="heritage-img"><img src="{e(r["photos"][1] if len(r.get("photos") or []) > 1 else (ph0 or IMG(ABOUT[k],1200)))}" alt="{n}" onerror="this.style.display=\'none\'"></div></div></div></section>')
    imgs = CARDS["restaurant"] if k == "restaurant" else CARDS[sub(r["Name"]) if k == "fastfood" else "coffee"]
    ttl = TITLES if k != "coffee" else ["Coffee & Espresso", "Tea & Cold Drinks", "Fresh Bakes"]
    items = imgs if imgs else [None] * 3
    cards = "".join(
        f'<div class="menu-card">' + (f'<div class="menu-img"><img src="{IMG(i)}" alt="{ttl[x]}" onerror="this.parentNode.style.display=\'none\'"></div>' if i else '')
        + f'<div class="menu-body"><h3>{ttl[x]}</h3><p>Ask us about today\'s selection.</p></div></div>'
        for x, i in enumerate(items))
    mi = r.get("menu") or []
    if mi:
        cards = "".join(f'<div class="menu-card"><div class="menu-body"><h3>{e(m["name"])}</h3><p>{e(m.get("desc",""))}</p>' + (f'<div class="price-row"><span class="price">{e(m["price"])}</span></div>' if m.get("price") else '') + '</div></div>' for m in mi)
    menu = (f'<section class="menu" id="menu"><div class="container"><div class="section-header"><span class="eyebrow">Menu</span><h2>Menu Highlights</h2></div>'
            f'<div class="menu-grid">{cards}</div></div></section>')
    rows = ([("Address", e(r["address"]))] if r.get("address") else []) + ([("Hours", e(r["hours"]))] if r.get("hours") else []) + [("Phone", f'<a href="tel:{re.sub(r"[^0-9+]","",ph)}">{e(ph)}</a>'), ("Email", f'<a href="mailto:{e(em)}">{e(em)}</a>'), ("Website", f'<a href="{e(web)}">{e(urlparse(web).netloc)}</a>')]
    det = "".join(f"<li><strong>{a}</strong><span>{b}</span></li>" for a, b in rows)
    bt = lambda h, l, c="btn-primary": f'<a href="{e(h)}" class="{B}{c} cbtn" target="_blank" rel="noopener">{l}</a>'
    contact = (f'<section class="contact" id="contact"><div class="container"><div class="contact-grid"><div class="contact-info"><h3>Visit & Contact</h3><p>Call, email or message {n} directly.</p><ul class="contact-details">{det}</ul></div>'
               f'<div class="contact-form"><h3 style="margin-bottom:18px">Reach Us</h3>{bt("tel:"+re.sub(r"[^0-9+]","",ph),"Call Now")}{bt("mailto:"+em,"Email Us","btn-dark" if k!="coffee" else "btn-gold")}'
               f'{bt(ig,"Instagram","btn-dark" if k!="coffee" else "btn-gold")}{bt(fb,"Facebook","btn-dark" if k!="coffee" else "btn-gold")}</div></div></div></section>')
    foot = f'<footer><div class="container"><div class="copyright footer-bottom">&copy; 2026 {n}. All rights reserved.</div></div></footer>'
    bar = f'<div class="demo-bar">Demo website concept for {n}, prepared by Solvexa</div>'
    js = ("<script>var t=document.getElementById('mobileToggle'),l=document.getElementById('navLinks');t.onclick=function(){"
          "if(l.style.display==='flex'){l.style.display='none'}else{l.style.cssText='display:flex;flex-direction:column;position:absolute;top:70px;left:0;width:100%;background:#fff;padding:24px;z-index:1500'}}</script>")
    return head + "<body>" + hdr + hero + about + menu + contact + foot + bar + js + "</body></html>"
GENERIC = {"catering","events","giftshop","press","support","corporate","marketing","reservation","reservations","orders","manager","lee"}
def main(src, out):
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig"))); seen = {}; idx = []
    for r in rows:
        k = kind(r["Name"]); s = slug(r["Name"]); seen[s] = seen.get(s, 0) + 1
        if seen[s] > 1: s += f"-{seen[s]}"
        os.makedirs(f"{out}/{s}", exist_ok=True)
        open(f"{out}/{s}/index.html", "w", encoding="utf-8").write(build(r, k))
        lp, dom = r["Email"].split("@")[0].lower(), r["Email"].split("@")[-1].lower().rsplit(".", 1)[0]
        q = "check: generic mailbox" if lp in GENERIC else ("check: email domain differs from website" if dom.replace("-", "") not in urlparse(r["Website"]).netloc.replace("-", "").lower() else "ok")
        idx.append({"name": r["Name"], "email": r["Email"], "phone": r["Phone"], "website": r["Website"], "instagram": r["Instagram"], "facebook": r["Facebook"],
                    "template": k, "site_path": f"/{s}/", "site_url": "", "email_quality": q, "review_status": "pending", "email_status": ""})
    w = csv.DictWriter(open(f"{out}/websites_tab.csv", "w", newline="", encoding="utf-8"), fieldnames=list(idx[0])); w.writeheader(); w.writerows(idx)
    print(len(idx), "sites written")
if __name__ == "__main__": main(sys.argv[1], sys.argv[2])
