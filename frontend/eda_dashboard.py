import streamlit as st
import plotly.express as px

def render_dashboard(df):
    st.markdown('<h1 style="color:#002D72;">Drug Safety EDA Dashboard</h1>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Records", f"{len(df):,}")
    with col2:
        avg_age = df['patient_age_years'].mean() if 'patient_age_years' in df.columns else 0
        st.metric("Avg Patient Age", f"{avg_age:.1f} yrs")
    with col3:
        dupes = len(df[df['is_duplicate'] == 'Y']) if 'is_duplicate' in df.columns else 0
        st.metric("Duplicate Flags", f"{dupes:,}")
    with col4:
        fatal = len(df[df['outcome'] == 'Fatal']) if 'outcome' in df.columns else 0
        st.metric("Fatal Outcomes", fatal)

    st.divider()

    if 'report_year' in df.columns:
        st.subheader("Reporting Volume Trends (2019-2024)")
        trend_data = df.groupby('report_year').size().reset_index(name='Reports')
        fig_trend = px.area(trend_data, x='report_year', y='Reports', color_discrete_sequence=['#00A3E0'])
        st.plotly_chart(fig_trend, use_container_width=True)

    if 'drug_class' in df.columns and 'is_serious' in df.columns:
        st.subheader("Seriousness Profile by Drug Class")
        fig_bar = px.bar(df, x="drug_class", color="is_serious", barmode="group", color_discrete_map={'Y': '#002D72', 'N': '#00A3E0'})
        st.plotly_chart(fig_bar, use_container_width=True)