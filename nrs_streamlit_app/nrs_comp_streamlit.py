import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os


## --- Load real data ---
@st.cache_data
def load_data():
    # Adding error handling for file existence
    data_dir = "generate_data/output/"
    def read_safe(file):
        path = os.path.join(data_dir, file)
        return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

    individuals = pd.read_csv("generate_data/output/individuals.csv")
    companies = pd.read_csv("generate_data/output/companies.csv")
    taxes = pd.read_csv("generate_data/output/taxes.csv")
    aml_flags_individual = pd.read_csv("generate_data/output/aml_flags.csv")
    aml_flags_companies = pd.read_csv("generate_data/output/aml_flags_companies.csv")
    spend_events = pd.read_parquet("generate_data/parquet/spend_events.parquet")
    transactions = pd.read_parquet("generate_data/parquet/transactions.parquet")
    banks = pd.read_csv("generate_data/output/banks_financial.csv")
    assets = pd.read_csv("generate_data/output/assets.csv")
    spend_aggregrates = pd.read_csv("generate_data/output/spend_aggregates.csv")
    relationships = pd.read_parquet("generate_data/parquet/relationships.parquet")

    # Ensure date columns are datetime objects
    for df in [taxes, transactions, spend_events, spend_aggregrates, relationships,
               aml_flags_individual, aml_flags_companies, companies, individuals, banks, assets ]:
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

    return individuals, companies, taxes, aml_flags_individual, aml_flags_companies, transactions, spend_events, spend_aggregrates

individuals, companies, taxes, aml_flags_individual, aml_flags_companies, transactions, spend_events, spend_aggregrates = load_data()

# --- 1. DESIGN SYSTEM & STYLE ---
st.set_page_config(layout="wide", page_title="NRS Data Hub")

# ---------------- 1. CONFIG & BRANDING ----------------
st.set_page_config(page_title="NRS 2026 National Snapshot", layout="wide")

# Figma Brand Colors
HEX_BG, HEX_PRIMARY, HEX_GREY_TEXT = "#F9FAFB", "#111827", "#6B7280"
HEX_BORDER, HEX_DANGER, HEX_SUCCESS = "#E5E7EB", "#DC2626", "#16A34A"

# Global Styling (CSS)
st.markdown(f"""
<style>
    .stApp {{ background-color: {HEX_BG}; }}

    /* Force all text elements to Black */
    html, body, [data-testid="stAppViewContainer"], .stMarkdown, p, h1, h2, h3, h4, h5, h6, span, label, .stTabs [data-baseweb="tab"] {{
        color: #767676 !important;
        font-family: 'Source Sans Pro', sans-serif;
    }}

    /* Metric Cards Styling */
    [data-testid="stMetricLabel"], [data-testid="stMetricValue"] {{
        color: black !important;
    }}

    .metric-card {{
        background: white;
        padding: 24px;
        border-radius: 12px;
        border: 1px solid {HEX_BORDER};
    }}

    .m-label {{ color: {HEX_GREY_TEXT}; font-size: 14px; margin-bottom: 8px; }}
    .m-value {{ color: {HEX_PRIMARY}; font-size: 32px; font-weight: 700; }}

    /* Dataframe Visibility */
    [data-testid="stTable"] td, [data-testid="stTable"] th, .dataframe th, .dataframe td {{
        color: black !important;
    }}

    /* Tax Computation Sidebar Extras */
    .tax-box {{ border-top: 1px solid {HEX_BORDER}; padding-top: 15px; margin-top: 15px; }}
    .tax-row {{ display: flex; justify-content: space-between; margin-bottom: 10px; font-size: 14px; }}
    .tax-val {{ font-weight: 600; }}
    .tax-gap {{ color: {HEX_DANGER}; font-size: 18px; font-weight: 700; }}
</style>
""", unsafe_allow_html=True)

