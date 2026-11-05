"""Quality checks for generated demo websites."""
import re
from collections import Counter
from bs4 import BeautifulSoup

def assess_html(document, business_name="", phone="", require_noindex=True):
    soup = BeautifulSoup(document or "", "html.parser")
    issues = []
    blocking = False
    score = 100

    def fail(points, message, block=False):
        nonlocal score, blocking
        if message not in issues:
            score -= points
            issues.append(message)
        blocking = blocking or block

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc = soup.find("meta", attrs={"name": "description"})
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    visible = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).lower()

    if not title or (business_name and business_name.lower() not in title.lower()):
        fail(15, "missing or mismatched page title")
    if not desc or len(desc.get("content", "").strip()) < 60:
        fail(15, "missing or short meta description")
    if not soup.find("meta", attrs={"name": "viewport"}):
        fail(12, "missing mobile viewport")
    if require_noindex and (not robots or "noindex" not in robots.get("content", "").lower()):
        fail(12, "missing noindex directive")
    if not soup.find("h1"):
        fail(12, "missing primary heading")
    if len(visible) < 250:
        fail(20, "page contains too little readable content")
    if business_name and business_name.lower() not in visible:
        fail(15, "business name missing from page")
    if "{{" in (document or "") or "lorem ipsum" in visible or "undefined" in visible:
        fail(25, "unresolved placeholder or generated filler detected", True)
    if any(not n.get_text(" ", strip=True) for n in soup.select(".hero p, .hero-lead, .bento-hero-left p")):
        fail(18, "hero has an empty lead paragraph", True)

    for label in soup.select(".chip, .eyebrow, .pillar-badge"):
        fragments = re.split(r"[·|,]", label.get_text(" ", strip=True))
        if any(len(part.strip()) == 1 and part.strip().isalpha() for part in fragments):
            fail(12, "suspicious one-character label or location", True)
            break

    cards = soup.select(".menu-card")
    if cards:
        names = []
        for card in cards:
            node = card.select_one(".menu-item-title, h3, h4")
            if node:
                names.append(re.sub(r"[^a-z0-9]+", " ", node.get_text(" ", strip=True).lower()).strip())
        counts = Counter(n for n in names if n)
        if any(count > 1 for count in counts.values()):
            fail(18, "menu contains duplicate product names", True)
        headings = [re.sub(r"[^a-z0-9]+", " ", n.get_text(" ", strip=True).lower()).strip()
                    for n in soup.select(".menu-section-title")]
        if any(h and h in names for h in headings):
            fail(14, "menu heading repeats a product name", True)
        prices = [n.get_text(" ", strip=True) for n in soup.select(".menu-item-price-tag") if n.get_text(" ", strip=True)]
        price_counts = Counter(prices)
        if len(prices) >= 3:
            value, count = price_counts.most_common(1)[0]
            if value and count >= 3 and count / len(prices) >= 0.6:
                fail(16, "menu prices suspiciously repeat across products", True)

    for section in soup.select("#about, #story, .about-section, .story-section"):
        paragraphs = [p.get_text(" ", strip=True) for p in section.select(".story-copy, .story-content p, .about-copy, .about-content p")]
        if not any(len(p) >= 80 for p in paragraphs) and section.select(".fact, .facts, address, .visit-address"):
            fail(14, "about section has contact facts but no business story", True)

    hero_images = {n.get("src") for n in soup.select(".hero img, .bento-img-frame img") if n.get("src")}
    story_images = {n.get("src") for n in soup.select("#about img, #story img, .story-photo-frame img") if n.get("src")}
    if hero_images.intersection(story_images):
        fail(10, "hero image repeated in about/story section", True)

    has_menu = bool(soup.find(id="menu")) or any(
        re.search("menu|order|reservation|book a table", a.get_text(" ", strip=True), re.I)
        for a in soup.find_all("a")
    )
    if not has_menu:
        fail(12, "no menu, ordering or reservation path")
    if phone:
        digits = re.sub(r"\D", "", phone)
        page_digits = re.sub(r"\\D", "", document or "")
        if len(digits) >= 7 and digits[-7:] not in page_digits:
            fail(15, "lead phone number missing")
        elif len(digits) >= 7 and not soup.select_one('a[href^="tel:"]'):
            fail(12, "phone missing click-to-call link")

    ids = {n.get("id") for n in soup.find_all(id=True)}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if href.startswith("#") and href[1:] and href[1:] not in ids:
            fail(3, "navigation points to missing section")
            break
    if any(not n.get("src", "").strip() for n in soup.find_all("img")):
        fail(5, "image missing source")

    score = max(0, min(100, score))
    passed = score >= 90 and not blocking
    return {"score": score, "passed": passed, "status": "ready" if passed else "needs_review",
            "issues": issues, "blocking_issues": blocking}
