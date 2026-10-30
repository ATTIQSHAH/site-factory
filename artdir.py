"""AI art director: picks a distinct design direction, has Gemini build a bespoke page from REAL facts/assets, then renders it, checks it, and revises."""
import base64, io, json, os, re, threading, time, functools, http.server, socketserver
import requests
from PIL import Image
KEY, MODEL = os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_DESIGN_MODEL", "gemini-2.5-flash")  # verify current model names and free limits
DIRS = {
 "editorial": "Editorial magazine: large high-contrast serif display, asymmetric 12-col grid, hairline rules, paper-white background, ink text, one restrained accent, generous whitespace, oversized pull-quote built only from real description text.",
 "dark_luxe": "Dark luxury: near-black, brass/gold accent, small wide-spaced uppercase labels, full-bleed photography, slow fades, centered formal composition, thin gold borders.",
 "rustic": "Rustic artisan: warm cream and earthy browns, sturdy slab or soft serif headings, stamped-badge details made with CSS only, ledger-style menu with dotted leaders, grounded and tactile.",
 "street": "Bold street food: oversized condensed type, hard colour blocks, thick borders, offset shadows, a marquee strip made from real menu item names, chunky buttons, high energy.",
 "nordic": "Minimal Nordic: pale neutrals, small refined sans type, strict grid, big photos with small captions, lots of air, no decoration, one muted accent.",
 "retro": "Retro diner: cream, cherry red and teal, rounded display type, stripe or checker motifs drawn in CSS, ticket-style menu cards, friendly and nostalgic but clean.",
 "botanical": "Fresh botanical: sage, olive and soft clay, organic SVG shapes, serif headings with airy sans body, rounded image masks, calm and natural.",
 "neon": "Night-time: deep navy or black with a single neon accent used sparingly on type and rules, sharp grid, tight uppercase headings, built for bars, pubs and breweries.",
 "mediterranean": "Mediterranean warmth: terracotta, olive and lime-wash cream, arched image masks via border-radius, humanist serif, sunlit and generous.",
 "split": "Modern split-screen: sticky image column beside scrolling text, big numerals, monochrome plus one saturated accent, confident asymmetry.",
 "roastery": "Craft roastery: kraft paper, espresso brown and cream, label-style typography, tight vertical rhythm, product-card menu, understated and premium.",
 "patisserie": "Soft patisserie: blush, butter and cream, rounded cards, a single script accent font used once, delicate, airy, photography forward."}
FIT = {"coffee": ["roastery", "nordic", "editorial", "botanical", "split"], "bakery": ["patisserie", "editorial", "nordic", "rustic", "botanical"],
       "grill": ["street", "rustic", "neon", "retro", "split"], "restaurant": ["dark_luxe", "editorial", "mediterranean", "botanical", "split", "neon", "rustic"]}
def pick(kind, used):
    c = FIT.get(kind, FIT["restaurant"]); return min(c, key=lambda k: (used.get(k, 0), c.index(k)))  # least-used first => variety across the batch
def palette(path):
    try: im = Image.open(path).convert("RGB").resize((120, 80)).quantize(colors=5).convert("RGB"); return ["#%02x%02x%02x" % c for _, c in sorted(im.getcolors(), reverse=True)[:4]]
    except Exception: return []