# --- 2. STATE MANAGEMENT ---
for key, val in {"nav": "Dashboard", "selected_state": None, "time_filter": "all", "selected_company":""}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 3. REUSABLE COMPONENTS ---
def metric_card(label, value, delta, route=None, danger=False):
    """
    Creates a clickable card using a container and a button.
    """
    with st.container(border=True):
        # Inject custom HTML for the card look
        color = HEX_DANGER if danger else HEX_SUCCESS
        st.markdown(f"""
            <div style="margin-bottom: -45px;">
                <div style="color:{HEX_GREY_TEXT}; font-size:14px;">{label}</div>
                <div style="color:{HEX_PRIMARY}; font-size:28px; font-weight:700; margin: 5px 0;">{value}</div>
                <div style="color:{HEX_SUCCESS}; font-size:13px; font-weight:500;">{delta}</div>
            </div>
        """, unsafe_allow_html=True)
        st.divider()
        # Transparent button overlay for routing
        if st.button("View Details →", key=f"nav_{label}", use_container_width=True):
            st.session_state.nav = route
            st.rerun()


def apply_time_filter(df):
    if df.empty or 'date' not in df.columns:
        return df
    today = pd.Timestamp.today()
    if st.session_state.time_filter == "12m":
        return df[df["date"] >= today - pd.DateOffset(months=12)]
    if st.session_state.time_filter == "7d":
        return df[df["date"] >= today - pd.DateOffset(days=7)]
    return df

def apply_global_filters(ind, comp, tax):
    ind_f = ind.copy()
    comp_f = comp.copy()
    tax_f = tax.copy()

    # 🔹 Search
    q = st.session_state.get("main_search", "").strip().lower()
    if q:
        if 'tin' or 'bvn' or 'name' in comp_f.columns:
            comp_f = comp_f[comp_f['name'].str.lower().str.contains(q, na=False)]
        if 'tin' or 'bvn' or 'name' in ind_f.columns:
            ind_f = comp_f[comp_f['name'].str.lower().str.contains(q, na=False)]
        if 'tin' or 'bvn' or 'name' in tax_f.columns:
            tax_f = ind_f[ind_f['name'].str.lower().str.contains(q, na=False)]


    # 🔹 State filter
    if st.session_state.selected_state:
        if 'state_of_residence' in ind_f.columns:
            ind_f = ind_f[ind_f['state_of_residence'].str.title() == st.session_state.selected_state]

        tax_f = tax_f.merge(
            ind_f[['individual_id']],
            left_on='entity_id',
            right_on='individual_id',
            how='inner'
        )

    # 🔹 Time filter
    tax_f = apply_time_filter(tax_f)

    return ind_f, comp_f, tax_f

# --- 1. ENHANCED DATA MAPPING ---
GEO_ZONES = {
    'North Central': ['Benue', 'Kogi', 'Kwara', 'Nasarawa', 'Niger', 'Plateau', 'Abuja (FCT)',
                      'Federal Capital Territory'],
    'North East': ['Adamawa', 'Bauchi', 'Borno', 'Gombe', 'Taraba', 'Yobe'],
    'North West': ['Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi', 'Sokoto', 'Zamfara'],
    'South East': ['Abia', 'Anambra', 'Ebonyi', 'Enugu', 'Imo'],
    'South South': ['Akwa Ibom', 'Bayelsa', 'Cross River', 'Delta', 'Edo', 'Rivers'],
    'South West': ['Ekiti', 'Lagos', 'Ogun', 'Ondo', 'Osun', 'Oyo']
}

# Create a flat map for easy pandas lookup
ZONE_LOOKUP = {state: zone for zone, states in GEO_ZONES.items() for state in states}
states = df

# --- 4. DATA PROCESSING ---
# Filter data first
filtered_ind , filtered_comp, filtered_taxes = apply_global_filters(individuals, companies, taxes)

# 1. Identify the correct ID column in ind
filtered_id_col = next((col for col in ['individual_id', 'entity_id', 'id'] if col in filtered_ind.columns), None)

if filtered_id_col:
    # Merge using the identified column
    filtered_ind = filtered_ind.merge(
        filtered_ind[['individual_id']],
        left_on=filtered_id_col,
        right_on='individual_id',
        how='inner'
    )
else:
    # Fallback if no matching ID found
    individuals, companies, taxes = pd.DataFrame({individuals, companies, taxes})

# KPI Calculations
total_pop = filtered_ind['individual_id'].nunique()
total_taxpayers = filtered_taxes['entity_id'].nunique()
avg_compliance = filtered_taxes['compliance_percent'].mean() if not filtered_taxes.empty else 0
total_alerts = filtered_ind.shape[0] + aml_flags_companies.shape[0]
taxpayer_rate = (total_taxpayers / total_pop * 100) if total_pop > 0 else 0

