import base64, io, json, os, re, statistics, requests
from PIL import Image
UA = {"User-Agent": "Mozilla/5.0 (compatible; DemoSiteBot/1.0)"}
PEX, GEM, GM = os.getenv("PEXELS_API_KEY", ""), os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
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
    return im if statistics.pstdev(px) >= 28 else None
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
def gemini_menu(data, mime):
    if not GEM or not data or len(data) > 15_000_000: return []
    p = 'Extract the menu printed in this document as a JSON array of {"section":str,"name":str,"desc":str,"price":str}. Only items actually printed, nothing invented, max 30 items.'
    try:
        r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GM}:generateContent?key={GEM}", timeout=90, json={"contents": [{"parts": [{"text": p}, {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}]}], "generationConfig": {"response_mime_type": "application/json"}})
        items = json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])
        return [i for i in items if isinstance(i, dict) and i.get("name")][:30]
    except Exception: return []
