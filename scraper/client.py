"""
scraper/client.py
─────────────────
HTTP client for ScraperAPI. Retrieves raw HTML strings.
Handles Streamlit caching outside Streamlit gracefully.
"""
import requests
from requests.exceptions import Timeout, RequestException
from .config import get_scraperapi_key

# ── Safe Streamlit Cache Wrapper ───────────────────────────────────────
# Try to use @st.cache_data if Streamlit is available.
# Otherwise, provide a pass-through dummy decorator.
try:
    import streamlit as st
    # Use cache_data, safely wrapped. If not imported in Streamlit context,
    # sometimes it still works, but safety first.
    cache_wrapper = st.cache_data(ttl=300, show_spinner=False)
except ImportError:
    def cache_wrapper(func):
        return func


class ScraperAPIClient:
    BASE = "https://api.scraperapi.com"
    TIMEOUT = 70

    def __init__(self):
        # Resolve key instantly upon instantiation
        self.api_key = get_scraperapi_key()

    @cache_wrapper
    def scrape(
        _self,
        url: str,
        render_js: bool = False,
        country_code: str = None,
        premium: bool = False,
    ) -> str:
        """
        Sends request to ScraperAPI and returns HTML.
        Decorated via Streamlit caching to prevent burning credits on app reruns.
        """
        params = {
            "api_key": _self.api_key,
            "url": url,
        }

        if render_js:
            params["render_js"] = "true"
        if country_code:
            params["country_code"] = country_code
        if premium:
            params["premium"] = "true"

        try:
            # We use TIMEOUT = 70 across the board as ScraperAPI takes time
            response = requests.get(
                _self.BASE,
                params=params,
                timeout=_self.TIMEOUT
            )

            # Special cases defined in requirements
            if response.status_code == 401:
                raise RuntimeError("Invalid ScraperAPI key.")
            elif response.status_code == 429:
                raise RuntimeError("Rate limit hit. Reduce requests or upgrade plan.")
            elif response.status_code != 200:
                raise RuntimeError(
                    f"HTTP {response.status_code}: {response.text[:200]}"
                )

            return response.text

        except Timeout:
            raise RuntimeError(f"Request timed out after {_self.TIMEOUT}s.")
        except RequestException as e:
            raise RuntimeError(f"Request failed: {str(e)}")