RULES = """You are a senior web designer building ONE self-contained HTML file (inline CSS and JS, at most two Google Fonts) for a restaurant or cafe demo pitch.
HARD RULES
- Use ONLY the facts and assets in the JSON brief. Never invent dishes, prices, reviews, awards, years, slogans or statistics. If a fact is missing, omit that element.
- Images: use only the given relative paths, with alt text and object-fit. Never hotlink. Give every hero text a solid overlay or panel so contrast is at least 4.5:1.
- Buttons are always solid-filled with readable text, never transparent over images.
- No emojis, no generic phrases (welcome to, passion for, culinary journey, unforgettable), no gradient blobs or glassmorphism, no lorem ipsum.
- Mobile-first and fluid (clamp() type, no horizontal scroll), tap targets at least 44px, sticky call/directions bar on mobile.
- Include when data exists: name or logo, tel: link, address with Google Maps link and embedded map iframe, hours, menu (all given items, grouped by section) or a button to menu_url, order button, social links, <meta name=robots content=noindex>, and a small fixed bar reading "Demo website concept for NAME".
- Follow the DESIGN DIRECTION strictly; compose a layout and section order that is distinct to this direction. Derive colours from the direction and the supplied dominant colours.
Return ONLY the complete HTML document, no markdown fences."""
def gem(parts, system=None, js=False):
    if not KEY: raise RuntimeError("no GEMINI_API_KEY")
    body = {"contents": [{"parts": parts}], "generationConfig": {"maxOutputTokens": 30000, **({"response_mime_type": "application/json"} if js else {})}}
    if system: body["systemInstruction"] = {"parts": [{"text": system}]}
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={KEY}", json=body, timeout=240).json()
    time.sleep(5); t = r["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(t) if js else re.sub(r"^```(?:html)?\s*|\s*```$", "", t.strip())
def brief(d, direction, folder):
    ph = d["photos"]; pal = palette(os.path.join(folder, ph[0])) if ph and not ph[0].startswith("/") else []
    return {"direction": direction, "direction_spec": DIRS[direction], "name": d["name"], "type": d["kind"], "city": d.get("city"), "about": d.get("about"), "phone": d["phone"], "email": d["email"], "address": d["address"],
            "hours": d["hours"], "logo": d["logo"][0] if d.get("logo") else None, "logo_needs_dark_chip": bool(d.get("logo") and d["logo"][1] == "light"), "photos": ph, "video": d.get("video"), "menu_items": d["menu"], "menu_url": d.get("menu_url"),
            "order_url": d.get("order_url"), "instagram": d.get("ig"), "facebook": d.get("fb"), "dominant_colors": pal}
def serve(root):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root); h.log_message = lambda *a: None
    s = socketserver.TCPServer(("127.0.0.1", 0), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
def qa(root, slug):
    from playwright.sync_api import sync_playwright
    s = serve(root); issues, shots = [], []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for w, h in ((390, 844), (1280, 800)):
                pg = b.new_page(viewport={"width": w, "height": h}); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto(f"http://127.0.0.1:{s.server_address[1]}/{slug}/", wait_until="networkidle", timeout=60000); pg.wait_for_timeout(800)
                pg.evaluate("document.querySelectorAll('*').forEach(e=>{if(getComputedStyle(e).opacity==='0')e.style.opacity=1})")
                if pg.evaluate("document.documentElement.scrollWidth>innerWidth+2"): issues.append(f"horizontal scroll at {w}px")
                bad = pg.evaluate("[...document.images].filter(i=>i.complete&&i.naturalWidth==0).map(i=>i.getAttribute('src'))")
                if bad: issues.append(f"broken images at {w}px: {bad[:3]}")
                if errs: issues.append(f"js error: {errs[0][:80]}")
                if w == 390 and len(pg.inner_text("body")) < 250: issues.append("page has almost no text")
                im = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB"); im = im.crop((0, 0, im.width, min(im.height, int(im.width * 3.2))))
                im.thumbnail((900, 2900)); buf = io.BytesIO(); im.save(buf, "JPEG", quality=70); shots.append(buf.getvalue())
            b.close()
    finally: s.shutdown()
    return issues, shots
def critique(shots, name):
    parts = [{"text": f"You are a ruthless art director reviewing a website demo for {name} that will be pitched to the owner. Image 1 is mobile, image 2 is desktop. Score 1-10 for: distinctive non-template look, polish and spacing, image crops and quality, text contrast, hierarchy. Penalise generic, cheap, empty or cluttered results. Return JSON {{\"score\": number, \"fixes\": [up to 5 specific concrete fixes]}}"}]
    parts += [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(x).decode()}} for x in shots]
    return gem(parts, js=True)
def make_site(d, root, slug, direction, fallback):
    """Return (html, info). Falls back to the fixed template if the AI path fails or scores low."""
    folder = os.path.join(root, slug); br = brief(d, direction, folder); best = (-99, None); html = None; fixes = []; issues = []
    try:
        for i in range(3):
            html = gem([{"text": "BRIEF:\n" + json.dumps(br, ensure_ascii=False)}], RULES + "\nDESIGN DIRECTION: " + DIRS[direction]) if i == 0 else \
                   gem([{"text": "BRIEF:\n" + json.dumps(br, ensure_ascii=False) + "\n\nCURRENT HTML:\n" + html + "\n\nFix these problems and return the full improved HTML only:\n- " + "\n- ".join(issues + fixes)}], RULES)
            open(f"{folder}/index.html", "w", encoding="utf-8").write(html); issues, shots = qa(root, slug); c = critique(shots, d["name"]); sc = float(c.get("score", 0)) - 2 * len(issues); fixes = c.get("fixes", [])
            if sc > best[0]: best = (sc, html)
            if not issues and sc >= 8: break
    except Exception as e: print("AI design failed:", str(e)[:100])
    if best[1] and best[0] >= 6: return best[1], {"theme": direction, "hero": "ai", "ai_score": round(best[0], 1)}
    h, info = fallback(d); info["ai_score"] = round(best[0], 1) if best[1] else 0; return h, info