#----Helper function----#
def view_header(title, subtitle=None):
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)
    if st.button("← Back to Dashboard"):
        st.session_state.nav = "Dashboard"
        st.rerun()
    st.divider()


# --- 5. SIDEBAR ---
with st.sidebar:
    st.markdown("## ⬢ NRS Data Hub")
    nav_options = ["Dashboard", "Compliance & scoring", "Suspicious activities", "Industries", "Individuals"]
    for option in nav_options:
        if st.button(option, use_container_width=True, type="secondary" if st.session_state.nav != option else "primary"):
            st.session_state.nav = option
            st.rerun()
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    st.divider()
    st.caption("Ibrahim Adedeji")
    st.caption("ibrahim@datahub.com")

# --- 6. VIEW: DASHBOARD ---
if st.session_state.nav == "Dashboard":
    # 1. Title Section
    st.markdown('<h1 style="color:#111827; margin-bottom:0;">Welcome back, Ibrahim</h1>', unsafe_allow_html=True)
    # 2. Subtitle and Search Row
    col_sub, col_search = st.columns([3, 1])
    with col_sub:
     st.markdown(
        "<p style='color:#6B7280; font-size:16px;'>Monitor national tax performance, data flows, and compliance insights at a glance.</p>",
    unsafe_allow_html=True)
    with col_search:
    # Aligned to the top right as per Figma
        st.text_input("Search", placeholder="Search", label_visibility="collapsed", key="main_search")

    # 3. Action Bar (Time Toggles + Date/Filter Actions)
    # Using more columns to create the specific spacing
    act_col1, act_col2 = st.columns([1, 1])
    taxes_filtered = apply_time_filter(taxes)
    with act_col1:
        # Time Toggle Buttons (Figma-style)
        t1, t2, t3, _ = st.columns([0.2, 0.2, 0.2, 0.4])

        with t1:
            if st.button("All time"):
                st.session_state.time_filter = "all"
                st.rerun()

        with t2:
            if st.button("12 months"):
                st.session_state.time_filter = "12m"
                st.rerun()
        with t3:
            if st.button("7 days"):
                st.session_state.time_filter = "7d"
                st.rerun()

    with act_col2:
        # Select Dates and Filters aligned to right
        _, d1, f1 = st.columns([0.4, 0.3, 0.3])

        # ---- Prepare options safely ----
        yoa_options = sorted(filtered_taxes['YOA'].dropna().unique())
        default_yoa = yoa_options[:5] if len(yoa_options) >= 5 else yoa_options

        state_options = sorted(filtered_comp['state'].dropna().unique())
        default_state = state_options[:5] if len(state_options) >= 5 else state_options

        with act_col2:
            # Right-aligned controls
            _, d1, f1 = st.columns([0.4, 0.3, 0.3])

            with d1:
                st.markdown(
                    "<p style='color:#6B7280; font-size:14px; margin-bottom:4px;'>Select Tax YOA</p>",
                    unsafe_allow_html=True
                )
                state_dates = st.multiselect(
                    label="",
                    options=yoa_options,
                    default=default_yoa
                )

            with f1:
                st.markdown(
                    "<p style='color:#6B7280; font-size:14px; margin-bottom:4px;'>Filter Individual or Company</p>",
                    unsafe_allow_html=True
                )
                state_filter = st.multiselect(
                    label="",
                    options=state_options,
                    default=default_state
                )

    if st.session_state.selected_state:
        st.info(f"Filtered by state: {st.session_state.selected_state}")

    st.markdown("---")  # Visual separator

    # Cards Section
    c1, c2, c3, c4 = st.columns(4)
    with c1: metric_card("Population", f"{total_pop:,}", "Total Registry", route="General Overview")
    with c2: metric_card("Taxpayers", f"{total_taxpayers:,}", f"{taxpayer_rate:.1f}% Rate", route="Individuals")
    with c3: metric_card("Compliance Index", f"{avg_compliance:.1f}%", "Avg Score", route="Compliance & scoring")
    with c4: metric_card("AML Alerts", f"{total_alerts:,}", "High Risk Flags", route="Suspicious activities", danger=True)

    # Map Logic

    def prepare_analysis_data(ind, tax, comp):
        # Standardize and Join
        ind.columns = [c.lower() for c in ind.columns]
        tax.columns = [c.lower() for c in tax.columns]
        comp.columns = [c.lower() for c in comp.columns]

        # Create Geopolitical Zone column
        ind['state'] = ind['state_of_residence'].str.strip()
        # ind['geopolitical_zone'] = ind['state'].map(ZONE_LOOKUP)
        ZONE_LOOKUP = {state: zone for zone, states in GEO_ZONES.items() for state in states}
        ind['geopolitical_zone'] = ind['state'].map(ZONE_LOOKUP).fillna("Unknown")

        # Note: If gender isn't in your CSV, we often infer or use a placeholder
        # For this snippet, we assume 'gender' exists or we use 'occupation' as a proxy
        if 'gender' not in ind.columns:
            ind['gender'] = "Not Specified"

            # Merge Tax with Individuals
        merged_ind = tax.merge(ind, left_on='entity_id', right_on='individual_id')
        return merged_ind, comp


    merged_ind, comp = prepare_analysis_data(individuals, taxes, companies)
    # --- 2. MULTI-DIMENSIONAL UI ---

    st.title("🇳🇬 National Compliance Analysis")
    st.markdown("---")

    # Top Level National Metrics (The "Image 2" look)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Avg Compliance", f"{merged_ind['compliance_percent'].mean():.1f}%")
    m2.metric("Total Tax Collected", f"₦{merged_ind['paid_amount'].sum():,.0f}")
    m3.metric("Highest Risk Zone", "North West")  # Dynamic based on data
    m4.metric("Active Taxpayers", f"{len(merged_ind):,}")

    st.markdown("### 📊 Deep-Dive Analysis")
    tab1, tab2, tab3 = st.tabs(["🌍 Geopolitical Zones", "🏭 Industry", "👤 Gender/Demographics"])


    # --- TAB 2: GEOPOLITICAL ZONES ---
    with tab1:
        st.markdown("#### **Compliance Performance by Geopolitical Zone**")
        zone_data = merged_ind.groupby('geopolitical_zone')['compliance_percent'].mean().reset_index().sort_values(
            'compliance_percent', ascending=False)

        fig_zone = px.bar(
            zone_data, x='geopolitical_zone', y='compliance_percent',
            color='compliance_percent', color_continuous_scale="RdYlGn",
            text_auto='.1f', title="Regional Performance Ranking"
        )
        st.plotly_chart(fig_zone, use_container_width=True)

    # --- TAB 3: INDUSTRY ---
    with tab2:  # Swapped for brevity in code snippet
        st.markdown("#### **Industry Revenue & Leakage Analysis**")
        fig_ind = px.treemap(
            comp, path=['industry_sector', 'name'], values='turnover',
            color='cit_due', color_continuous_scale="Viridis",
            title="Revenue Concentration (Size: Turnover, Color: Tax Due)"
        )
        st.plotly_chart(fig_ind, use_container_width=True)

    # --- TAB 4: GENDER & DEMOGRAPHICS ---
    with tab3:
        st.markdown("#### **Demographic Breakdown**")
        c1, c2 = st.columns(2)

        with c1:
            st.write("**Compliance by Gender**")
            gender_data = merged_ind.groupby('gender')['compliance_percent'].mean().reset_index()
            fig_pie = px.pie(gender_data, values='compliance_percent', names='gender', hole=.4)
            st.plotly_chart(fig_pie, use_container_width=True)

        with c2:
            st.write("**High-Risk Occupations**")
            occ_risk = merged_ind.groupby('occupation')['risk_score'].mean().sort_values(ascending=False).head(
                10).reset_index()
            fig_occ = px.bar(occ_risk, x='risk_score', y='occupation', orientation='h', color='risk_score',
                             color_continuous_scale="Reds")
            st.plotly_chart(fig_occ, use_container_width=True)

