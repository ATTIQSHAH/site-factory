"""Quality gates for generated demo websites.

The checks here are deliberately deterministic. Missing business facts are not
filled with guesses: absent menu/hours data is reported and must be resolved
through a real source or an explicit manual review.
"""
import re
from collections import Counter
from bs4 import BeautifulSoup


MENU_TERMS = re.compile(r"menu|order|reservation|book(?:ing)?", re.I)


def _norm(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _external_menu_path(soup):
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        label = anchor.get_text(" ", strip=True) + " " + href
        if MENU_TERMS.search(label) and href.lower().startswith(("https://", "http://")):
            return True
    return False


def _menu_items(soup):
    items = []
    for node in soup.select(".menu-card, .it, [itemtype*='MenuItem']"):
        title = node.select_one(".menu-item-title, h3, h4, .item-name")
        if title is None:
            title = node.find(["strong", "b"])
        name = title.get_text(" ", strip=True) if title else ""
        if not name:
            # The premium fallback uses a two-column row without a title class.
            first = node.select_one("div span")
            name = first.get_text(" ", strip=True) if first else ""
        if name:
            items.append(_norm(name))
    return [item for item in items if item]


def assess_html(document, business_name="", phone="", require_noindex=True,
                require_menu_path=True, require_hours=False):
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
    desc = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    visible = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).lower()

    if not title or (business_name and business_name.lower() not in title.lower()):
        fail(15, "missing or mismatched page title")
    if not desc or len(desc.get("content", "").strip()) < 60:
        fail(15, "missing or short meta description")
    if not soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)}):
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
    if any(not node.get_text(" ", strip=True) for node in soup.select(".hero p, .hero-lead, .bento-hero-left p")):
        fail(18, "hero has an empty description or lead paragraph", True)

    for label in soup.select(".chip, .eyebrow, .pillar-badge"):
        fragments = re.split(r"[·|,]", label.get_text(" ", strip=True))
        if any(len(part.strip()) == 1 and part.strip().isalpha() for part in fragments):
            fail(12, "suspicious one-character label or location", True)
            break

    items = _menu_items(soup)
    counts = Counter(items)
    if any(count > 1 for count in counts.values()):
        fail(18, "menu contains duplicate product names", True)

    section_names = {_norm(node.get_text(" ", strip=True)) for node in soup.select(".menu-section-title")}
    if section_names.intersection(items):
        fail(14, "menu heading repeats a product name", True)

    prices = [node.get_text(" ", strip=True) for node in soup.select(".menu-item-price-tag, .it > div span:last-child")
              if node.get_text(" ", strip=True)]
    price_counts = Counter(prices)
    if len(prices) >= 3:
        value, count = price_counts.most_common(1)[0]
        if value and count >= 3 and count / len(prices) >= 0.6:
            fail(16, "menu prices suspiciously repeat across products", True)

    has_menu_path = len(items) >= 3 or _external_menu_path(soup)
    if require_menu_path and not has_menu_path:
        fail(18, "no usable menu, ordering or reservation path", True)
    elif items and len(items) < 3 and not _external_menu_path(soup):
        fail(12, "menu has fewer than three products and no external menu path", True)

    for section in soup.select("#about, #story, .about-section, .story-section"):
        paragraphs = [p.get_text(" ", strip=True) for p in section.select(
            ".story-copy, .story-content p, .about-copy, .about-content p, p.lead")]
        if section.select(".fact, .facts, address, .visit-address") and not any(len(p) >= 80 for p in paragraphs):
            fail(14, "about section has contact facts but no business story", True)

    hero_images = {node.get("src") for node in soup.select(".hero img, .bento-img-frame img") if node.get("src")}
    story_images = {node.get("src") for node in soup.select("#about img, #story img, .story-photo-frame img") if node.get("src")}
    if hero_images.intersection(story_images):
        fail(10, "hero image repeated in about/story section", True)

    if require_hours and not soup.select(".hours tr, .hours-list tr, .hours-table tr, [itemprop='openingHours']"):
        fail(18, "source-provided opening hours are missing", True)

    if phone:
        digits = re.sub(r"\D", "", phone)
        phone_sources = [soup.get_text(" ", strip=True)] + [
            node.get("href", "") for node in soup.select('a[href^="tel:"]')
        ]
        page_digits = re.sub(r"\D", "", " ".join(phone_sources))
        if len(digits) >= 7 and digits[-7:] not in page_digits:
            fail(15, "lead phone number missing", True)
        elif len(digits) >= 7 and not soup.select_one('a[href^="tel:"]'):
            fail(12, "phone missing click-to-call link", True)

    ids = {node.get("id") for node in soup.find_all(id=True)}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if href.startswith("#") and href[1:] and href[1:] not in ids:
            fail(3, "navigation points to missing section")
            break
    if any(not node.get("src", "").strip() for node in soup.find_all("img")):
        fail(5, "image missing source")

    score = max(0, min(100, score))
    passed = score >= 90 and not blocking
    return {
        "score": score,
        "passed": passed,
        "status": "ready" if passed else "needs_review",
        "issues": issues,
        "blocking_issues": blocking,
        "menu_card_count": len(items),
        "has_menu_path": has_menu_path,
    }
