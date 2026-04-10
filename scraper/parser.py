"""
scraper/parser.py
─────────────────
HTML content extraction using BeautifulSoup4 and lxml.
"""
import re
from bs4 import BeautifulSoup


def extract_clean_text(html: str) -> str:
    """
    Remove scripts, styles, nav, footer, aside.
    Normalize whitespace, preserving paragraph breaks as \\n\\n.
    Return visible body text only.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")

    # Remove non-content tags
    tags_to_remove = [
        "script", "style", "nav", "footer", "aside", "header",
        "noscript", "iframe", "svg", "button", "form",
        # Common structural or non-text blocks
        "meta", "link"
    ]
    for tag in soup(tags_to_remove):
        tag.decompose()

    # Look for common cookie/ad banners (basic class heuristic)
    for element in soup.find_all(class_=re.compile(r'cookie|banner|advert|popup|subscription', re.I)):
        element.decompose()

    # Extract clean text, separating paragraphs
    # We replace <br> and </p> boundaries with newlines to keep structure
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for p in soup.find_all("p"):
        p.append("\n\n")

    text = soup.get_text()

    # Normalize whitespace: convert multiple spaces/newlines down to double newlines max
    # 1. Clean horizontal whitespace
    lines = [line.strip() for line in text.split('\n')]
    # 2. Re-join and remove excessive vertical breaks
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()

    return text


def extract_severity(html: str) -> str:
    """
    Scan for severity keywords in priority order.
    Case-insensitive matching.
    """
    # Quick text-only scan is usually sufficient
    text = BeautifulSoup(html, "lxml").get_text().lower()

    if "contraindicated" in text:
        return "Contraindicated"
    if "major" in text:
        return "Major"
    if "moderate" in text:
        return "Moderate"
    if "minor" in text:
        return "Minor"

    return "Unknown"


def extract_interaction_blocks(html: str) -> list[dict]:
    """
    Targets interaction-specific DOM patterns across trusted sites.
    Returns:
      [{ severity: str, description: str, source: str }, ...]
    Fallback to clean text if no structured blocks found.
    """
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    blocks = []

    # ── 1. Drugs.com ──
    # Classes: .interactions-reference, .box-wrapper, .interactions-reference-wrapper
    drugs_wrappers = soup.select(".interactions-reference, .box-wrapper, .interactions-reference-wrapper")
    for wrapper in drugs_wrappers:
        # Avoid nested duplication by clearing out if we capture a parent block
        # Actually in bs4 just extracting text is fine.
        desc = wrapper.get_text(" ", strip=True)
        if len(desc) > 30: # sanity check
            blocks.append({
                "severity": extract_severity(str(wrapper)),
                "description": desc,
                "source": "drugs.com"
            })

    # ── 2. RxList ──
    # Classes: .monograph, .drug-interaction
    if not blocks:
        rxlist_wrappers = soup.select(".monograph, .drug-interaction")
        for wrapper in rxlist_wrappers:
            desc = wrapper.get_text(" ", strip=True)
            if len(desc) > 30:
                blocks.append({
                    "severity": extract_severity(str(wrapper)),
                    "description": desc,
                    "source": "rxlist"
                })

    # ── 3. MedlinePlus ──
    # Selectors: #drug-interaction, .interaction-info
    if not blocks:
        medline_wrappers = soup.select("#drug-interaction, .interaction-info")
        for wrapper in medline_wrappers:
            desc = wrapper.get_text(" ", strip=True)
            if len(desc) > 30:
                blocks.append({
                    "severity": extract_severity(str(wrapper)),
                    "description": desc,
                    "source": "medlineplus"
                })

    # ── 4. NIH / NCBI ──
    # Classes: .abstract-content, .interaction
    if not blocks:
        ncbi_wrappers = soup.select(".abstract-content, .interaction")
        for wrapper in ncbi_wrappers:
            desc = wrapper.get_text(" ", strip=True)
            if len(desc) > 30:
                blocks.append({
                    "severity": extract_severity(str(wrapper)),
                    "description": desc,
                    "source": "nih/ncbi"
                })

    # ── Fallback ──
    if not blocks:
        clean_text = extract_clean_text(html)
        if len(clean_text) > 50:
            blocks.append({
                "severity": extract_severity(html),
                "description": clean_text[:2000],  # Keep it manageable
                "source": "Fallback Parser"
            })

    return blocks