# --- VIEW: INDUSTRIES ---
elif st.session_state.nav == "Industries":
    if st.session_state.selected_company is None:
        st.title("Industries")
        m1, m2, m3, m4 = st.columns(4)
        # with m1:
        #     draw_metric("Declared income", "₦122B", "20%")
        # with m2:
        #     draw_metric("Estimated income", "₦470B", "40%")
        # with m3:
        #     draw_metric("Income gap", "₦348B", "10%", is_up=False)
        # with m4:
        #     draw_metric("Potential tax revenue", "₦592B", "20%")

        st.markdown("### Industries <span style='color:grey; font-size:14px'>240,000</span>", unsafe_allow_html=True)
        st.write("---")
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            st.text_input("Search", placeholder="Search by name or TIN")
        with c2:
            st.selectbox("State", )

        df_indus = pd.DataFrame({
            "Name": ["Piggyvest", "MTN", "Zenith", "Guaranty Bank", "Glovo", "FBN"],
            "TIN": ["*****7890-0001", "*****4546-0003", "*****8757-0002", "*****8823-0006", "*****9981-0001",
                    "*****9754-0007"],
            "Tax period": ["Q1, 2024", "Q2, 2024", "Q3, 2024", "Q4, 2024", "Q1, 2024", "Q1, 2024"],
            "Compliance": ["70%", "60%", "90%", "20%", "40%", "60%"],
            "Type": ["Plc", "Limited", "NGO", "Plc", "Plc", "Plc"]
        })


        for idx, row in df_indus.iterrows():
            cols = st.columns([2, 2, 1, 1, 1, 1])
            cols[0].write(row['Name'])
            cols[1].write(row['TIN'])
            cols[2].write(row['Tax period'])
            cols[3].write(row['Compliance'])
            cols[4].write(row['Type'])
            if cols[5].button("View", key=row['Name']):
                st.session_state.selected_company = row['Name']
                st.rerun()

    else:
        # --- COMPANY DETAIL VIEW (NESTED) ---
        if st.button("← Back"):
            st.session_state.selected_company = None
            st.rerun()

        st.markdown('<div class="company-banner"></div>', unsafe_allow_html=True)
        col_header, col_info = st.columns([1, 4])
        with col_header:
            st.image("https://ui-avatars.com/api/?name=P&background=0047FF&color=fff", width=80)
        with col_info:
            st.subheader(st.session_state.selected_company)
            st.caption("TIN: *****45565 | info@piggyvest.com")

        # Horizontal Stats Bar from Image
        st.markdown(f"""
            <div style="background: #F9FAFB; padding: 15px; border-radius: 8px; border: 1px solid {HEX_BORDER}; margin: 20px 0;">
                <div style="display: flex; justify-content: space-between; font-size: 12px;">
                    <div><span style="color:grey">RC</span><br><b>****567891</b></div>
                    <div><span style="color:grey">No of directors</span><br><b>4</b></div>
                    <div><span style="color:grey">Industry</span><br><b>Technology</b></div>
                    <div><span style="color:grey">Type</span><br><b>Plc</b></div>
                    <div><span style="color:grey">Employees</span><br><b>120</b></div>
                    <div><span style="color:grey">Customers base</span><br><b>50M</b></div>
                    <div><span style="color:grey">Location</span><br><b>🇳🇬 Lagos, Nigeria</b></div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Tab Navigation
        tab_nav = st.radio("View", ["Overview", "Inflows", "Outflows", "Directors", "Tax payment history", "Employees",
                                    "Customers"],
                           horizontal=True, label_visibility="collapsed")

        main_col, side_col = st.columns([2.5, 1])

        with main_col:
            if tab_nav == "Overview":
                st.markdown("### Overview")
                st.caption("An overview of tax payer details")
                ov1, ov2, ov3, ov4 = st.columns(4)
                ov1.markdown(
                    '<div class="ov-card" style="background:#FDF2FF">Estimated income<br><h3>₦64,000,000.00</h3></div>',
                    unsafe_allow_html=True)
                ov2.markdown(
                    '<div class="ov-card" style="background:#F0FDF4">Declared income<br><h3>₦14,000,000.00</h3></div>',
                    unsafe_allow_html=True)
                ov3.markdown(
                    '<div class="ov-card" style="background:#EFF6FF">Net difference<br><h3>₦50,000,000.00</h3></div>',
                    unsafe_allow_html=True)
                ov4.markdown(
                    '<div class="ov-card" style="background:#FFF1F2">Estimated tax gap<br><h3>₦24,000,00.60</h3></div>',
                    unsafe_allow_html=True)

                st.markdown("#### AI Generated description")
                st.info(
                    f"{st.session_state.selected_company} is a privately held Nigerian financial technology company.")

            elif tab_nav == "Inflows":
                st.markdown("### Inflows")
                st.caption("An overview of transaction inflows")
                st.segmented_control("Filter", ["All", "Operations", "Investments", "Finance", "Donations"],
                                     default="All", label_visibility="collapsed")

                # Transaction Data for Inflows
                inflow_data = pd.DataFrame({
                    "Date": ["22 Jan 2022", "22 Jan 2023", "23 Jan 2024"],
                    "Amount": ["₦30,217,739.23", "₦4,617,235.10", "₦25,442,163.99"],
                    "From": ["Bokku Mart", "Chioma Rita", "Ardova plc"],
                    "Method": ["Transfer", "Transfer", "POS"]
                })
                st.dataframe(inflow_data, use_container_width=True, hide_index=True)

            elif tab_nav == "Outflows":
                st.markdown("### Outflows")
                st.caption("An overview of transaction outflows")
                st.segmented_control("Filter", ["All", "Operations", "Investments", "Finance", "Donations"],
                                     default="All", label_visibility="collapsed")

                # Transaction Data for Outflows
                outflow_data = pd.DataFrame({
                    "Date": ["22 Jan 2022", "22 Jan 2023"],
                    "Amount": ["₦348,200.00", "₦18,482,800.00"],
                    "To": ["Bokku Mart", "Chioma Rita"],
                    "Method": ["Transfer", "Transfer"]
                })
                st.dataframe(outflow_data, use_container_width=True, hide_index=True)

        with side_col:
            st.markdown("### Tax computation")
            st.caption("A breakdown of estimated payable tax")
            st.markdown(f"""
                <div class="tax-box">
                    <div class="tax-row"><span>Declared taxable income</span><span class="tax-val">₦2,000.00</span></div>
                    <div class="tax-row"><span>Predicted taxable income</span><span class="tax-val">₦200,000.00</span></div>
                    <hr style="border:0.5px solid {HEX_BORDER}">
                    <div class="tax-row"><span>Predicted payable tax</span><span class="tax-gap">₦150,000.00</span></div>
                </div>
            """, unsafe_allow_html=True)

        view_header(
            "Industries & Companies",
            "Corporate tax behavior and sector insights"
        )

        st.metric("Companies", filtered_comp.shape[0])

        st.dataframe(
            filtered_comp.head(100),
            use_container_width=True
        )

elif st.session_state.nav == "General Overview":
    st.title("National Overview")
    st.markdown("##### **Question: What is the national snapshot?**")
    # Metrics Section
    col1, col2, col3, col4 = st.columns(4)

    population_count = individuals['individual_id'].nunique()
    total_alerts_individual = len(aml_flags_individual)
    total_alerts_companies = len(aml_flags_companies)
    avg_compliance = filtered_taxes['compliance_percent'].mean()

    with col1:
        st.metric("Population", f"{population_count:,}")
    with col2:
        st.metric("Total Alerts for individuals", f"{total_alerts:,}")
    with col3:
        st.metric("Total Alerts for companies", f"{total_alerts_companies:,}")
    with col4:
        st.metric("Avg Compliance", f"{avg_compliance:.1f}%")

elif st.session_state.nav == "Taxpayer":
    st.title("Taxpayer")
    st.markdown("How many people currently pay their tax")
    st.markdown("#### **Taxpayer Sample Data (Top 100)**")
    st.dataframe(filtered_ind.head(100), use_container_width=True)


# --- VIEW: INDIVIDUALS ---
elif st.session_state.nav == "Individuals":

    view_header(
        "Individuals",
        "Filtered view of registered individual taxpayers"
    )

    st.metric("Individuals Count who has paid = ", filtered_ind.shape[0])

    st.dataframe(
        filtered_ind.head(100),
        use_container_width=True
    )


    st.markdown("### Individuals <span style='color:grey; font-size:14px'>120,000</span>", unsafe_allow_html=True)
    df_ind = pd.DataFrame({
        "TIN": ["13456785", "13456789", "13456789", "13456789"],
        "Tax station": ["Agege", "Mushin1", "Ojo", "Epe"],
        "State of residence": ["Kano", "Kebbi", "Kastina", "Kogi"],
        "Status": ["Flagged", "Compliant", "Flagged", "Flagged"]
    })

elif st.session_state.nav == "Compliance & scoring":
    view_header(
        "Compliance & Scoring",
        "Payment, filing, and reporting behavior"
    )

    st.metric("Average Compliance", f"{avg_compliance:.1f}%")

    st.dataframe(
        filtered_taxes[['entity_id', 'compliance_percent', 'outstanding_balance']]
        .sort_values("compliance_percent")
        .head(100),
        use_container_width=True
    )

    # ---------------- 1️⃣ TAX COMPLIANCE METRICS ----------------
    st.header("1️⃣ Tax Compliance Metrics")

    # Merge individual data with PIT taxes
    ind_tax = pd.merge(
        individuals,
        taxes[taxes['tax_type'] == 'PIT'],
        left_on='individual_id',
        right_on='entity_id'
    )

    # ---------------- SIDEBAR FILTERS ----------------
    st.sidebar.header("Filters / Slicers")
    region_filter = st.sidebar.multiselect(
        "Select States / Regions",
        options=sorted(individuals['state_of_residence'].unique()),
        default=sorted(individuals['state_of_residence'].unique())
    )
    industry_filter = st.sidebar.multiselect(
        "Select Company Industries",
        options=sorted(companies['industry_sector'].unique()),
        default=sorted(companies['industry_sector'].unique())
    )

    # Apply filters
    ind_tax_filtered = ind_tax[ind_tax['state_of_residence'].isin(region_filter)]
    companies_filtered = companies[companies['industry_sector'].isin(industry_filter)]

    # ---- A. Compliance by Geography ----
    st.subheader("A. Compliance by Geography")
    st.markdown("**Question:** Which states / LGAs / zones are most compliant? Where enforcement focus is needed?")
    geo_compliance = ind_tax_filtered.groupby('state_of_residence')['compliance_percent'].mean().reset_index()
    fig_geo = px.bar(
        geo_compliance,
        x='state_of_residence',
        y='compliance_percent',
        labels={"state_of_residence": "State", "compliance_percent": "Average Compliance %"},
        text_auto=True
    )
    st.plotly_chart(fig_geo, use_container_width=True)

    # ---- B. Compliance Distribution ----
    st.subheader("B. Compliance Distribution")
    st.markdown("**Question:** How many taxpayers are highly compliant, partially compliant, or non-compliant?")
    fig_hist = px.histogram(
        ind_tax_filtered,
        x='compliance_percent',
        nbins=10,
        labels={"compliance_percent": "Compliance %", "count": "Number of Taxpayers"}
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    # ---- C. Tax vs Income / Turnover Gap ----
    st.subheader("C. Tax vs Income / Turnover Gap")
    st.markdown("**Question:** Are taxpayers underreporting their income or companies underreporting revenue?")

    # Individuals
    fig_scatter_ind = px.scatter(
        ind_tax_filtered,
        x='declared_income',
        y='estimated_income',
        color='compliance_percent',
        hover_data=['full_name'],
        labels={"declared_income": "Declared Income (₦)", "estimated_income": "Estimated Income (₦)"}
    )
    st.plotly_chart(fig_scatter_ind, use_container_width=True)

    # Companies
    fig_scatter_comp = px.scatter(
        companies_filtered,
        x='turnover',
        y='cit_due',
        color='industry_sector',
        hover_data=['name'],
        labels={"turnover": "Turnover (₦)", "cit_due": "CIT Due (₦)"}
    )
    st.plotly_chart(fig_scatter_comp, use_container_width=True)


    # ---- D. Compliance Index Over Industry / Category ----
    st.subheader("D. Compliance Index by Industry / Occupation")
    st.markdown("**Question:** Which sectors or occupations are more compliant? Helps targeted audits.")
    ind_compliance_by_occ = ind_tax_filtered.groupby('occupation')['compliance_percent'].mean().reset_index()
    fig_occ = px.bar(
        ind_compliance_by_occ.sort_values('compliance_percent', ascending=False),
        x='occupation',
        y='compliance_percent',
        labels={"occupation": "Occupation", "compliance_percent": "Average Compliance %"}
    )
    st.plotly_chart(fig_occ, use_container_width=True)

    comp_compliance_by_industry = companies_filtered.groupby('industry_sector')['cit_due'].mean().reset_index()
    fig_industry = px.bar(
        comp_compliance_by_industry.sort_values('cit_due', ascending=False),
        x='industry_sector',
        y='cit_due',
        labels={"industry_sector": "Industry", "cit_due": "Average CIT Due (₦)"}
    )
    st.plotly_chart(fig_industry, use_container_width=True)


elif st.session_state.nav == "Suspicious activities":
    view_header(
        "Suspicious Activities",
        "AML-triggered entities requiring investigation"
    )

    st.metric("Total Alerts", total_alerts)

    st.dataframe(
        filtered_ind.head(100),
        use_container_width=True
    )

