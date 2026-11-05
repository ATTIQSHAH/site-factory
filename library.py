"""Growing template library: classify the business, reuse a vetted template (capped uses), or have Gemini design a new one, test it, and save it."""
import json, os, re, random
from jinja2.sandbox import SandboxedEnvironment
from PIL import Image
import artdir
LIB = os.getenv("LIB_DIR", "library"); CAP = int(os.getenv("TEMPLATE_MAX_USES", "3")); TYPES = ["coffee", "bakery", "grill", "restaurant"]
ENV = SandboxedEnvironment(autoescape=True)
def load(): p = f"{LIB}/index.json"; return json.load(open(p)) if os.path.exists(p) else []
def save(idx): os.makedirs(LIB, exist_ok=True); json.dump(idx, open(f"{LIB}/index.json", "w"), indent=1)
def classify(name, about, items, fallback):
    try:
        r = artdir.gem([{"text": f"Business: {name}\nDescription: {about}\nMenu items: {[i['name'] for i in items[:12]]}\nClassify into exactly one of: coffee (coffee shops, cafes), bakery (bakeries, desserts, cakes), grill (BBQ, burgers, pizza, tacos, pubs, breweries), restaurant (all other restaurants). Return JSON {{\"type\": \"...\"}}"}], js=True)
        return r["type"] if r.get("type") in TYPES else fallback
    except Exception: return fallback
def ctx(d):
    g = {}
    for i in d["menu"]: g.setdefault(i.get("section") or "Menu", []).append(i)
    tel = re.sub(r"[^0-9+]", "", d["phone"] or ""); tel = "+1" + tel if tel and not tel.startswith("+") and len(tel) == 10 else tel
    q = __import__("urllib.parse").parse.quote(d["address"] or d["name"])
    return {"name": d["name"], "type": d["kind"], "city": d.get("city") or "", "about": d.get("about") or "", "phone": d["phone"] or "", "tel": tel, "email": d["email"] or "", "address": d["address"] or "", "map_q": q,
            "directions_url": f"https://www.google.com/maps/search/?api=1&query={q}", "hours": d["hours"], "logo": d["logo"][0] if d.get("logo") else "", "logo_chip": ("dark" if d["logo"][1] == "light" else "white") if d.get("logo") else "",
            "photos": d["photos"], "video": d.get("video") or "", "menu_groups": [{"title": k, "items": v} for k, v in g.items()], "menu_url": d.get("menu_url") or "", "order_url": d.get("order_url") or "", "instagram": d.get("ig") or "", "facebook": d.get("fb") or ""}
RULES = artdir.RULES.replace("building ONE self-contained HTML file", "writing ONE reusable Jinja2 template (a self-contained HTML file with inline CSS and JS)").replace("Return ONLY the complete HTML document, no markdown fences.", "") + """
TEMPLATE RULES
- It will be rendered many times with different businesses. Use ONLY these variables: name, type, city, about, phone, tel, email, address, map_q, directions_url, hours (list of [day, time]), logo (path or empty), logo_chip ('dark', 'white' or empty), photos (list of paths, may be 0 to 8), video (path or empty), menu_groups (list of {title, items:[{name, price, desc}]}), menu_url, order_url, instagram, facebook.
- Guard EVERY optional element with {% if %}. The page must still look finished with: no photos, no menu, no hours, no logo, no address, no video. Never index photos[n] without checking photos|length. Reuse photos only when there are enough.
- Never hard-code any business facts, names, dishes, colours of a specific brand or images. The design is the reusable part.
- Return ONLY the Jinja2/HTML source, no markdown fences."""
def sample(scn, root):
    d = {"name": "Harbor Street Kitchen", "kind": "restaurant", "city": "Austin", "about": "A neighbourhood kitchen serving seasonal plates and fresh bread. Open for lunch and dinner with a short wine list.", "phone": "(512) 555-0199", "email": "hi@example.com",
         "address": "120 Harbor St, Austin, TX 78701", "hours": [["Mon to Fri", "11 AM to 9 PM"], ["Sat to Sun", "10 AM to 10 PM"]], "logo": None, "photos": [], "video": None, "menu": [], "menu_url": "https://example.com/menu", "order_url": "https://example.com/order", "ig": "https://instagram.com/x", "fb": "https://facebook.com/x"}
    if scn == "full":
        os.makedirs(f"{root}/full/img", exist_ok=True); random.seed(5)
        for n in range(6):
            im = Image.new("RGB", (1600, 1000), tuple(random.randint(40, 200) for _ in range(3)))
            for _ in range(40): x, y = random.randint(0, 1500), random.randint(0, 900); im.paste(tuple(random.randint(30, 230) for _ in range(3)), (x, y, x + random.randint(60, 400), y + random.randint(40, 300)))
            im.save(f"{root}/full/img/p{n}.jpg")
        Image.new("RGBA", (300, 90), (255, 255, 255, 255)).save(f"{root}/full/img/logo.png")
        d.update(photos=[f"img/p{n}.jpg" for n in range(6)], logo=("img/logo.png", "light"), menu=[{"section": s, "name": f"Dish {s[0]}{n}", "price": f"${8 + n}", "desc": "House made with seasonal ingredients"} for s in ("Starters", "Mains") for n in range(5)])
    elif scn == "partial":
        os.makedirs(f"{root}/partial/img", exist_ok=True); Image.new("RGB", (1600, 1000), (120, 90, 60)).save(f"{root}/partial/img/p0.jpg"); d.update(photos=["img/p0.jpg"], hours=[], address="")
    else: d.update(about="", hours=[], address="", email="")
    return d
