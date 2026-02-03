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

#--- 1b. Helpers ---
DATA_DIR = Path("data")

def require_file(filename: str) -> Path:
    path = DATA_DIR / filename
    if not path.exists():
        st.error(f"Missing file: {path}. Put **{filename}** inside your **data/** folder.")
        st.stop()
    return path

def title_case_label(s: str) -> str:
    return str(s).replace("_", " ").strip().title()

def month_label(dt_series: pd.Series) -> pd.Series:
    return pd.to_datetime(dt_series, errors="coerce").dt.to_period("M").astype(str)

def naira(x):
    try:
        if pd.isna(x):
            return "₦0"
        return f"₦{float(x):,.0f}"
    except Exception:
        return "₦0"

def fmt_ratio(x):
    if pd.isna(x):
        return "N/A"
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "N/A"


# --- 1C. Load Core Assets ---
@st.cache_data
def load_people():
    return pd.read_csv(require_file("nigeria_people_dataset.csv"), dtype={"bvn": str})

@st.cache_data
def load_demographics():
    return pd.read_csv(require_file("people_demographics_dataset.csv"), dtype={"bvn": str})

@st.cache_data
def load_risk_flags():
    df = pd.read_csv(require_file("risk_flags_dataset.csv"), dtype={"bvn": str})
    if "risk_score" in df.columns:
        df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
    df["status"] = df.get("status", "Unknown").fillna("Unknown")
    return df

@st.cache_data
def load_accounts():
    return pd.read_csv(require_file("accounts_dataset.csv"), dtype={"bvn": str, "account_id": str})

@st.cache_data
def load_transactions():
    upgraded = DATA_DIR / "transactions_dataset_upgraded.csv"
    normal = DATA_DIR / "transactions_dataset.csv"
    path = upgraded if upgraded.exists() else normal
    if not path.exists():
        st.error("Missing transactions file. Put transactions_dataset.csv (or transactions_dataset_upgraded.csv) in data/.")
        st.stop()

    df = pd.read_csv(path, dtype={"bvn": str, "account_id": str, "transaction_id": str})
    df["txn_datetime"] = pd.to_datetime(df.get("txn_datetime"), errors="coerce")
    df["amount"] = pd.to_numeric(df.get("amount"), errors="coerce").fillna(0.0)

    if "category_v2" in df.columns:
        df["category_use"] = df["category_v2"].fillna("Other Spending")
    elif "category" in df.columns:
        df["category_use"] = df["category"].fillna("Other Spending")
    else:
        df["category_use"] = "Other Spending"

    if "direction" not in df.columns:
        df["direction"] = "outflow"

    return df

