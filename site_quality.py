"""Deterministic publication gate for generated demo websites."""
import re
from bs4 import BeautifulSoup


def assess_html(document, business_name="", phone="", require_noindex=True):
    """Score a rendered HTML document for basic correctness before calling it live."""
    soup = BeautifulSoup(document or "", "html.parser")
    issues = []
    score = 100
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description = soup.find("meta", attrs={"name": "description"})
    viewport = soup.find("meta", attrs={"name": "viewport"})
    robots = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    body_text = soup.body.get_text(" ", strip=True) if soup.body else soup.get_text(" ", strip=True)
    visible = re.sub(r"\s+", " ", body_text).lower()

    def fail(points, message):
        nonlocal score
        score -= points
        issues.append(message)

    if not title:
        fail(15, "missing page title")
    elif business_name and business_name.lower() not in title.lower():
        fail(12, "business name missing from page title")
    if not description or len(description.get("content", "").strip()) < 60:
        fail(15, "missing or too-short meta description")
    if not viewport:
        fail(12, "missing mobile viewport")
    if require_noindex and (not robots or "noindex" not in robots.get("content", "").lower()):
        fail(12, "missing noindex directive")
    if not soup.find("h1"):
        fail(12, "missing primary heading")
    if len(visible) < 250:
        fail(20, "page contains too little readable content")
    if business_name and business_name.lower() not in visible:
        fail(15, "business name not present in page content")
    if re.search(r"\{\{[A-Z0-9_]+\}\}", document or "") or re.search(r"\blorem ipsum\b|\bundefined\b|\bnull\b", visible, re.I):
        fail(20, "unresolved placeholder or generated filler detected")

    for hero_paragraph in soup.select(".hero p"):
        if not hero_paragraph.get_text(" ", strip=True):
            fail(12, "hero section contains an empty description")
            break

    for label in soup.select(".chip, .eyebrow"):
        fragments = re.split(r"[·|,]", label.get_text(" ", strip=True))
        if any(len(part.strip()) == 1 and part.strip().isalpha() for part in fragments):
            fail(12, "suspicious one-character label or location")
            break

    has_menu_or_order = bool(soup.find(id="menu")) or any(
        re.search(r"menu|order|reservation|book a table", a.get_text(" ", strip=True), re.I)
        for a in soup.find_all("a")
    )
    if not has_menu_or_order:
        fail(12, "no menu, ordering, or reservation path")

    if phone:
        digits = re.sub(r"\D", "", phone)
        page_digits = re.sub(r"\D", "", document or "")
        if len(digits) >= 7 and digits[-7:] not in page_digits:
            fail(15, "lead phone number missing from generated page")
        elif len(digits) >= 7 and not any(a.get("href", "").lower().startswith("tel:") for a in soup.find_all("a", href=True)):
            fail(12, "phone is shown without a click-to-call link")

    ids = {node.get("id") for node in soup.find_all(id=True)}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        if href.startswith("#") and href[1:] and href[1:] not in ids:
            fail(3, "navigation link points to a missing section")
            break
    for image in soup.find_all("img"):
        if not image.get("src", "").strip():
            fail(5, "image element has no source")
            break

    score = max(0, min(100, score))
    return {
        "score": score,
        "passed": score >= 90 and not any("unresolved" in issue for issue in issues),
        "status": "ready" if score >= 90 and not any("unresolved" in issue for issue in issues) else "needs_review",
        "issues": issues,
    }
