"""
scraper/config.py
─────────────────
Resolves the ScraperAPI key in priority order:
  1. st.secrets["SCRAPERAPI_KEY"]  (Streamlit Cloud)
  2. os.getenv("SCRAPERAPI_KEY")   (local / .env via python-dotenv)

Wrap every st.* call in try/except so the module loads outside Streamlit.
"""
import os

# Load .env file if present (no-op when python-dotenv not installed)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def get_scraperapi_key() -> str:
    """
    Return the ScraperAPI key, or raise ValueError with setup instructions.
    """
    # ── Priority 1: Streamlit Secrets ─────────────────────────────────────
    try:
        import streamlit as st  # noqa: PLC0415
        key = st.secrets.get("SCRAPERAPI_KEY")
        if key:
            return key
    except Exception:
        # Running outside Streamlit — normal for CLI / tests
        pass

    # ── Priority 2: Environment variable ──────────────────────────────────
    key = os.getenv("SCRAPERAPI_KEY")
    if key:
        return key

    # ── Not found ─────────────────────────────────────────────────────────
    raise ValueError(
        "ScraperAPI key not found. Provide it via ONE of:\n"
        "  • Streamlit Cloud  → App Settings → Secrets → SCRAPERAPI_KEY = \"…\"\n"
        "  • Local .env file  → SCRAPERAPI_KEY=your_key_here\n"
        "  • Shell env        → export SCRAPERAPI_KEY=your_key_here\n"
        "Get a free key at https://www.scraperapi.com/"
    )
