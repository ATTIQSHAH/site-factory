"""Render a generated demo and enforce content, browser and visual quality gates."""
import argparse
import io
import json
import re
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from bs4 import BeautifulSoup
from PIL import Image
from playwright.sync_api import sync_playwright

import artdir
from site_quality import assess_html
from menu_verification import menu_links, verify_menu_destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", default="sites/fluff-bake-bar")
    parser.add_argument("--report-dir", default="review/fluff-bake-bar")
    parser.add_argument("--business", default="")
    parser.add_argument("--phone", default="")
    parser.add_argument("--source-website", default="")
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
    screenshots = {}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for width, height, label in ((390, 844, "mobile"), (1280, 900, "desktop")):
                page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(f"http://127.0.0.1:{server.server_port}/{site.name}/",
                          wait_until="networkidle", timeout=60000)
                page.evaluate("document.querySelectorAll('.rv').forEach(e => { e.classList.add('on'); e.style.opacity='1'; e.style.transform='none'; })")
                page.evaluate("async () => { const imgs=[...document.images]; imgs.forEach(i=>i.loading='eager'); await Promise.all(imgs.map(i=>i.decode().catch(()=>null))); }")
                page.wait_for_timeout(250)
                shot_path = report_dir / f"{label}.png"
                page.screenshot(path=str(shot_path), full_page=True)
                screenshots[label] = shot_path.read_bytes()
                metrics = page.evaluate("""() => {
                  const rect = e => { const r=e.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; };
                  const cards=[...document.querySelectorAll('.menu-card, .menu .it')].map(rect);
                  const columns=new Set(cards.map(r=>Math.round(r.x/12)*12)).size;
                  const hero=document.querySelector('.hero');
                  const bar=document.querySelector('.m');
                  const heroLead=document.querySelector('.hero-lead, .hero p, .bento-hero-left p');
                  const heroCta=document.querySelector('.hero .btn, .hero .btn-main, .hero .nav-cta');
                  const overlap=!!(bar && heroCta && getComputedStyle(bar).display!=='none' && getComputedStyle(bar).position==='fixed' &&
                    rect(heroCta).y+rect(heroCta).h > window.innerHeight-rect(bar).h && rect(heroCta).y < window.innerHeight);
                  const sources=[...document.images].map(i=>i.currentSrc||i.src).filter(Boolean);
                  const duplicates=sources.filter((src,i)=>sources.indexOf(src)!==i);
                  return {
                    horizontal_overflow: document.documentElement.scrollWidth > window.innerWidth+2,
                    overflow_elements: [...document.querySelectorAll("body *")].map(e => { const r=e.getBoundingClientRect(); return {tag:e.tagName, className: typeof e.className === "string" ? e.className.slice(0,60) : "", right: Math.round(r.right), width: Math.round(r.width)}; }).filter(e => e.right > window.innerWidth+2).slice(0,12),
                    broken_images: [...document.images].filter(i=>i.complete&&i.naturalWidth===0).map(i=>i.currentSrc||i.src),
                    menu_card_count: cards.length,
                    menu_columns: columns,
                    empty_hero_lead: !!heroLead && !heroLead.textContent.trim(),
                    mobile_bar_overlaps_hero: overlap,
                    repeated_image_count: new Set(duplicates).size
                  };
                }""")
                checks.append({
                    "viewport": label, "width": width, **metrics,
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
    soup = BeautifulSoup(html, "html.parser")
    business = args.business or (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
    tel = args.phone or ((soup.select_one('a[href^="tel:"]') or {}).get("href", "").replace("tel:", ""))
    quality = assess_html(html, business, tel)
    menu_count = len(soup.select(".menu-card, .menu .it"))
    menu_candidates = menu_links(html, args.source_website or "")
    menu_destination_checks = [verify_menu_destination(url) for url in menu_candidates[:5]]
    has_verified_menu_destination = any(item["verified"] for item in menu_destination_checks)
    has_verified_menu = menu_count >= 3 or has_verified_menu_destination
    hours_count = len(soup.select("table.hours tr, .hours-list tr, .hours tr"))
    visible = soup.get_text(" ", strip=True)
    has_address = bool(re.search(r"\b\d{1,6}\s+[A-Za-z0-9 .'-]+\b(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Dr|Drive|Ln|Lane|Way)\b", visible, re.I))
    data_checks = {
        "menu_card_count": menu_count,
        "has_menu_or_order_path": quality.get("has_menu_path", False),
        "verified_menu_destination": has_verified_menu_destination,
        "menu_destination_checks": menu_destination_checks,
        "hours_row_count": hours_count,
        "has_opening_hours": hours_count > 0,
        "has_street_address": has_address,
        "has_click_to_call": bool(soup.select_one('a[href^="tel:"]')),
    }

    visual_review = {"status": "unavailable", "score": 0, "fixes": []}
    if artdir.KEY and all(label in screenshots for label in ("mobile", "desktop")):
        try:
            images = []
            for label in ("mobile", "desktop"):
                image = Image.open(io.BytesIO(screenshots[label])).convert("RGB")
                image.thumbnail((1600, 5000))
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=82)
                images.append(buffer.getvalue())
            critique = artdir.critique(images, business or site.name)
            visual_review = {
                "status": "passed" if float(critique.get("score", 0)) >= 8 else "needs_changes",
                "score": float(critique.get("score", 0)),
                "fixes": critique.get("fixes", []),
            }
        except Exception as exc:
            message = str(exc)[:300]
            status = "quota_exhausted" if "429" in message or "quota" in message.lower() else "error"
            visual_review = {"status": status, "score": 0, "fixes": [message]}

    browser_passed = all(
        not check["horizontal_overflow"] and not check["broken_images"] and
        not check["javascript_errors"] and not check["empty_hero_lead"] and
        not check["mobile_bar_overlaps_hero"] and check["repeated_image_count"] == 0 and
        not (check["viewport"] == "desktop" and check["menu_card_count"] >= 3 and check["menu_columns"] < 2)
        for check in checks
    )
    report = {
        "business": business,
        "source_website": args.source_website,
        "quality": quality,
        "data_checks": data_checks,
        "browser_checks": checks,
        "visual_review": visual_review,
        "passed": quality["passed"] and browser_passed and
                  data_checks["has_menu_or_order_path"] and has_verified_menu and data_checks["has_opening_hours"] and
                  data_checks["has_click_to_call"] and data_checks["has_street_address"] and
                  visual_review["status"] == "passed",
    }
    (report_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit("Demo failed the quality gate; inspect report.json and screenshots.")


if __name__ == "__main__":
    main()
