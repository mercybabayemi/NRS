
import streamlit as st
import pandas as pd
import sys
import os

from analysis.components.audit_data import audit_data
#from analysis.components.clean_data import clean_data

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from components.sidebar import side_bar
from views.compliance import compliance_view
from views.dashboard import dashboard_view
from views.individuals import individual_view
from views.industries import industries_view
from views.suspicious_activity import suspicious_view
from components.load_data import load_data

# --- 1. DESIGN SYSTEM & STYLE ---
st.set_page_config(layout="wide", page_title="NRS Data Hub")

## --- 2. Load real data ---
individuals_loaded, industries_loaded, taxes_loaded, transaction_loaded, banks_loaded, assets_loaded, relationships_loaded  = load_data()
audit_data(individuals_loaded, industries_loaded, taxes_loaded, transaction_loaded, banks_loaded, assets_loaded, relationships_loaded)
#clean_data(industries_loaded, individuals_loaded)


# --- 2. STATE MANAGEMENT ---
for key, val in {"nav": "Dashboard", "selected_company":"", "selected_individual":""}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. SIDEBAR ---
side_bar()

# --- 4. Pages/views ---
# views = {
#     "Dashboard": dashboard_view,
#     "Compliance & scoring": compliance_view,
#     "Suspicious activities": suspicious_view,
#     "Industries": industries_view,
#     "Individuals": individual_view
# }
#
# views.get(st.session_state.nav)

if st.session_state.nav == "Dashboard":
    dashboard_view()
elif st.session_state.nav == "Compliance & scoring":
    compliance_view()
elif st.session_state.nav == "Suspicious activities":
    suspicious_view()
elif st.session_state.nav == "Industries":
    industries_view()
elif st.session_state.nav == "Individuals":
    individual_view()
