
import streamlit as st

#----3. Helper function----#
def view_header(title, subtitle=None, show_back=False, back_target=None):
    if show_back and back_target:
        if st.button("← Back to {}".format(back_target)):
            st.session_state[back_target] = None
            st.rerun()

    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
    st.divider()