"""
# ── Paste into your existing Streamlit app.py ──────────────────

from scraper import get_drug_interaction, get_drug_info

# ── Single drug lookup ─────────────────────────────────────────
# drug_generic comes from df["drug_name_generic"] column
result = get_drug_info(
    drug_generic="rivaroxaban",
    drug_reported="XARELTO"        # fallback if generic missing
)

if result["status"] == "ok":
    st.subheader(result["drug"])
    st.write(result["summary"])
    st.write("**Known Side Effects:**", ", ".join(result["side_effects"]))
    st.warning(result["warnings"])
    st.caption(f"Source: {result['source_url']}")

# ── Two drug interaction lookup ────────────────────────────────
result = get_drug_interaction(
    drug1_generic="rivaroxaban",
    drug2_generic="semaglutide",
    drug1_reported="XARELTO",      # optional fallbacks
    drug2_reported="ozempic"
)

if result["status"] == "ok":
    # Color-code by severity
    severity_colors = {
        "Contraindicated": "error",
        "Major":           "error",
        "Moderate":        "warning",
        "Minor":           "info",
        "Unknown":         "info",
    }
    getattr(st, severity_colors[result["severity"]])(
        f"Severity: {result['severity']}"
    )
    st.write(result["summary"])
    for block in result["interactions"]:
        with st.expander(block["severity"]):
            st.write(block["description"])
    st.caption(f"Source: {result['source_url']}")

elif result["status"] == "not_found":
    st.info("No interaction data found for this drug combination.")

elif result["status"] == "error":
    st.error(result["error"])

# ── Handling missing generic names (real FAERS issue) ──────────
# ~12% of drug_name_generic is missing in FAERS data
# Always pass both columns so enricher can fall back:
row = df.iloc[0]
result = get_drug_interaction(
    drug1_generic=row.get("drug_name_generic"),   # may be NaN
    drug1_reported=row.get("drug_name_reported"),  # always present
)
# ───────────────────────────────────────────────────────────────
"""

from scraper.enricher import get_drug_interaction, get_drug_info, export_to_text

__all__ = ["get_drug_interaction", "get_drug_info", "export_to_text"]
