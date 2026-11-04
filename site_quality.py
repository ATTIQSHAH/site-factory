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
        fail(8, "business name missing from page title")
    if not description or len(description.get("content", "").strip()) < 40:
        fail(10, "missing or too-short meta description")
    if not viewport:
        fail(10, "missing mobile viewport")
    if require_noindex and (not robots or "noindex" not in robots.get("content", "").lower()):
        fail(10, "missing noindex directive")
    if not soup.find("h1"):
        fail(8, "missing primary heading")
    if len(visible) < 250:
        fail(20, "page contains too little readable content")
    if business_name and business_name.lower() not in visible:
        fail(15, "business name not present in page content")
    if re.search(r"\{\{[A-Z0-9_]+\}\}|lorem ipsum|undefined|null", document or "", re.I):
        fail(20, "unresolved placeholder or generated filler detected")

    if phone:
        digits = re.sub(r"\D", "", phone)
        page_digits = re.sub(r"\D", "", document or "")
        if len(digits) >= 7 and digits[-7:] not in page_digits:
            fail(8, "lead phone number missing from generated page")
        elif len(digits) >= 7 and not any(a.get("href", "").lower().startswith("tel:") for a in soup.find_all("a", href=True)):
            fail(5, "phone is shown without a click-to-call link")

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
        "passed": score >= 80 and not any("unresolved" in issue for issue in issues),
        "status": "ready" if score >= 80 and not any("unresolved" in issue for issue in issues) else "needs_review",
        "issues": issues,
    }
