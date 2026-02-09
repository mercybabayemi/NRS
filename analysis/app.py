
import streamlit as st
import pandas as pd
import sys
import os

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
individuals, industries, transactions, all_banks, assets  = load_data()

# --- 2. STATE MANAGEMENT ---
for key, val in {"nav": "Dashboard", "selected_company":"", "selected_individual":""}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. SIDEBAR ---
side_bar()

# --- 4. Pages/views ---
views = {
    "Dashboard": dashboard_view,
    "Compliance & scoring": compliance_view,
    "Suspicious activities": suspicious_view,
    "Industries": industries_view,
    "Individuals": individual_view
}

views.get(st.session_state.nav, dashboard_view)()