def render(t, d): return ENV.from_string(open(f"{LIB}/{t['id']}.j2", encoding="utf-8").read()).render(**ctx(d))
def test_template(path_src, direction, root="/tmp/libqa"):
    """Render a candidate in 3 data scenarios; return (issues, score)."""
    tpl = ENV.from_string(path_src); issues = []; score = 0
    for scn in ("full", "partial", "bare"):
        d = sample(scn, root); os.makedirs(f"{root}/{scn}", exist_ok=True)
        try: open(f"{root}/{scn}/index.html", "w", encoding="utf-8").write(tpl.render(**ctx(d)))
        except Exception as e: return [f"{scn}: render error {str(e)[:80]}"], 0
        i, shots = artdir.qa(root, scn, 60 if scn == "bare" else 250); issues += [f"{scn}: {x}" for x in i]
        if scn == "full" and not i: score = float(artdir.critique(shots, "a sample restaurant (images are neutral placeholders; judge layout, type, spacing and distinctiveness only)").get("score", 0))
    return issues, score
def generate(idx, kind, hint=""):
    use = {}; [use.__setitem__(t["direction"], use.get(t["direction"], 0) + 1) for t in idx]; direction = artdir.pick(kind, use); tid = f"{kind}-{direction}-{len(idx) + 1:03d}"
    src, issues = None, []
    for _ in range(3):
        try:
            prompt = f"Design a reusable {kind} website template. DIRECTION: {artdir.DIRS[direction]}" + (f"\nPrevious attempt failed these checks, fix them:\n- " + "\n- ".join(issues) + "\nPREVIOUS SOURCE:\n" + src if src else "")
            src = re.sub(r"^```(?:html|jinja2?)?\s*|\s*```$", "", artdir.gem([{"text": prompt}], artdir.RULES.split("HARD RULES")[0] + RULES, False).strip())
            issues, score = test_template(src, direction)
            if not issues and score >= 7:
                os.makedirs(LIB, exist_ok=True); open(f"{LIB}/{tid}.j2", "w", encoding="utf-8").write(src)
                t = {"id": tid, "direction": direction, "types": [kind], "status": "new", "uses": 0, "score": round(score, 1)}; idx.append(t); save(idx); return t
            issues = issues or [f"critique score {score}"]
        except Exception as e: issues = [f"error {str(e)[:80]}"]
    return None
def make_site(d, root, slug, kind, fallback):
    idx = load(); ok = [t for t in idx if kind in t["types"] and t["status"] != "rejected" and t["uses"] < CAP]
    t = min(ok, key=lambda t: (t["uses"], -t["score"])) if ok else generate(idx, kind)
    if t is None: return fallback(d)
    try:
        html = render(t, d); os.makedirs(f"{root}/{slug}", exist_ok=True); open(f"{root}/{slug}/index.html", "w", encoding="utf-8").write(html); issues, _ = artdir.qa(root, slug)
    except Exception: issues = ["render failed"]
    if issues: print("template", t["id"], "failed on", slug, issues[:2]); return fallback(d)
    t["uses"] += 1; save(idx); return html, {"theme": t["direction"], "hero": t["id"], "ai_score": t["score"], "template_id": t["id"], "template_status": t["status"]}
