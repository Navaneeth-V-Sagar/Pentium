"""
scraper/enricher.py
───────────────────
MAIN FILE — Provides drug interaction and drug info lookup strategies.
Handles fallback logic, normalizes inputs, and ensures we never crash.
"""
from scraper.client import ScraperAPIClient
from scraper.parser import extract_interaction_blocks, extract_severity, extract_clean_text
from bs4 import BeautifulSoup
import urllib.parse

# Initialize client globally but lazily
client = None

def get_client() -> ScraperAPIClient:
    global client
    if client is None:
        client = ScraperAPIClient()
    return client

INTERACTION_SOURCES = [
    {
        "name": "drugs.com",
        "url_single": "https://www.drugs.com/drug-interactions/{drug}.html",
        "url_pair": "https://www.drugs.com/drug-interactions/{drug1}-{drug2}.html",
        "render_js": True,
    },
    {
        "name": "medlineplus",
        "url_single": "https://medlineplus.gov/druginfo/meds/{drug}.html",
        "url_pair": None,
        "render_js": False,
    },
    {
        "name": "rxlist",
        "url_single": "https://www.rxlist.com/{drug}-drug.htm",
        "url_pair": None,
        "render_js": False,
    },
]

def _normalize(generic: str, reported: str) -> str:
    """Normalize drug name: lowercase, strip, spaces to hyphens."""
    val = generic if generic else reported
    if not val:
        return ""
    return str(val).lower().strip().replace(" ", "-")

def _search_drug_url(api_client, drug1: str, drug2: str) -> str:
    """Uses Google Search to find the exact drugs.com internal URL for an interaction."""
    query = f"site:drugs.com/drug-interactions {drug1} {drug2}"
    search_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    
    print(f"Searching Google for true URL: {search_url}")
    try:
        html = api_client.scrape(search_url, render_js=False)
        soup = BeautifulSoup(html, "lxml")
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "drugs.com/drug-interactions/" in href and not "drugs.com/drug-interactions/search" in href:
                # Some google links are wrapped in /url?q=...
                if "/url?q=" in href:
                    href = href.split("/url?q=")[1].split("&")[0]
                return href
    except Exception as e:
        print(f"Google search lookup failed: {e}")
        
    return None

def get_drug_interaction(
    drug1_generic: str,
    drug2_generic: str = None,
    drug1_reported: str = None,
    drug2_reported: str = None,
) -> str:
    """
    PRIMARY FUNCTION. Fetches interactions between two drugs, or
    side effects/warnings for a single drug if drug2 is omitted.
    Returns a formatted string containing the clinical data.
    """
    drug1 = _normalize(drug1_generic, drug1_reported)
    drug2 = _normalize(drug2_generic, drug2_reported) if (drug2_generic or drug2_reported) else None

    # Base return object on failure
    result = {
        "drug1": drug1,
        "drug2": drug2,
        "severity": "Unknown",
        "interactions": [],
        "summary": "Could not retrieve interaction data.",
        "source_name": "",
        "source_url": "",
        "status": "error",
        "error": None,
    }

    if not drug1:
        result["error"] = "No primary drug provided."
        return export_to_text(result)

    try:
        api_client = get_client()
    except Exception as e:
        result["error"] = f"Client initialization failed: {e}"
        return export_to_text(result)

    for source in INTERACTION_SOURCES:
        # Determine URL format
        if drug2 and source["url_pair"]:
            if source["name"] == "drugs.com":
                url = _search_drug_url(api_client, drug1, drug2)
                if not url:
                    # Fallback to naive format if search fails absolutely
                    url = source["url_pair"].format(drug1=drug1, drug2=drug2)
            else:
                url = source["url_pair"].format(drug1=drug1, drug2=drug2)
        elif not drug2 and source["url_single"]:
            url = source["url_single"].format(drug=drug1)
        else:
            print(f"Skipping {source['name']}: Unsupported mode.")
            continue
            
        print(f"Attempting ScraperAPI for {url}")
        
        try:
            html = api_client.scrape(url, render_js=source["render_js"])
            blocks = extract_interaction_blocks(html)
            
            if blocks:
                # Success!
                first_block = blocks[0]
                summary = first_block["description"][:500] + ("..." if len(first_block["description"]) > 500 else "")
                
                result.update({
                    "severity": first_block["severity"],
                    "interactions": blocks,
                    "summary": summary,
                    "source_name": source["name"],
                    "source_url": url,
                    "status": "ok",
                    "error": None
                })
                return export_to_text(result)
            else:
                print(f"No structured blocks found in {url}.")
                
        except Exception as e:
            print(f"Scrape attempt failed for {url}: {e}")

    # If we exhausted all sources without finding blocks
    result["status"] = "not_found"
    result["error"] = None
    result["summary"] = "No interaction data found for this drug combination."
    return export_to_text(result)

