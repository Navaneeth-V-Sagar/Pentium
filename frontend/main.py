import streamlit as st
import pandas as pd
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__)) 
root_dir = os.path.dirname(current_dir) 

if root_dir not in sys.path:
    sys.path.append(root_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from Data_pipeline.faers_pipeline import run_pipeline
except ImportError as e:
    st.error(f"Import Error: {e}")

from eda_dashboard import render_dashboard
from agent_portal import render_agent_portal

st.set_page_config(page_title="MResult | Drug Safety AI", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stSidebar"] { background-color: #002D72; }
    [data-testid="stSidebar"] * { color: white !important; }
    .main-header { color: #002D72; font-weight: 800; font-size: 2.2rem; }
    </style>
""", unsafe_allow_html=True)

st.sidebar.image("https://mresult.com/wp-content/uploads/2021/04/mresult-logo.png", width=150)
st.sidebar.markdown("### SYSTEM CONTROLS")

uploaded_file = st.sidebar.file_uploader("Upload faers_adverse_events.csv", type=['csv'])

if uploaded_file:
    if st.sidebar.button("RUN PIPELINE"):
        with st.sidebar.status("Processing..."):
            raw_df = pd.read_csv(uploaded_file)
            st.session_state['data'] = run_pipeline(raw_df)
        st.sidebar.success("Pipeline Complete")

st.sidebar.divider()
page = st.sidebar.radio("Navigation", ["EDA Dashboard", "Agent Portal"])

if 'data' not in st.session_state:
    st.markdown('<h1 class="main-header">Pharmacovigilance Intelligence Suite</h1>', unsafe_allow_html=True)
    st.info("Upload the FAERS dataset to begin signal detection analysis.")
else:
    if page == "EDA Dashboard":
        render_dashboard(st.session_state['data'])
    else:
        render_agent_portal(st.session_state['data'])