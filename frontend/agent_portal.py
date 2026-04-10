import streamlit as st
import pandas as pd
import io

def render_agent_portal(df):
    st.markdown('<h1 style="color:#002D72;">Agent Intelligence Portal</h1>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown("""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; border-left: 5px solid #002D72;">
                <h4 style="margin-top:0; color:#002D72;">Analysis Parameters</h4>
                <p style="font-size: 0.9rem; color: #555;">Data context: FAERS Records | Date range: 2019-2024</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("")
        
        col1, col2 = st.columns([1, 2])
        with col1:
            target_drugs = st.text_input("Target Drug Components", placeholder="e.g., Humira")
        with col2:
            user_query = st.text_input("Specific Inquiry", placeholder="e.g., Analyze cardiac risks in 2023")

    if st.button("🚀 DISPATCH AGENTS"):
        if not target_drugs or not user_query:
            st.warning("Please provide both drug components and an inquiry.")
        else:
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_content = csv_buffer.getvalue()

            with st.spinner("Multi-Agent Framework is processing..."):
                mock_output = f"Signal analysis for {target_drugs} complete. Analysis of dataset confirms trends for {user_query}."
                mock_tokens = 4850
                
                st.divider()
                st.subheader("Agent Framework Results")
                
                t1, t2 = st.columns(2)
                t1.metric("Token Usage", f"{mock_tokens:,}")
                t2.metric("Status", "Success")

                st.markdown(f"""
                    <div style="background-color: white; border: 1px solid #002D72; padding: 25px; border-radius: 10px;">
                        <p style="color: #002D72; font-weight: bold; margin-bottom: 5px;">Final Agent Output:</p>
                        <p style="font-family: sans-serif; line-height: 1.6;">{mock_output}</p>
                    </div>
                """, unsafe_allow_html=True)

                st.download_button("Download Agent Report", mock_output, file_name="agent_analysis.txt")