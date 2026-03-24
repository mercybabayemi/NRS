
import streamlit as st

#----3. Helper function----#
def side_bar():
    with st.sidebar:
        st.markdown("## ⬢ NRS Data Hub")
        nav_options = ["Dashboard", "Compliance & scoring", "Suspicious activities", "Industries", "Individuals"]
        for option in nav_options:
            if st.button(option,
                         use_container_width=True,
                         #type="primary" if st.session_state.nav == option else "secondary"
                         ):
                st.session_state.nav = option
                st.rerun()
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.divider()
        st.caption("Ibrahim Adedeji")
        st.caption("ibrahim@datahub.com")