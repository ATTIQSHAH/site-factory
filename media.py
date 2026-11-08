import base64, io, json, os, re, statistics, time, requests
from PIL import Image
UA = {"User-Agent": "Mozilla/5.0 (compatible; DemoSiteBot/1.0)"}
PEX, GEM, GM = os.getenv("PEXELS_API_KEY", ""), os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL") or os.getenv("GEMINI_DESIGN_MODEL") or "gemini-3.8-flash"
def dl(u):
    try: r = requests.get(u, headers=UA, timeout=25); r.raise_for_status(); return r.content, r.headers.get("content-type", "")
    except Exception: return None, ""
def photo(b):
    """Return RGB image only if it is a real, sharp, photo-like picture (not a logo/graphic)."""
    try: im = Image.open(io.BytesIO(b)); im.load()
    except Exception: return None
    w, h = im.size
    if w < 900 or h < 550 or not .55 <= w / h <= 2.4: return None
    im = im.convert("RGB"); px = [sum(p) / 3 for p in im.resize((32, 32)).getdata()]
    if statistics.pstdev(px) < 28: return None
    h = sorted(im.resize((80, 80)).quantize(colors=16).histogram(), reverse=True)
    return None if sum(h[:3]) / 6400 > .72 else im  # flat promo graphics: 3 colours cover most pixels
def ahash(im): g = list(im.convert("L").resize((8, 8)).getdata()); m = sum(g) / 64; return "".join("1" if x > m else "0" for x in g)
def save(im, path, maxw=1600):
    if im.width > maxw: im = im.resize((maxw, int(im.height * maxw / im.width)))
    im.save(path, "JPEG", quality=80, optimize=True, progressive=True)
def logo(b, path):
    """Save logo as PNG; return 'light' if it needs a dark pill behind it, 'dark' otherwise, None if unusable."""
    try: im = Image.open(io.BytesIO(b)).convert("RGBA")
    except Exception: return None
    if im.width < 70 or im.height < 20: return None
    px = [p for p in im.resize((48, 48)).getdata() if p[3] > 40]
    if not px: return None
    lum = sum(0.3 * p[0] + 0.59 * p[1] + 0.11 * p[2] for p in px) / len(px)
    im.thumbnail((600, 180)); im.save(path, "PNG", optimize=True); return "light" if lum > 185 else "dark"
def pexels_photos(q, n):
    if not PEX: return []
    try:
        r = requests.get("https://api.pexels.com/v1/search", params={"query": q, "per_page": n, "orientation": "landscape"}, headers={"Authorization": PEX}, timeout=25).json()
        return [p["src"]["large2x"] for p in r.get("photos", [])]
    except Exception: return []
def pexels_video(q):
    if not PEX: return None, None
    try:
        r = requests.get("https://api.pexels.com/videos/search", params={"query": q, "per_page": 6, "orientation": "landscape"}, headers={"Authorization": PEX}, timeout=25).json()
        for v in r.get("videos", []):
            f = [x for x in v["video_files"] if x.get("file_type") == "video/mp4" and 1200 <= (x.get("width") or 0) <= 1920 and (v.get("duration") or 99) <= 30]
            if f: return f[0]["link"], v.get("image")
    except Exception: pass
    return None, None
def _gemini_response(body, timeout):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GM}:generateContent?key={GEM}"
    for attempt in range(3):
        response = requests.post(url, timeout=timeout, json=body)
        if response.status_code == 429:
            try: error_payload = response.json()
            except Exception: error_payload = {}
            message = str(error_payload.get("error", {}).get("message") or response.text or "rate limited")
            if "quota" in message.lower() or "resource_exhausted" in message.lower():
                raise RuntimeError(f"Gemini HTTP 429: {message[:250]}")
        if response.status_code == 429 or 500 <= response.status_code < 600:
            if attempt < 2:
                try: delay = float(response.headers.get("Retry-After", ""))
                except (TypeError, ValueError): delay = 2 ** (attempt + 1)
                time.sleep(min(max(delay, 2 ** (attempt + 1)), 12))
                continue
            raise RuntimeError(f"Gemini HTTP {response.status_code}: {response.text[:250]}")
        response.raise_for_status()
        return response.json()
    raise RuntimeError("Gemini request failed after bounded retries")



def gemini_menu(data, mime):
    if not GEM or not data or len(data) > 15_000_000: return []
    p = 'Extract the menu printed in this document as a JSON array of {"section":str,"name":str,"desc":str,"price":str}. Only items actually printed, nothing invented, max 30 items.'
    try:
        payload = _gemini_response({"contents": [{"parts": [{"text": p}, {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}]}], "generationConfig": {"responseMimeType": "application/json"}}, 90)
        items = json.loads(payload["candidates"][0]["content"]["parts"][0]["text"])
        return [i for i in items if isinstance(i, dict) and i.get("name")][:30]
    except Exception:
        return []

def label(im):
    """Vision label (needs Gemini key): food, drink, interior, exterior, people, graphic, logo. '' if unavailable."""
    if not GEM: return ""
    b = io.BytesIO(); t = im.copy(); t.thumbnail((640, 640)); t.save(b, "JPEG", quality=70)
    try:
        payload = _gemini_response({"contents": [{"parts": [{"text": "Classify this image for a restaurant website. Reply with exactly one word: food, drink, interior, exterior, people, graphic, logo."}, {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(b.getvalue()).decode()}}]}]}, 40)
        w = payload["candidates"][0]["content"]["parts"][0]["text"].strip().lower().split()[0].strip(".,")
        return w if w in {"food", "drink", "interior", "exterior", "people", "graphic", "logo"} else ""
    except Exception:
        return ""