def get_drug_info(drug_generic: str, drug_reported: str = None) -> str:
    """
    Fetches general info about a single drug.
    Tries medlineplus, then drugs.com.
    Returns a formatted string containing the clinical data.
    """
    drug = _normalize(drug_generic, drug_reported)
    
    result = {
        "drug": drug,
        "summary": "Could not retrieve drug information.",
        "side_effects": [],
        "warnings": "",
        "source_name": "",
        "source_url": "",
        "status": "error",
    }

    if not drug:
        return export_to_text(result)

    try:
        api_client = get_client()
    except Exception as e:
        return export_to_text(result)

    # Custom order: medlineplus first
    sources = [
        next((s for s in INTERACTION_SOURCES if s["name"] == "medlineplus"), None),
        next((s for s in INTERACTION_SOURCES if s["name"] == "drugs.com"), None)
    ]
    sources = [s for s in sources if s is not None]

    for source in sources:
        url = source["url_single"].format(drug=drug)
        print(f"Attempting ScraperAPI for INFO {url}")
        
        try:
            html = api_client.scrape(url, render_js=source["render_js"])
            text = extract_clean_text(html)
            
            if len(text) > 50:
                result.update({
                    "summary": text[:600] + ("..." if len(text) > 600 else ""),
                    "source_name": source["name"],
                    "source_url": url,
                    "status": "ok"
                })
                return export_to_text(result)
        except Exception as e:
            print(f"Scrape attempt failed for info {url}: {e}")

    result["status"] = "not_found"
    return export_to_text(result)

def export_to_text(result: dict) -> str:
    """
    Converts a scraping result dictionary into a clean, readable text string.
    Can be used directly with Streamlit's st.download_button() or saved to disk.
    """
    lines = []
    
    if result.get("drug2"):
        lines.append(f"INTERACTION REPORT: {result['drug1'].upper()} & {result['drug2'].upper()}")
        lines.append("=" * 60)
        lines.append(f"Severity: {result.get('severity', 'Unknown')}")
    else:
        lines.append(f"DRUG INFO REPORT: {result.get('drug', 'Unknown').upper()}")
        lines.append("=" * 60)

    lines.append(f"\nSTATUS: {result.get('status', 'error').upper()}")
    
    if result.get("error"):
        lines.append(f"Error Details: {result['error']}")
        
    lines.append(f"\nSOURCE: {result.get('source_name', 'Unknown')} ({result.get('source_url', 'N/A')})")
    lines.append("-" * 60)
    
    lines.append("\nSUMMARY:")
    lines.append(result.get("summary", "No summary available."))
    
    if result.get("side_effects"):
        lines.append("\nKNOWN SIDE EFFECTS:")
        lines.append(", ".join(result["side_effects"]))
        
    if result.get("warnings"):
        lines.append("\nWARNINGS:")
        lines.append(result["warnings"])

    interactions = result.get("interactions", [])
    if interactions:
        lines.append(f"\n\nDETAILED INTERACTIONS ({len(interactions)} records):")
        for i, block in enumerate(interactions, 1):
            lines.append(f"\n--- [ {block.get('severity', 'Unknown')} ] ---")
            lines.append(block.get("description", ""))

    return "\n".join(lines)

if __name__ == "__main__":
    print("--- Drug Interaction Smoke Test ---")
    print(get_drug_interaction("rivaroxaban", "aspirin"))
    print("\n--- Drug Info Smoke Test ---")
    print(get_drug_info("semaglutide"))
