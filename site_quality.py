"""Deterministic quality checks for demo-first pitch websites."""
import re
from collections import Counter
from bs4 import BeautifulSoup

def assess_html(document, business_name="", phone="", require_noindex=True):
    soup = BeautifulSoup(document or "", "html.parser")
    issues, blocking, score = [], False, 100
    def fail(points, message, block=False):
        nonlocal score, blocking
        if message not in issues:
            score -= points
            issues.append(message)
        blocking = blocking or block
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    desc = soup.find("meta", attrs={"name": "description"})
    robots = soup.find("meta", attrs={"name": re.compile("^robots$", re.I)})
    visible = re.sub(r"\\s+", " ", soup.get_text(" ", strip=True)).lower()
    if not title or (business_name and business_name.lower() not in title.lower()):
        fail(15, "missing or mismatched page title")
    if not desc or len(desc.get("content", "").strip()) < 60:
        fail(12, "missing or short meta description")
    if not soup.find("meta", attrs={"name": "viewport"}):
        fail(12, "missing mobile viewport")
    if require_noindex and (not robots or "noindex" not in robots.get("content", "").lower()):
        fail(12, "missing noindex directive")
    h1=soup.find("h1")
    if not h1: fail(12, "missing primary heading", True)
    elif business_name and h1.get_text(" ",strip=True).casefold()!=business_name.casefold():
        fail(18, "primary heading does not exactly match the target business", True)
    if len(visible)<250: fail(20,"page contains too little readable content")
    if business_name and business_name.lower() not in visible: fail(15,"business name missing from page")
    if "{{" in (document or "") or "lorem ipsum" in visible or "undefined" in visible:
        fail(25,"unresolved placeholder or generated filler detected",True)
    if any(not n.get_text(" ",strip=True) for n in soup.select(".hero p,.hero-lead,.bento-hero-left p")):
        fail(18,"hero has an empty description or lead paragraph",True)
    for label in soup.select(".chip,.eyebrow,.pillar-badge"):
        if any(len(x.strip())==1 and x.strip().isalpha() for x in re.split(r"[·|,]",label.get_text(" ",strip=True))):
            fail(12,"suspicious one-character label or location",True); break
    cards=soup.select(".menu-card,.menu .it")
    names=[]
    for card in cards:
        node=card.select_one(".menu-item-title,h3,h4,.it div span:first-child")
        if node: names.append(re.sub(r"[^a-z0-9]+"," ",node.get_text(" ",strip=True).lower()).strip())
    counts=Counter(x for x in names if x)
    if any(n>1 for n in counts.values()): fail(15,"sample menu contains duplicate item names",True)
    note=soup.select_one(".concept-menu-disclaimer")
    note_text=note.get_text(" ",strip=True).lower() if note else ""
    labelled=bool(note and ("illustrative" in note_text or "concept preview" in note_text))
    if len(cards)<5: fail(18,"sample menu has fewer than five visible items",True)
    if not labelled: fail(18,"sample menu is not clearly labelled as illustrative concept content",True)
    if any(not x.get("src","").strip() for x in soup.find_all("img")): fail(5,"image missing source")
    hero={x.get("src") for x in soup.select(".hero img,.bento-img-frame img") if x.get("src")}
    story={x.get("src") for x in soup.select("#about img,#story img,.story-photo-frame img") if x.get("src")}
    if hero.intersection(story): fail(10,"hero image repeated in about/story section",True)
    if phone:
        digits=re.sub(r"\\D","",phone); page_digits=re.sub(r"\\D","",document or "")
        if len(digits)>=7 and digits[-7:] not in page_digits: fail(12,"provided business phone number missing")
        elif len(digits)>=7 and not soup.select_one('a[href^="tel:"]'): fail(8,"provided business phone lacks click-to-call link")
    ids={x.get("id") for x in soup.find_all(id=True)}
    for a in soup.find_all("a",href=True):
        href=a.get("href","").strip()
        if href.startswith("#") and href[1:] and href[1:] not in ids:
            fail(4,"navigation points to missing section"); break
    score=max(0,min(100,score)); passed=score>=90 and not blocking
    return {"score":score,"passed":passed,"status":"ready" if passed else "needs_review",
            "issues":issues,"blocking_issues":blocking,"menu_item_count":len(cards),
            "has_menu_path":len(cards)>=5,"menu_is_illustrative":labelled}
