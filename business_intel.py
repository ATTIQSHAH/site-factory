"""Evidence-weighted business classification from a business website."""
import re

RULES = {
    "coffee": {
        "patterns": (r"coffee\s*(?:shop|house|bar|roast(?:er|ery)?|company|co\.)?", r"espresso", r"cappuccino", r"pour[- ]over", r"specialty coffee", r"coffee beans"),
        "query": "coffee shop",
    },
    "bakery": {
        "patterns": (r"bakery", r"patisserie", r"pastry", r"croissant", r"bread\s*(?:shop|company|bakery)?", r"sourdough", r"cakes?\s*(?:and|&)\s*desserts?", r"macaron", r"donut"),
        "query": "bakery pastries",
    },
    "cafe": {
        "patterns": (r"caf[eé]", r"brunch", r"breakfast\s*(?:cafe|restaurant|club)", r"tea\s*room", r"bistro"),
        "query": "cafe interior",
    },
    "fastfood": {
        "patterns": (r"pizzeria", r"pizza", r"burger", r"fried chicken", r"wings", r"taco", r"taqueria", r"shawarma", r"kebab", r"fast[- ]food", r"hot dogs?"),
        "query": "fast food",
    },
    "grill": {
        "patterns": (r"barbecue", r"\bbbq\b", r"smokehouse", r"steakhouse", r"grill", r"chophouse", r"brewpub"),
        "query": "grilled food",
    },
}
SCHEMA_KIND = {
    "cafeorcoffeeshop": "cafe",
    "bakery": "bakery",
    "restaurant": "restaurant",
    "foodestablishment": "restaurant",
}


def classify_business(name="", title="", description="", headings=(), menu_items=(), schema_types=()):
    """Return (render_kind, image_query, metadata) without inventing business facts.

    Website title/description/headings and structured data carry more weight than
    the lead's display name. Menu text is useful supporting evidence, not proof
    on its own. The result always includes the evidence used for auditability.
    """
    fields = [
        ("name", str(name or ""), 3),
        ("title", str(title or ""), 4),
        ("description", str(description or ""), 4),
        ("headings", " ".join(str(x) for x in (headings or [])), 3),
        ("menu", " ".join(str(x.get("name", "")) if isinstance(x, dict) else str(x) for x in (menu_items or [])), 1),
    ]
    scores, evidence = {key: 0 for key in RULES}, {key: [] for key in RULES}
    for source, value, weight in fields:
        value = re.sub(r"\s+", " ", value).lower()
        for category, rule in RULES.items():
            for pattern in rule["patterns"]:
                if re.search(pattern, value, re.I):
                    scores[category] += weight
                    evidence[category].append({"source": source, "signal": pattern})
    schema_text = " ".join(str(x) for x in (schema_types or [])).lower()
    for token, category in SCHEMA_KIND.items():
        if token in re.sub(r"[^a-z]", "", schema_text):
            scores[category] += 5
            evidence[category].append({"source": "structured_data", "signal": token})
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        best = "restaurant"
    confidence = round(scores[best] / max(1, sum(scores.values())), 2)
    query = RULES[best]["query"] if best in RULES else "restaurant interior"
    if best == "restaurant":
        query = "restaurant interior"
    return best, query, {
        "subcategory": best,
        "confidence": confidence,
        "scores": scores,
        "evidence": evidence[best],
    }