@st.cache_data
def load_monthly():
    df = pd.read_csv(require_file("spend_metrics_monthly_dataset.csv"), dtype={"bvn": str})
    for c in ["total_inflows", "total_outflows", "spending_ratio", "net_cashflow"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

@st.cache_data
def load_employment():
    return pd.read_csv(require_file("employment_history_dataset.csv"), dtype={"bvn": str, "employer_id": str})

@st.cache_data
def load_employers():
    return pd.read_csv(require_file("employers_dataset.csv"), dtype={"employer_id": str})


people = load_people()
demo = load_demographics()
risk = load_risk_flags()
accounts = load_accounts()
txns = load_transactions()
monthly = load_monthly()
employment = load_employment()
employers = load_employers()

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
if "selected_bvn" not in st.session_state: st.session_state.selected_bvn = None



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
    if st.button("👥 Individuals", use_container_width=True):
        st.session_state.nav = "Individuals"
        st.session_state.selected_bvn = None
    # Optional: quick jump if already selected
    if st.session_state.selected_bvn and st.button("📌 Individual Economic Activity", use_container_width=True):
        st.session_state.nav = "Individuals_Economic_Activity"



# --- 5B. Render Functions for Views ---
# --- VIEW: INDIVIDUALS (ECONOMIC ACTIVITY DEEP DIVE) ---
def render_individuals_view():
    st.title("Individuals")

    directory = people.merge(risk[["bvn", "risk_score", "status"]], on="bvn", how="left")
    directory["status"] = directory["status"].fillna("Unknown")
    directory["risk_score"] = pd.to_numeric(directory["risk_score"], errors="coerce").fillna(-1)

    # Guard columns
    if "state_of_residence" not in directory.columns:
        st.error("Missing column state_of_residence in nigeria_people_dataset.csv")
        st.stop()
    if "local_government_area" not in directory.columns:
        st.error("Missing column local_government_area in nigeria_people_dataset.csv")
        st.stop()

    # Filters (in-page, since her sidebar already used for app-wide nav)
    with st.expander("Filters", expanded=True):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            states = ["All"] + sorted(directory["state_of_residence"].dropna().unique().tolist())
            selected_state = st.selectbox("State of residence", states, key="ind_state")

        subset = directory.copy()
        if selected_state != "All":
            subset = subset[subset["state_of_residence"] == selected_state].copy()

        with c2:
            lgas = ["All"] + sorted(subset["local_government_area"].dropna().unique().tolist())
            selected_lga = st.selectbox("LGA (tax area)", lgas, key="ind_lga")

        if selected_lga != "All":
            subset = subset[subset["local_government_area"] == selected_lga].copy()

        with c3:
            statuses = ["All"] + sorted(subset["status"].dropna().unique().tolist())
            selected_status = st.selectbox("Risk status", statuses, key="ind_status")

        if selected_status != "All":
            subset = subset[subset["status"] == selected_status].copy()

        with c4:
            search = st.text_input("Search (BVN)", "", key="ind_search").strip().lower()

        if search:
            subset = subset[subset["bvn"].str.contains(search, na=False)].copy()

    st.write(f"Showing **{len(subset):,}** individuals")

    # Sorting
    status_order = {"Flagged": 0, "Review": 1, "Compliant": 2, "Unknown": 3}
    subset["status_rank"] = subset["status"].map(status_order).fillna(99)
    subset = subset.sort_values(["status_rank", "risk_score"], ascending=[True, False])

    # Pagination
    st.divider()
    cA, cB, cC = st.columns([1, 1, 2])
    with cA:
        page_size = st.selectbox("Rows per page", [50, 100, 200, 500, 1000], index=2, key="ind_page_size")
    total_rows = len(subset)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)

    with cB:
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="ind_page")

    start = (page - 1) * page_size
    end = min(start + page_size, total_rows)
    page_df = subset.iloc[start:end].copy()

    st.caption(f"Page **{page}** of **{total_pages}** — rows **{start+1:,}–{end:,}**")

    # Display table
    show = page_df[["bvn", "state_of_residence", "local_government_area", "risk_score", "status"]].rename(
        columns={
            "bvn": "BVN",
            "state_of_residence": "State (Residence)",
            "local_government_area": "LGA (Residence)",
            "risk_score": "Risk Score",
            "status": "Risk Status",
        }
    )

    st.dataframe(show, use_container_width=True, height=520)

    st.write("### Open Individual")
    bvn_options = page_df["bvn"].dropna().astype(str).tolist()
    if not bvn_options:
        st.info("No BVN available in this filtered view.")
        return

    chosen_bvn = st.selectbox("Select BVN to view economic activity", bvn_options, key="ind_pick_bvn")
    if st.button("View Economic Activity →", use_container_width=True, key="ind_open_details"):
        st.session_state.selected_bvn = chosen_bvn
        st.session_state.nav = "Individuals_Economic_Activity"
        st.rerun()

# --- VIEW: INDIVIDUALS ECONOMIC ACTIVITY DEEP DIVE ---

