"""Catalogue and rank the handcrafted HTML templates in templates/."""
import hashlib, os
PREFIXES = {"coffee": ("coffee_",), "cafe": ("cafe_",), "bakery": ("cafe_",), "fastfood": ("fast_",), "grill": ("fast_", "rest_"), "restaurant": ("rest_",)}
ALIASES = {"bakery": ("patisserie", "bakery", "sourdough", "bakeshop", "chocolatier", "cake"), "coffee": ("roastery", "espresso", "pour_over", "coffeehouse", "cold_brew", "cupping"), "cafe": ("brunch", "botanical", "kissaten", "crepe", "gelato", "book_cafe", "matcha"), "fastfood": ("burger", "chicken", "pizza", "taqueria", "ramen", "hotdogs", "fries", "falafel", "poke", "bao", "drive_thru"), "grill": ("steakhouse", "chophouse", "smokey", "grill", "trattoria"), "restaurant": ("haute_cuisine", "trattoria", "steakhouse", "omakase", "brasserie", "seafood", "tapas", "farmhouse", "asian", "taverna", "mezcaleria", "fondue", "lebanese", "bistro")}
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
def catalogue():
    if not os.path.isdir(ROOT): return []
    return [{"id": f[:-5], "file": f, "family": f.split("_", 1)[0], "style": f[:-5].split("_", 1)[-1].replace("_", " ").title()} for f in sorted(os.listdir(ROOT)) if f.endswith(".html") and f != "premium.html"]
def select(kind, name="", about="", menu=None):
    rows = catalogue(); prefixes = PREFIXES.get(kind, PREFIXES["restaurant"])
    pool = [r for r in rows if r["file"].startswith(prefixes)]
    if not pool: return "premium.html", {"id": "premium", "family": "fallback", "style": "Premium fallback"}
    signal = " ".join([name or "", about or ""] + [str(x.get("name", "")) for x in (menu or [])]).lower()
    terms = ALIASES.get(kind, ())
    def score(row): return sum(3 for term in terms if term in row["id"].lower() and term.replace("_", " ") in signal)
    ranked = [(score(r), r) for r in pool]; best = max(x[0] for x in ranked)
    tied = [r for points, r in ranked if points == best]
    seed = int(hashlib.sha1((name or "business").encode("utf-8")).hexdigest()[:8], 16)
    chosen = tied[seed % len(tied)]
    return chosen["file"], chosen
