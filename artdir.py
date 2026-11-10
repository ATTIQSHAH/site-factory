"""AI art director: picks a distinct design direction, has Gemini build a bespoke page from REAL facts/assets, then renders it, checks it, and revises."""
import base64, io, json, os, re, threading, time, functools, http.server, socketserver
import requests
from PIL import Image
KEY, MODEL = os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_DESIGN_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-3.8-flash"\nLAST_DESIGN_PROVIDER, LAST_DESIGN_MODEL = "", ""
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
    """Generate with Gemini first, then configured OpenAI-compatible providers."""
    errors = []
    if KEY:
        body = {"contents": [{"parts": parts}], "generationConfig": {
            "maxOutputTokens": 30000,
            **({"responseMimeType": "application/json"} if js else {})
        }}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
        try:
            response = None
            for attempt in range(3):
                response = requests.post(
                    url, headers={"x-goog-api-key": KEY}, json=body, timeout=240
                )
                if response.status_code == 429:
                    try:
                        error_payload = response.json()
                    except Exception:
                        error_payload = {}
                    message = str(error_payload.get("error", {}).get("message") or response.text or "rate limited")
                    if "quota" in message.lower() or "resource_exhausted" in message.lower():
                        raise RuntimeError(f"Gemini HTTP 429: {message[:250]}")
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt < 2:
                        try:
                            delay = float(response.headers.get("Retry-After", ""))
                        except (TypeError, ValueError):
                            delay = 2 ** (attempt + 1)
                        time.sleep(min(max(delay, 2 ** (attempt + 1)), 12))
                        continue
                response.raise_for_status()
                break
            payload = response.json()
            candidates = payload.get("candidates") or []
            if not candidates:
                raise RuntimeError("Gemini returned no candidate: " + json.dumps(payload.get("promptFeedback", payload.get("error", {})))[:250])
            text = next(
                (part.get("text") for part in candidates[0].get("content", {}).get("parts", [])
                 if isinstance(part.get("text"), str)), ""
            )
            if not text.strip():
                raise RuntimeError("Gemini returned empty content")
            return json.loads(text) if js else re.sub(r"^\x60{3}(?:html)?\s*|\s*\x60{3}$", "", text.strip())
        except Exception as exc:
            errors.append("Gemini: " + str(exc)[:220])
    else:
        errors.append("Gemini: API key not configured")

    # The AI design prompt is text-only, so use compatible text models as fallbacks.
    try:
        import provider_router
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        user_text = "\n".join(
            str(part.get("text", "")) for part in parts if isinstance(part, dict)
        )
        messages.append({"role": "user", "content": user_text})
        result = provider_router.chat_candidates("design", messages, max_tokens=30000, timeout=240)
        text = result["content"]
        if js:
            return json.loads(re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", text.strip(), flags=re.I))
        return re.sub(r"^\x60{3}(?:html)?\s*|\s*\x60{3}$", "", text.strip(), flags=re.I)
    except Exception as exc:
        errors.append("Fallback providers: " + str(exc)[:350])
    raise RuntimeError("All AI design providers failed: " + " | ".join(errors))

def brief(d, direction, folder):
    ph = d["photos"]; pal = palette(os.path.join(folder, ph[0])) if ph and not ph[0].startswith("/") else []
    return {"direction": direction, "direction_spec": DIRS[direction], "name": d["name"], "type": d["kind"], "city": d.get("city"), "about": d.get("about"), "phone": d["phone"], "email": d["email"], "address": d["address"],
            "hours": d["hours"], "logo": d["logo"][0] if d.get("logo") else None, "logo_needs_dark_chip": bool(d.get("logo") and d["logo"][1] == "light"), "photos": ph, "video": d.get("video"), "menu_items": d["menu"], "menu_url": d.get("menu_url"),
            "order_url": d.get("order_url"), "instagram": d.get("ig"), "facebook": d.get("fb"), "dominant_colors": pal}
def serve(root):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    h = functools.partial(Q, directory=root)
    s = socketserver.TCPServer(("127.0.0.1", 0), h); threading.Thread(target=s.serve_forever, daemon=True).start(); return s
def qa(root, slug, min_text=250):
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
                if w == 390 and len(pg.inner_text("body")) < min_text: issues.append("page has almost no text")
                im = Image.open(io.BytesIO(pg.screenshot(full_page=True))).convert("RGB"); im = im.crop((0, 0, im.width, min(im.height, int(im.width * 3.2))))
                im.thumbnail((900, 2900)); buf = io.BytesIO(); im.save(buf, "JPEG", quality=70); shots.append(buf.getvalue())
            b.close()
    finally: s.shutdown()
    return issues, shots
def _parse_visual_review(answer):
    """Parse a strict JSON object, tolerating harmless provider wrappers."""
    if isinstance(answer, list):
        answer = "".join(
            part.get("text", "") for part in answer
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        )
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Provider returned no text content")
    cleaned = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", answer.strip(), flags=re.I)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        # Some free vision endpoints wrap JSON in prose. Extract the first
        # complete object without accepting partial/truncated responses.
        decoder = json.JSONDecoder()
        result = None
        for offset, char in enumerate(cleaned):
            if char == "{":
                try:
                    result, _ = decoder.raw_decode(cleaned[offset:])
                    break
                except json.JSONDecodeError:
                    continue
        if result is None:
            raise ValueError("Provider response did not contain a complete JSON object")
    if not isinstance(result, dict) or "score" not in result:
        raise ValueError("Visual review JSON must contain a score")
    score = float(result["score"])
    if not 1 <= score <= 10:
        raise ValueError(f"Visual score outside 1-10 range: {score}")
    fixes = result.get("fixes", [])
    if not isinstance(fixes, list):
        raise ValueError("Visual review fixes must be a JSON list")
    fixes = [str(item).strip() for item in fixes if str(item).strip()]
    return {"score": score, "fixes": fixes[:5]}


def critique(shots, name):
    """Review mobile and desktop screenshots through resilient OpenRouter vision fallbacks."""
    key = os.getenv("OPENROUTER_API_KEY", "")

    # Prefer vision models that return ordinary text reliably. Keep model IDs
    # configurable so providers can be changed without editing application code.
    models = [
        os.getenv("OPENROUTER_VISUAL_MODEL", "google/gemma-4-31b-it:free"),
        os.getenv("OPENROUTER_VISUAL_FALLBACK_MODEL", "dots-studio/dots-3-note-preview:free"),
        os.getenv("OPENROUTER_VISUAL_TERTIARY_MODEL", "google/gemma-4-26b-a4b-it:free"),
        os.getenv("OPENROUTER_VISUAL_QUATERNARY_MODEL", "nvidia/nemotron-3.5-super-vl:free"),
        os.getenv("OPENROUTER_VISUAL_ROUTER_MODEL", "openrouter/free"),
    ]
    prompt = (
        f"Review this website demo for {name}. Image 1 is mobile; image 2 is desktop. "
        "Evaluate visual polish, distinctiveness, spacing, image crops, text contrast, "
        "typography hierarchy, navigation and calls to action. Score from 1 (poor) "
        "to 10 (excellent). List at most 5 concrete, visible fixes. Do not infer "
        "problems that are not visible. Return exactly one JSON object with numeric "
        'score and a fixes array, for example: {"score": 8, "fixes": ["Improve hero crop"]}.'
    )
    parts = [{"type": "text", "text": prompt}]
    for shot in shots:
        encoded = base64.b64encode(shot).decode("ascii")
        parts.append({"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + encoded}})

    # Prefer Gemini for visual review. OpenRouter is retained only as a fallback.
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        gemini_model = (
            os.getenv("GEMINI_VISUAL_MODEL")
            or os.getenv("GEMINI_DESIGN_MODEL")
            or os.getenv("GEMINI_MODEL")
            or MODEL
        )
        gemini_parts = [{"text": prompt}]
        for shot in shots:
            gemini_parts.append({
                "inlineData": {
                    "mimeType": "image/jpeg",
                    "data": base64.b64encode(shot).decode("ascii"),
                }
            })
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent",
                headers={"x-goog-api-key": gemini_key},
                json={
                    "contents": [{"parts": gemini_parts}],
                    "generationConfig": {
                        "temperature": 0,
                        "maxOutputTokens": 700,
                        "responseMimeType": "application/json",
                    },
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            candidates = payload.get("candidates") or []
            parts_out = (candidates[0].get("content") or {}).get("parts") or []
            answer = next(
                (part.get("text") for part in parts_out if isinstance(part.get("text"), str)),
                "",
            )
            parsed = _parse_visual_review(answer)
            return {
                **parsed,
                "provider": "gemini",
                "model": gemini_model,
            }
        except Exception as exc:
            errors = [f"Gemini primary ({gemini_model}): {str(exc)[:220]}"]
    else:
        errors = ["Gemini: API key not configured"]

    if key:
        for model in dict.fromkeys(models):
            # Rate-limited providers are skipped immediately; retrying the same
            # free endpoint burns time and does not help the other available models.
            for attempt in range(2):
                try:
                    response = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": parts}],
                            "temperature": 0,
                            "max_tokens": 700,
                        },
                        timeout=120,
                    )
                    if response.status_code == 429:
                        errors.append(f"{model}: HTTP 429 rate limited")
                        break
                    if response.status_code in (408, 425) or response.status_code >= 500:
                        detail = f"HTTP {response.status_code}: {response.text[:180]}"
                        if attempt == 0:
                            headers = getattr(response, "headers", {}) or {}
                            try:
                                retry_after = float(headers.get("Retry-After", ""))
                            except (TypeError, ValueError):
                                retry_after = 2
                            time.sleep(min(max(retry_after, 1), 5))
                            continue
                        errors.append(f"{model}: {detail}")
                        break
    
                    response.raise_for_status()
                    payload = response.json()
                    choices = payload.get("choices") or []
                    message = choices[0].get("message") if choices else None
                    if not isinstance(message, dict):
                        raise ValueError("Provider returned no assistant message")
    
                    answer = message.get("content")
                    # Some reasoning-first vision models put the final answer in
                    # reasoning instead of content. Accept it only if it contains
                    # a complete, schema-valid review object.
                    candidates = [answer, message.get("reasoning")]
                    parsed = None
                    parse_errors = []
                    for candidate in candidates:
                        if candidate:
                            try:
                                parsed = _parse_visual_review(candidate)
                                break
                            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                                parse_errors.append(str(exc))
                    if parsed is None:
                        raise ValueError(
                            "No valid review JSON in model output"
                            + (": " + "; ".join(parse_errors[:2]) if parse_errors else "")
                        )
                    return {
                        **parsed,
                        "provider": "openrouter",
                        "model": model,
                    }
                except Exception as exc:
                    errors.append(f"{model}: {str(exc)[:220]}")
                    break
    
    else:
        errors.append("OpenRouter: API key not configured; trying Gemini fallback")
    # Additional vision-capable providers (optional; model IDs must be configured).
    try:
        import provider_router
        routed = provider_router.chat_candidates(
            "visual", [{"role": "user", "content": parts}],
            max_tokens=700, timeout=120
        )
        parsed = _parse_visual_review(routed["content"])
        return {
            **parsed,
            "provider": routed["provider"],
            "model": routed["model"],
        }
    except Exception as exc:
        errors.append("Groq/Cloudflare fallback: " + str(exc)[:300])

    raise RuntimeError("All visual-review providers failed: " + " | ".join(errors))

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
    if best[1] and best[0] >= 6: return best[1], {"theme": direction, "hero": "ai", "ai_score": round(best[0], 1), "ai_provider": LAST_DESIGN_PROVIDER, "ai_model": LAST_DESIGN_MODEL}
    h, info = fallback(d); info["ai_score"] = round(best[0], 1) if best[1] else 0; return h, info
