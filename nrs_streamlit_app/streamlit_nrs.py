import streamlit as st
import pandas as pd
import os
import plotly.express as px

# --- 1. DESIGN SYSTEM & SCALE ---
st.set_page_config(layout="wide", page_title="NRS Data Hub")

HEX_BG, HEX_PRIMARY, HEX_GREY_TEXT = "#F9FAFB", "#111827", "#6B7280"
HEX_BORDER, HEX_DANGER, HEX_SUCCESS = "#E5E7EB", "#DC2626", "#16A34A"

st.markdown(f"""
<style>
    .stApp {{ background-color: {HEX_BG}; }}
    .metric-card {{ background: white; padding: 24px; border-radius: 12px; border: 1px solid {HEX_BORDER}; }}
    .m-label {{ color: {HEX_GREY_TEXT}; font-size: 14px; margin-bottom: 8px; }}
    .m-value {{ color: {HEX_PRIMARY}; font-size: 32px; font-weight: 700; }}
    .company-banner {{ background: url('https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200'); background-size: cover; height: 120px; border-radius: 12px 12px 0 0; }}
    .ov-card {{ padding: 20px; border-radius: 10px; margin-bottom: 10px; border: 1px solid {HEX_BORDER}; }}
    .tax-box {{ border-top: 1px solid {HEX_BORDER}; padding-top: 15px; margin-top: 15px; }}
    .tax-row {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }}
    .tax-gap {{ color: {HEX_DANGER}; font-size: 18px; font-weight: 700; }}
</style>
""", unsafe_allow_html=True)

# --- 2. DATA LOADING LOGIC ---
DATA_PATH = "generate_data/output/"


@st.cache_data
def load_nrs_data(file_name):
    # Fallback to dummy data if local files aren't present
    try:
        return pd.read_csv(os.path.join(DATA_PATH, file_name))
    except:
        return pd.DataFrame()


# --- 3. STATE MANAGEMENT ---
if 'nav' not in st.session_state: st.session_state.nav = "Dashboard"
if 'selected_company' not in st.session_state: st.session_state.selected_company = None
if 'analysis_target' not in st.session_state: st.session_state.analysis_target = None


# --- 4. REUSABLE COMPONENTS ---
def draw_interactive_metric(label, value, delta, target_nav, is_up=True):
    container = st.container()
    color = HEX_SUCCESS if is_up else HEX_DANGER
    with container:
        st.markdown(f"""<div class="metric-card"><div class="m-label">{label}</div><div class="m-value">{value}</div>
                    <div style="color:{color}; font-size:14px">{'↑' if is_up else '↓'} {delta}</div></div>""",
                    unsafe_allow_html=True)
        if st.button(f"Analyze {label}", key=f"btn_{label}"):
            st.session_state.nav = "Special_Analysis"
            st.session_state.analysis_target = label
            st.rerun()



# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("## ⬢ NRS Data Hub")
    if st.button("🏠 Dashboard", use_container_width=True): st.session_state.nav = "Dashboard"
    if st.button("🏢 Industries", use_container_width=True):
        st.session_state.nav = "Industries"
        st.session_state.selected_company = None
    if st.button("👥 Individuals", use_container_width=True): st.session_state.nav = "Individuals"

# --- 6. NAVIGATION LOGIC ---

# --- VIEW: SPECIAL ANALYSIS (THE "WHY") ---
if st.session_state.nav == "Special_Analysis":
    st.title(f"Analysis Deep Dive: {st.session_state.analysis_target}")
    if st.button("← Return to Dashboard"):
        st.session_state.nav = "Dashboard"
        st.rerun()

    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.markdown(f"### Regional Breakdown of {st.session_state.analysis_target}")
        # Dummy Plotly logic mapping to your "Waterfall" philosophy
        df_viz = pd.DataFrame({"Sector": ["Tech", "Oil", "Finance", "Retail"], "Value": [40, 30, 20, 10]})
        fig = px.bar(df_viz, x="Sector", y="Value", color="Sector", template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        st.info(
            f"**Insight:** The {st.session_state.analysis_target} is primarily driven by under-reporting in the informal sector.")

# --- VIEW: DASHBOARD ---
elif st.session_state.nav == "Dashboard":
    st.title("National Performance")
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        draw_interactive_metric("Income Gap", "₦348B", "10%", "Special_Analysis", False)
    with m2:
        draw_interactive_metric("Taxpayer Base", "20.8K", "20%", "Special_Analysis")
    with m3:
        draw_interactive_metric("Compliance Index", "82%", "5%", "Special_Analysis")
    with m4:
        draw_interactive_metric("Alerts", "1,204", "16%", "Special_Analysis", False)

# --- VIEW: INDUSTRIES ---
elif st.session_state.nav == "Industries":
    if st.session_state.selected_company is None:
        st.title("Industry Overview")
        # Treemap logic mentioned in Phase 3
        st.markdown("#### Market Compliance Treemap")
        df_ind = pd.DataFrame({
            "Industry": ["Tech", "Tech", "Finance", "Oil", "Oil"],
            "Company": ["Piggyvest", "Paystack", "Zenith", "Shell", "Total"],
            "Turnover": [100, 80, 300, 500, 450],
            "Compliance": [90, 85, 95, 60, 65]
        })
        fig = px.treemap(df_ind, path=['Industry', 'Company'], values='Turnover', color='Compliance',
                         color_continuous_scale='RdYlGn')
        st.plotly_chart(fig, use_container_width=True)

        # Selection Table
        st.markdown("---")
        for name in ["Piggyvest", "MTN", "Zenith"]:
            c_row = st.columns([4, 1])
            c_row[0].write(f"**{name}** | TIN: *****7890")
            if c_row[1].button("View Details", key=f"v_{name}"):
                st.session_state.selected_company = name
                st.rerun()
    else:
        # Entity Detail Deep Dive
        if st.button("← Back to List"):
            st.session_state.selected_company = None
            st.rerun()

        st.markdown('<div class="company-banner"></div>', unsafe_allow_html=True)
        st.header(st.session_state.selected_company)

        tab = st.radio("Analytics", ["Overview", "Inflows", "Outflows"], horizontal=True)

        m_col, s_col = st.columns([2, 1])
        with m_col:
            if tab == "Overview":
                # The Calculation logic for the Side Panel (Phase 3, Step 3)
                v1, v2, v3, v4 = st.columns(4)
                v1.metric("Est. Income", "₦64M")
                v2.metric("Declared", "₦14M")
                v3.metric("Gap", "₦50M", delta_color="inverse")
            elif tab == "Inflows":
                st.write("### Real-time Transaction Monitor")
                st.dataframe(load_nrs_data("transactions.csv").head(10), use_container_width=True)

        with s_col:
            st.markdown("### Tax Computation")
            st.markdown(f"""<div class="tax-box">
                <div class="tax-row"><span>System Estimate</span><b>₦200,000</b></div>
                <div class="tax-row"><span>Declared</span><b>₦50,000</b></div>
                <div class="tax-row"><span style='color:red'>Payable Gap</span><b class='tax-gap'>₦150,000</b></div>
            </div>""", unsafe_allow_html=True)

# --- VIEW: INDIVIDUALS (HNI/Seyi View) ---
elif st.session_state.nav == "Individuals":
    st.title("HNI & Individual Monitoring")
    # Bullet Chart Logic
    st.write("### Income vs. Asset Correlation")
    df_hni = load_nrs_data("individuals.csv")
    if not df_hni.empty:
        fig = px.scatter(df_hni, x="declared_income", y="asset_value", color="status", hover_name="name")
        st.plotly_chart(fig, use_container_width=True)


