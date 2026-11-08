"""Verify that external menu/order links lead to usable destinations."""
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


MENU_TERMS = ("menu", "order", "ordering", "reservation", "book a table", "catering")


def menu_links(document, base_url=""):
    """Return unique HTTP(S) links whose visible label or URL suggests menu/order intent."""
    soup = BeautifulSoup(document or "", "html.parser")
    found = []
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()
        label = anchor.get_text(" ", strip=True)
        if not any(term in (label + " " + href).lower() for term in MENU_TERMS):
            continue
        target = urljoin(base_url, href)
        if urlparse(target).scheme in ("http", "https") and target not in found:
            found.append(target)
    return found


def verify_menu_destination(url, timeout=15, session=None):
    """Check that a candidate destination responds and contains menu/order content."""
    client = session or requests
    try:
        response = client.get(url, timeout=timeout, allow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0 (compatible; SiteQualityReview/1.0)"})
        response.raise_for_status()
        final_url = response.url
        if urlparse(final_url).scheme not in ("http", "https"):
            return {"verified": False, "url": final_url, "reason": "unsupported redirect destination"}

        content_type = response.headers.get("content-type", "").lower()
        if "application/pdf" in content_type or final_url.lower().endswith(".pdf"):
            is_pdf = response.content[:5] == b"%PDF-"
            return {"verified": is_pdf, "url": final_url,
                    "reason": "" if is_pdf else "PDF response did not contain a valid PDF signature"}

        soup = BeautifulSoup(response.text or "", "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        text = " ".join(soup.stripped_strings).lower()
        if len(text) < 80:
            return {"verified": False, "url": final_url, "reason": "destination has too little readable content"}
        signals = sum(term in (title + " " + text) for term in MENU_TERMS)
        has_products_or_prices = bool(
            soup.select("[itemtype*='Product'], [class*='menu-item'], [class*='product'], [class*='price']")
        ) or any(symbol in text for symbol in ("$", "£", "€"))
        verified = signals > 0 and (has_products_or_prices or "reservation" in text or "book a table" in text)
        return {"verified": verified, "url": final_url,
                "reason": "" if verified else "destination did not show convincing menu, ordering, or booking content"}
    except requests.RequestException as exc:
        return {"verified": False, "url": url, "reason": str(exc)[:240]}
