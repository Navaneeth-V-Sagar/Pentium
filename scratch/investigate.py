from scraper.enricher import get_client
from bs4 import BeautifulSoup

client = get_client()

html = client.scrape("https://www.google.com/search?q=site:drugs.com/drug-interactions+ibuprofen+aspirin", render_js=False)
soup = BeautifulSoup(html, "lxml")

links = []
for a in soup.find_all("a", href=True):
    href = a["href"]
    # Google's raw result links sometimes look like /url?q=https://www.drugs.com/...
    if "drugs.com/drug-interactions/" in href:
        if "/url?q=" in href:
            href = href.split("/url?q=")[1].split("&")[0]
        links.append(href)

print("Found links:", links)
