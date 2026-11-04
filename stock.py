"""Curated local stock-image selection for restaurant, cafe, coffee and fast-food demos.

Place only commercially usable, properly licensed images under sites/_stock/.
The selector favors niche + subject relevance, checks image dimensions/quality,
avoids near-duplicates, and spreads selected images across visual subjects.
"""
import hashlib
import json
import os
import re
from pathlib import Path

from PIL import Image
import media

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
CATEGORY_RULES = [
    ("bakery", re.compile(r"bakery|patisserie|pastry|croissant|sourdough|macaron|donut|cake shop", re.I)),
    ("fastfood", re.compile(r"fast[\s-]?food|burger|hamburger|pizza|pizzeria|fried chicken|wings|taco|tacos|fries|hotdog|hot dog|kebab|shawarma", re.I)),
    ("coffee", re.compile(r"coffee|espresso|roast|roastery|cappuccino|latte", re.I)),
    ("cafe", re.compile(r"cafe|café|bistro|brunch", re.I)),
]
SUBJECTS = {
    "restaurant": ["food", "interior", "exterior", "dining", "people", "detail"],
    "bakery": ["pastry", "bread", "cake", "interior", "coffee", "exterior"],
    "cafe": ["interior", "coffee", "food", "lifestyle", "exterior", "detail"],
    "coffee": ["coffee", "interior", "barista", "beans", "food", "exterior"],
    "fastfood": ["burger", "pizza", "fried-chicken", "fries", "food", "interior", "exterior", "people"],
}
CATEGORY_FALLBACKS = {
    "restaurant": ["restaurant", "shared"],
    "bakery": ["bakery", "cafe", "restaurant", "shared"],
    "cafe": ["cafe", "coffee", "restaurant", "shared"],
    "coffee": ["coffee", "cafe", "restaurant", "shared"],
    "fastfood": ["fastfood", "restaurant", "grill", "shared"],
}


def business_category(name, render_kind="restaurant"):
    text = str(name or "").lower()
    for category, pattern in CATEGORY_RULES:
        if pattern.search(text):
            return category
    if render_kind == "coffee":
        return "coffee"
    return "restaurant"


def _load_manifest(root):
    path = root / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _image_info(path):
    try:
        raw = path.read_bytes()
        if len(raw) < 35_000:
            return None
        im = media.photo(raw)
        if im is None or im.width < 1000 or im.height < 650:
            return None
        ratio = im.width / im.height
        if not 1.15 <= ratio <= 2.2:
            return None
        return media.ahash(im)
    except Exception:
        return None


def _tokens(value):
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower().replace("_", "-")))


def select_stock(stock_root, business_name, render_kind, site_folder, existing_photos, limit=6):
    """Return public /_stock/... URLs for relevant, quality-checked local images."""
    root = Path(stock_root)
    if limit <= 0 or not root.is_dir():
        return []

    category = business_category(business_name, render_kind)
    category_order = CATEGORY_FALLBACKS[category]
    subject_order = SUBJECTS[category]
    manifest = _load_manifest(root)
    existing_hashes, existing_urls = set(), set()

    for item in existing_photos or []:
        if str(item).startswith("/_stock/"):
            existing_urls.add(str(item))
            continue
        local = Path(site_folder) / str(item)
        if local.is_file():
            digest = _image_info(local)
            if digest:
                existing_hashes.add(digest)

    candidates = []
    seen_hashes = set(existing_hashes)
    for category_rank, folder_name in enumerate(category_order):
        folder = root / folder_name
        if not folder.is_dir():
            continue
        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
                continue
            digest = _image_info(path)
            if not digest or digest in seen_hashes:
                continue
            rel = path.relative_to(root).as_posix()
            meta = manifest.get(rel, {})
            if not isinstance(meta, dict):
                meta = {}
            path_tokens = _tokens(path.parent.as_posix() + " " + path.stem)
            tags = _tokens(meta.get("tags", []))
            all_tokens = path_tokens | tags
            subject_rank = len(subject_order) + 2
            subject = "general"
            for idx, wanted in enumerate(subject_order):
                wanted_tokens = _tokens(wanted)
                if wanted_tokens & all_tokens:
                    subject_rank, subject = idx, wanted
                    break
            # Explicit manifest tags can improve relevance without changing filenames.
            tag_bonus = 0 if tags else 1
            candidates.append({
                "path": path,
                "rel": rel,
                "hash": digest,
                "category_rank": category_rank,
                "subject_rank": subject_rank,
                "subject": subject,
                "tag_bonus": tag_bonus,
                "tokens": all_tokens,
            })
            seen_hashes.add(digest)

    if not candidates:
        return []

    # Stable per-business rotation prevents every lead receiving the same first image.
    seed = int(hashlib.sha1(str(business_name).encode("utf-8")).hexdigest()[:8], 16)
    candidates.sort(key=lambda x: (
        x["category_rank"], x["subject_rank"], x["tag_bonus"],
        (sum(map(ord, x["rel"])) + seed) % 997, x["rel"]
    ))

    selected, subject_counts = [], {}
    selected_hashes = set(existing_hashes)
    for candidate in candidates:
        if len(selected) >= limit:
            break
        if candidate["hash"] in selected_hashes:
            continue
        subject = candidate["subject"]
        if subject_counts.get(subject, 0) >= 2:
            continue
        url = "/_stock/" + candidate["rel"]
        if url in existing_urls:
            continue
        selected.append(url)
        selected_hashes.add(candidate["hash"])
        subject_counts[subject] = subject_counts.get(subject, 0) + 1

    return selected
