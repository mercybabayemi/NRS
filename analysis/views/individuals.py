import streamlit as st
from analysis.components.header import view_header

def individual_view():
    if st.session_state.selected_individual is None or st.session_state.selected_individual is "":
        view_header(
            "Individuals",
            "Individual tax behavior and sector insights"
        )

    else:
        selected_ind = st.session_state.selected_individual
        view_header(f"{st.session_state.selected_individual} Analysis", "Individual data Overview", True, selected_ind)