def render_individual_econ_activity_view():
    bvn = st.session_state.selected_bvn

    if not bvn:
        st.warning("No individual selected.")
        if st.button("← Go to Individuals"):
            st.session_state.nav = "Individuals"
            st.rerun()
        return

    # Back button
    if st.button("← Back to Individuals"):
        st.session_state.nav = "Individuals"
        st.rerun()

    # Pull records
    p_df = people[people["bvn"] == str(bvn)]
    if p_df.empty:
        st.error("BVN not found in people dataset.")
        return
    p = p_df.iloc[0]

    d_df = demo[demo["bvn"] == str(bvn)]
    d = d_df.iloc[0] if not d_df.empty else None

    r_df = risk[risk["bvn"] == str(bvn)]
    r = r_df.iloc[0] if not r_df.empty else None

    name = "Unknown Name"
    emp_status = ""
    if d is not None:
        first = str(d.get("first_name", "")).strip()
        last = str(d.get("last_name", "")).strip()
        name = (f"{first} {last}").strip() or "Unknown Name"
        emp_status = str(d.get("employment_status", "")).strip()

    state_res = str(p.get("state_of_residence", "")).strip()
    lga_res = str(p.get("local_government_area", "")).strip()
    income_src = str(p.get("source_of_income", "")).strip()

    st.title("Individual Economic Activity")

    left, right = st.columns([2, 1], vertical_alignment="top")
    with left:
        st.subheader(name)
        st.caption(f"BVN: {bvn}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("State (Residence)", state_res or "—")
        c2.metric("LGA (Residence)", lga_res or "—")
        c3.metric("Source of Income", income_src or "—")
        c4.metric("Employment Status", emp_status or "—")

    with right:
        if r is not None:
            st.metric("Risk Status", str(r.get("status", "Unknown")))
            rs = r.get("risk_score", np.nan)
            st.metric("Risk Score", f"{float(rs):.1f}" if pd.notna(rs) else "N/A")
            reason = str(r.get("flag_reason", "")).strip()
            if reason:
                st.caption(reason)

    st.divider()

    tabs = st.tabs(["Overview", "Spending", "Transactions", "Accounts", "Employment"])

    # ---- Overview
    with tabs[0]:
        m = monthly[monthly["bvn"] == str(bvn)].copy()
        if m.empty:
            st.warning("No monthly metrics found for this BVN.")
        else:
            m = m.sort_values("year_month")
            total_in = float(m["total_inflows"].sum()) if "total_inflows" in m.columns else 0.0
            total_out = float(m["total_outflows"].sum()) if "total_outflows" in m.columns else 0.0
            avg_ratio = float(m["spending_ratio"].dropna().mean()) if "spending_ratio" in m.columns else np.nan

            k1, k2, k3 = st.columns(3)
            k1.metric("Total Inflows", naira(total_in))
            k2.metric("Total Outflows", naira(total_out))
            k3.metric("Avg Spending Ratio", fmt_ratio(avg_ratio))

            df_tot = pd.DataFrame({"Type": ["Inflows", "Outflows"], "Amount": [total_in, total_out]})
            fig = px.bar(df_tot, x="Type", y="Amount", text="Amount")
            fig.update_traces(texttemplate="₦%{text:,.0f}", textposition="outside")
            fig.update_layout(yaxis_title="Amount (₦)", xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    # ---- Spending
    with tabs[1]:
        t_all = txns[txns["bvn"] == str(bvn)].copy()
        t_all["txn_datetime"] = pd.to_datetime(t_all["txn_datetime"], errors="coerce")
        t_all = t_all.dropna(subset=["txn_datetime"]).copy()

        outflows = t_all[t_all["direction"].astype(str).str.lower() == "outflow"].copy()
        if outflows.empty:
            st.warning("No outflow/spending transactions found.")
        else:
            outflows["month"] = month_label(outflows["txn_datetime"])

            months = sorted(outflows["month"].dropna().unique().tolist())
            if not months:
                st.warning("No month information found.")
            else:
                cA, cB = st.columns(2)
                with cA:
                    start_m = st.selectbox("From month", months, index=0, key=f"econ_from_{bvn}")
                with cB:
                    end_m = st.selectbox("To month", months, index=len(months)-1, key=f"econ_to_{bvn}")
                outflows = outflows[(outflows["month"] >= start_m) & (outflows["month"] <= end_m)].copy()

            cat_totals = (outflows.groupby("category_use", as_index=False)["amount"].sum()
                          .sort_values("amount", ascending=False))
            cat_totals["Category"] = cat_totals["category_use"].apply(title_case_label)

            fig_pie = px.pie(cat_totals.head(10), names="Category", values="amount", hole=0.45)
            fig_pie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)

            fig_bar = px.bar(cat_totals.head(12), x="Category", y="amount", text="amount")
            fig_bar.update_traces(texttemplate="₦%{text:,.0f}", textposition="outside")
            fig_bar.update_layout(xaxis_title="", yaxis_title="Amount (₦)")
            st.plotly_chart(fig_bar, use_container_width=True)

    # ---- Transactions
    with tabs[2]:
        t_all = txns[txns["bvn"] == str(bvn)].copy()
        t_all["txn_datetime"] = pd.to_datetime(t_all["txn_datetime"], errors="coerce")
        t_all = t_all.dropna(subset=["txn_datetime"]).copy()
        if t_all.empty:
            st.warning("No transactions found.")
        else:
            t_all = t_all.sort_values("txn_datetime", ascending=False)
            t_show = t_all.copy()
            t_show["Date/Time"] = t_show["txn_datetime"].dt.strftime("%Y-%m-%d %H:%M")
            t_show["Amount (₦)"] = t_show["amount"].apply(naira)
            t_show["Category"] = t_show["category_use"].apply(title_case_label)
            t_show["Direction"] = t_show["direction"].astype(str).str.title()
            cols = [c for c in ["Date/Time", "Direction", "Amount (₦)", "Category", "channel", "merchant_name", "narration", "account_id"] if c in t_show.columns]
            st.dataframe(t_show[cols].head(400), use_container_width=True, height=560)

    # ---- Accounts
    with tabs[3]:
        a = accounts[accounts["bvn"] == str(bvn)].copy()
        if a.empty:
            st.warning("No accounts found.")
        else:
            st.dataframe(a, use_container_width=True)

    # ---- Employment
    with tabs[4]:
        e = employment[employment["bvn"] == str(bvn)].copy()
        if e.empty:
            st.info("No employment records found.")
        else:
            e = e.merge(employers, on="employer_id", how="left")
            if "start_date" in e.columns:
                e["start_date"] = pd.to_datetime(e["start_date"], errors="coerce").dt.date
            if "end_date" in e.columns:
                e["end_date"] = pd.to_datetime(e["end_date"].replace("", pd.NA), errors="coerce").dt.date
            st.dataframe(e, use_container_width=True)





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
    render_individuals_view()

elif st.session_state.nav == "Individuals_Economic_Activity":
    render_individual_econ_activity_view()


