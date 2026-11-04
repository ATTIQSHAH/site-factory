"""Render a generated demo at mobile and desktop sizes and save a deterministic QA report."""
import argparse
import json
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright
from site_quality import assess_html
from bs4 import BeautifulSoup
import re


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="sites/fluff-bake-bar")
    parser.add_argument("--report-dir", default="review/fluff-bake-bar")
    args = parser.parse_args()

    site = Path(args.site).resolve()
    index = site / "index.html"
    if not index.is_file():
        raise SystemExit(f"Generated site not found: {index}")
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    handler = partial(SimpleHTTPRequestHandler, directory=str(site.parent))
    handler.log_message = lambda *unused: None
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    checks = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for width, height, label in ((390, 844, "mobile"), (1280, 900, "desktop")):
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(
                    f"http://127.0.0.1:{server.server_port}/{site.name}/",
                    wait_until="networkidle",
                    timeout=60000,
                )
                page.evaluate("document.querySelectorAll('.rv').forEach(e => { e.classList.add('on'); e.style.opacity = '1'; e.style.transform = 'none'; })")
                page.evaluate("async () => { const imgs = [...document.images]; imgs.forEach(img => img.loading = 'eager'); await Promise.all(imgs.map(img => img.decode().catch(() => null))); }")
                page.wait_for_timeout(250)
                page.screenshot(path=str(report_dir / f"{label}.png"), full_page=True)
                horizontal_overflow = page.evaluate(
                    "document.documentElement.scrollWidth > window.innerWidth + 2"
                )
                broken_images = page.evaluate(
                    "[...document.images].filter(i => i.complete && i.naturalWidth === 0)"
                    ".map(i => i.currentSrc || i.src)"
                )
                checks.append({
                    "viewport": label,
                    "width": width,
                    "horizontal_overflow": horizontal_overflow,
                    "broken_images": broken_images,
                    "javascript_errors": errors,
                    "page_title": page.title(),
                    "h1": page.locator("h1").first.inner_text() if page.locator("h1").count() else "",
                })
                page.close()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    html = index.read_text(encoding="utf-8")
    quality = assess_html(html, "Fluff Bake Bar", "(713) 522-1900")
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(" ", strip=True)
    menu_item_count = len(soup.select(".menu-card"))
    hours_row_count = len(soup.select(".hours-list tr"))
    has_street_address = bool(re.search(
        r"\\b\\d{1,6}\\s+[A-Za-z0-9 .'-]+\\b(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way)\\b",
        visible_text, re.I
    ))
    has_click_to_call = bool(soup.select_one('a[href^="tel:"]'))
    data_checks = {
        "menu_item_count": menu_item_count,
        "has_menu_items": menu_item_count >= 5,
        "hours_row_count": hours_row_count,
        "has_opening_hours": hours_row_count >= 1,
        "has_street_address": has_street_address,
        "has_click_to_call": has_click_to_call,
    }
    report = {
        "business": "Fluff Bake Bar",
        "source_website": "https://fluffbakebar.com/",
        "quality": quality,
        "data_checks": data_checks,
        "browser_checks": checks,
        "passed": quality["passed"] and all(data_checks.values()) and all(
            not c["horizontal_overflow"] and not c["broken_images"] and not c["javascript_errors"]
            for c in checks
        ),
    }
    (report_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit("Fluff Bake Bar demo needs review; see report.json and screenshots.")


if __name__ == "__main__":
    main()
