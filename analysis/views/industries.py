from analysis.components.header import view_header
import streamlit as st

def industries_view():
    if st.session_state.selected_company is None:
        view_header(
            "Industries",
            "Corporate tax behavior and sector insights", False, None
        )

    else:
        view_header(f"{st.session_state.selected_company} Analysis", "Industry data Overview", True, "selected_company")