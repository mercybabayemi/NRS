from analysis.components.header import view_header
import streamlit as st

def industries_view():
    if st.session_state.selected_company is None or st.session_state.selected_company is "":
        view_header(
            "Industries",
            "Corporate tax behavior and sector insights", False, None
        )

    else:
        selected_comp = st.session_state.get()
        view_header(f"{st.session_state.selected_company} Analysis", "Industry data Overview", True, selected_comp)