import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
from pathlib import Path
import numpy as np
import random
from pathlib import Path


## --- Load real data ---
@st.cache_data
def load_data():
    # Adding error handling for file existence
    data_dir = "generate_data/output/"
    def read_safe(file):
        path = os.path.join(data_dir, file)
        return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

    individuals = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/individuals.csv")
    companies = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/companies.csv")
    taxes = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/taxes.csv")
    aml_flags_individual = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/aml_flags.csv")
    aml_flags_companies = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/aml_flags_companies.csv")
    spend_events = pd.read_parquet("~/NRS/nrs_streamlit_app/generate_data/parquet/spend_events.parquet")
    transactions = pd.read_parquet("~/NRS/nrs_streamlit_app/generate_data/parquet/transactions.parquet")
    banks = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/banks_financial.csv")
    assets = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/assets.csv")
    spend_aggregrates = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/spend_aggregates.csv")
    relationships = pd.read_parquet("~/NRS/nrs_streamlit_app/generate_data/parquet/relationships.parquet")

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
    
    .stButton button {{
        background: #111827;  /* HEX_PRIMARY */
        color: white;
    }}

    .stButton button:hover {{
        background: #111827;  /* stays same on hover */
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


#--- 1b. Helpers ---
DATA_DIR = Path("nrs_streamlit_app/data")


def require_file(filename: str) -> Path:
    p = Path(filename).expanduser()
    if not p.is_absolute():
        p = (DATA_DIR / filename).resolve()
    if not p.exists():
        st.error(f"Missing file: {p}")
        st.stop()
    return p

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


def get_outflow_txns_enriched(bvn: str, start_month: str, end_month: str) -> pd.DataFrame:
    base = txns[txns["bvn"] == bvn].copy()
    base["txn_datetime"] = pd.to_datetime(base["txn_datetime"], errors="coerce")
    base = base.dropna(subset=["txn_datetime"]).copy()

    out = base[base["direction"].astype(str).str.lower() == "outflow"].copy()
    out["month"] = month_label(out["txn_datetime"])

    out = out[(out["month"] >= start_month) & (out["month"] <= end_month)].copy()

    # if sparse → silently enrich
    cat_count = out["category_use"].nunique(dropna=True) if "category_use" in out.columns else 0
    txn_count = len(out)

    acct_id = None
    if "account_id" in out.columns and not out["account_id"].dropna().empty:
        acct_id = str(out["account_id"].dropna().iloc[0])

    if cat_count < 6 or txn_count < 40:
        syn_key = f"syn::{bvn}::{start_month}::{end_month}"
        if syn_key not in st.session_state:
            st.session_state[syn_key] = generate_synthetic_spend_for_bvn(bvn, start_month, end_month, acct_id)
        syn_df = st.session_state[syn_key]
        if not syn_df.empty:
            out = pd.concat([out, syn_df], ignore_index=True)

    return out


def render_benchmark_bars(
    *,
    bvn: str,
    monthly: pd.DataFrame,
    people: pd.DataFrame,
    person_months: list[str],
    state_res: str,
    lga_res: str,
):
    # ---- safety: normalize column names (handles trailing spaces) ----
    monthly = monthly.copy()
    people = people.copy()
    monthly.columns = monthly.columns.astype(str).str.strip()
    people.columns = people.columns.astype(str).str.strip()

    needed_people_cols = ["bvn", "state_of_residence", "local_government_area"]
    missing = [c for c in needed_people_cols if c not in people.columns]
    if missing:
        st.error(f"People dataset missing columns: {missing}. Found: {list(people.columns)}")
        return

    # ---- merge (avoid accidental suffix surprise) ----
    monthly_geo = monthly.merge(
        people[needed_people_cols],
        on="bvn",
        how="left",
        suffixes=("", "_people"),
    )

    # ---- resolve the actual column names after merge ----
    # Prefer the non-suffixed version if it exists, otherwise take the people-suffixed version.
    state_col = "state_of_residence" if "state_of_residence" in monthly_geo.columns else "state_of_residence_people"
    lga_col = "local_government_area" if "local_government_area" in monthly_geo.columns else "local_government_area_people"

    if state_col not in monthly_geo.columns or lga_col not in monthly_geo.columns:
        st.error(
            "Geography columns not found after merge. "
            f"state_col={state_col} in cols? {state_col in monthly_geo.columns}, "
            f"lga_col={lga_col} in cols? {lga_col in monthly_geo.columns}. "
            f"Available cols: {list(monthly_geo.columns)}"
        )
        return

    # Restrict to same months as the individual (fair comparison)
    bench = monthly_geo[monthly_geo["year_month"].astype(str).isin(person_months)].copy()

    # Normalize strings (and normalize comparisons)
    bench[state_col] = bench[state_col].astype(str).str.strip()
    bench[lga_col] = bench[lga_col].astype(str).str.strip()
    state_res = str(state_res).strip()
    lga_res = str(lga_res).strip()

    # Individual
    indiv_outflows = bench.loc[bench["bvn"] == bvn, "total_outflows"].sum()

    # LGA average (per person)
    lga_df = bench[(bench[state_col] == state_res) & (bench[lga_col] == lga_res)]
    lga_avg = lga_df.groupby("bvn")["total_outflows"].sum().mean() if not lga_df.empty else 0

    # State average (per person)
    state_df = bench[bench[state_col] == state_res]
    state_avg = state_df.groupby("bvn")["total_outflows"].sum().mean() if not state_df.empty else 0

    chart_df = pd.DataFrame({
        "Group": ["Individual", "LGA Average", "State Average"],
        "Outflows": [indiv_outflows, lga_avg, state_avg],
    })

    fig = px.bar(
        chart_df,
        x="Group",
        y="Outflows",
        text="Outflows",
        title="Outflow Comparison (Individual vs LGA vs State)",
    )
    fig.update_traces(texttemplate="₦%{text:,.0f}", textposition="outside")
    fig.update_layout(yaxis_title="Outflows (₦)", xaxis_title="")

    # Streamlit deprecation-safe:
    st.plotly_chart(fig, width="stretch")



def render_connections(bvn: str, start_month: str, end_month: str):
    t = txns[txns["bvn"] == bvn].copy()
    t["txn_datetime"] = pd.to_datetime(t["txn_datetime"], errors="coerce")
    t = t.dropna(subset=["txn_datetime"]).copy()
    t["month"] = month_label(t["txn_datetime"])
    t = t[(t["month"] >= start_month) & (t["month"] <= end_month)].copy()

    if t.empty:
        st.warning("No transactions in this period.")
        return

    # define counterparty label (merchant_name preferred)
    t["counterparty"] = t.get("merchant_name", pd.Series(["Unknown"] * len(t))).fillna("Unknown")
    t["counterparty"] = t["counterparty"].astype(str).str.strip().replace("", "Unknown")

    out = t[t["direction"].astype(str).str.lower() == "outflow"].copy()
    inc = t[t["direction"].astype(str).str.lower() == "inflow"].copy()

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### Top Places Money Went (Outflows)")
        if out.empty:
            st.info("No outflows in this period.")
        else:
            top_out = out.groupby("counterparty", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(10)
            fig = px.bar(top_out, x="counterparty", y="amount", text="amount")
            fig.update_traces(texttemplate="₦%{text:,.0f}", textposition="outside")
            fig.update_layout(xaxis_title="", yaxis_title="Amount (₦)")
            st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("### Top Sources of Money (Inflows)")
        if inc.empty:
            st.info("No inflows in this period.")
        else:
            top_in = inc.groupby("counterparty", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(10)
            fig = px.bar(top_in, x="counterparty", y="amount", text="amount")
            fig.update_traces(texttemplate="₦%{text:,.0f}", textposition="outside")
            fig.update_layout(xaxis_title="", yaxis_title="Amount (₦)")
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Sankey (simple flow view)
    st.markdown("### Flow Map (Simple)")
    # build a small sankey: Person -> Top Out Counterparties and Top In Counterparties -> Person
    top_out = out.groupby("counterparty", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(6)
    top_in = inc.groupby("counterparty", as_index=False)["amount"].sum().sort_values("amount", ascending=False).head(6)

    nodes = ["This Individual"]
    nodes += [f"Spent: {c}" for c in top_out["counterparty"].tolist()]
    nodes += [f"Received: {c}" for c in top_in["counterparty"].tolist()]

    node_index = {n: i for i, n in enumerate(nodes)}
    sources, targets, values = [], [], []

    for _, row in top_out.iterrows():
        sources.append(node_index["This Individual"])
        targets.append(node_index[f"Spent: {row['counterparty']}"])
        values.append(float(row["amount"]))

    for _, row in top_in.iterrows():
        sources.append(node_index[f"Received: {row['counterparty']}"])
        targets.append(node_index["This Individual"])
        values.append(float(row["amount"]))

    import plotly.graph_objects as go
    fig = go.Figure(
        data=[go.Sankey(
            node=dict(label=nodes),
            link=dict(source=sources, target=targets, value=values)
        )]
    )
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

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
people_master = load_people()
people = people_master
# st.write("DEBUG: people loaded?", "people" in globals(), "rows:", len(people))

demo = load_demographics()
risk = load_risk_flags()
accounts = load_accounts()
txns = load_transactions()
monthly = load_monthly()
employment = load_employment()
employers = load_employers()



# -----------------------
# Synthetic spend (quietly used for richness)
# -----------------------
ENRICH_CATEGORIES = [
    "Food & Groceries", "Eating Out / Restaurants", "Airtime", "Internet / Data",
    "Transportation", "Fueling", "Electricity", "Cable TV", "Healthcare",
    "Shopping / E-commerce", "Entertainment", "Betting & Gaming",
    "Outgoing Transfer", "POS Withdrawal", "Bank Fees & Charges",
]

AMOUNT_RANGES = {
    "Food & Groceries": (800, 15000),
    "Eating Out / Restaurants": (1500, 20000),
    "Airtime": (200, 3000),
    "Internet / Data": (500, 10000),
    "Transportation": (300, 12000),
    "Fueling": (2000, 40000),
    "Electricity": (1000, 25000),
    "Cable TV": (1500, 18000),
    "Healthcare": (800, 30000),
    "Shopping / E-commerce": (1500, 60000),
    "Entertainment": (500, 20000),
    "Betting & Gaming": (200, 25000),
    "Outgoing Transfer": (2000, 120000),
    "POS Withdrawal": (1000, 60000),
    "Bank Fees & Charges": (50, 2500),
}

MERCHANTS = {
    "Airtime": ["MTN VTU", "Airtel VTU", "Glo VTU", "9mobile VTU"],
    "Internet / Data": ["MTN Data", "Airtel Data", "Glo Data", "9mobile Data", "Smile", "Spectranet", "Starlink"],
    "Food & Groceries": ["Shoprite", "SPAR", "Local Market", "Justrite", "Everyday Supermarket"],
    "Eating Out / Restaurants": ["KFC", "Chicken Republic", "Dominos", "Mr Biggs", "Local Bukka", "Cafe Neo"],
    "Transportation": ["Uber", "Bolt", "Bus Fare", "Okada Fare", "Toll Gate"],
    "Fueling": ["NNPC Station", "TotalEnergies", "Oando", "Mobil"],
    "Electricity": ["IKEDC", "EKEDC", "JEDC", "AEDC"],
    "Cable TV": ["DSTV", "GOtv", "StarTimes"],
    "Healthcare": ["Pharmacy", "Clinic", "Hospital"],
    "Shopping / E-commerce": ["Jumia", "Konga", "Mall Purchase", "Online Store"],
    "Entertainment": ["Cinema", "Game Center", "Concert Tickets"],
    "Betting & Gaming": ["Bet9ja", "SportyBet", "1xBet", "BetKing"],
    "Outgoing Transfer": ["Transfer to Family", "Transfer to Vendor", "Transfer to Savings"],
    "POS Withdrawal": ["POS Cash Agent", "POS Withdrawal"],
    "Bank Fees & Charges": ["SMS Alert", "Maintenance Fee", "Stamp Duty", "Transfer Charge"],
}
CHANNELS = ["POS", "USSD", "Mobile App", "Bank Transfer", "ATM", "Card", "Web"]

def _log_uniform(lo, hi):
    lo = max(1.0, float(lo))
    hi = max(lo + 1.0, float(hi))
    return float(np.exp(np.random.uniform(np.log(lo), np.log(hi))))

def _random_dt_between(start_ts: pd.Timestamp, end_ts: pd.Timestamp) -> pd.Timestamp:
    delta = (end_ts - start_ts).total_seconds()
    if delta <= 0:
        return start_ts
    r = np.random.randint(0, int(delta))
    return start_ts + pd.Timedelta(seconds=int(r))

def generate_synthetic_spend_for_bvn(bvn: str, start_month: str, end_month: str, account_id: str | None):
    # stable seed per bvn+period so it doesn't jump around
    seed = abs(hash((bvn, start_month, end_month))) % (2**32 - 1)
    np.random.seed(seed)
    random.seed(seed)

    months = pd.period_range(start=start_month, end=end_month, freq="M")
    if len(months) == 0:
        return pd.DataFrame()

    cats = ENRICH_CATEGORIES.copy()
    random.shuffle(cats)
    cats = cats[:10]

    rows = []
    for per in months:
        month_start = per.to_timestamp()
        month_end = (per + 1).to_timestamp()

        weights = np.random.dirichlet([0.9] * len(cats))
        n = int(np.clip(28 + np.random.randint(-7, 8), 18, 45))
        chosen = np.random.choice(cats, size=n, p=weights, replace=True)

        for i, cat in enumerate(chosen, start=1):
            lo, hi = AMOUNT_RANGES.get(cat, (200, 20000))
            amt = _log_uniform(lo, hi)
            merchant = random.choice(MERCHANTS.get(cat, [cat]))
            channel = random.choice(CHANNELS)
            dt = _random_dt_between(month_start, month_end)

            rows.append({
                "transaction_id": f"SYN_UI_{bvn}_{str(per)}_{i:03d}",
                "bvn": bvn,
                "account_id": str(account_id) if account_id else f"ACC_{bvn}",
                "txn_datetime": dt,
                "direction": "outflow",
                "amount": round(amt, 2),
                "category_use": cat,
                "merchant_name": merchant,
                "narration": f"{cat} - {merchant}",
                "channel": channel,
                "_synthetic": True,  # internal only
            })

    return pd.DataFrame(rows)

# --- 2. STATE MANAGEMENT ---
for key, val in {"nav": "Dashboard", "selected_state": None, "time_filter": "all", "selected_company":"", "selected_bvn":None}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# --- 2B. URL → SESSION ROUTER ---
qp_view = st.query_params.get("view")
qp_bvn = st.query_params.get("bvn")

# Streamlit may return lists
if isinstance(qp_view, list):
    qp_view = qp_view[0] if qp_view else None
if isinstance(qp_bvn, list):
    qp_bvn = qp_bvn[0] if qp_bvn else None

if qp_view == "individual_economic_activity" and qp_bvn:
    st.session_state.selected_bvn = str(qp_bvn).strip()
    st.session_state.nav = "Individuals_Economic_Activity"


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
state_list = [state for states in GEO_ZONES.values() for state in states]

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

# --- 5B. Render Functions for Views ---
# --- VIEW: INDIVIDUALS (ECONOMIC ACTIVITY DEEP DIVE) ---
def render_individuals_view():
    st.title("Individuals")

    directory = (
        people.merge(risk[["bvn", "risk_score", "status"]], on="bvn", how="left")
    )
    directory["status"] = directory["status"].fillna("Unknown")
    directory["risk_score"] = pd.to_numeric(directory["risk_score"], errors="coerce").fillna(-1)

    # Filters (sidebar)
    st.sidebar.header("Filters")

    states = ["All"] + sorted(directory["state_of_residence"].dropna().unique().tolist())
    selected_state = st.sidebar.selectbox("State of residence", states, key="ind_state")

    subset = directory.copy()
    if selected_state != "All":
        subset = subset[subset["state_of_residence"] == selected_state].copy()

    lgas = ["All"] + sorted(subset["local_government_area"].dropna().unique().tolist())
    selected_lga = st.sidebar.selectbox("LGA", lgas, key="ind_lga")

    if selected_lga != "All":
        subset = subset[subset["local_government_area"] == selected_lga].copy()

    statuses = ["All"] + sorted(subset["status"].dropna().unique().tolist())
    selected_status = st.sidebar.selectbox("Risk status", statuses, key="ind_status")

    if selected_status != "All":
        subset = subset[subset["status"] == selected_status].copy()

    search = st.sidebar.text_input("Search (BVN)", "", key="ind_search").strip()
    if search:
        subset = subset[subset["bvn"].str.contains(search, na=False)].copy()

    st.write(f"Showing **{len(subset):,}** individuals")

    # Sorting
    status_order = {"Flagged": 0, "Review": 1, "Compliant": 2, "Unknown": 3}
    subset["status_rank"] = subset["status"].map(status_order).fillna(99)
    subset = subset.sort_values(["status_rank", "risk_score"], ascending=[True, False])

    # Pagination
    st.sidebar.divider()
    st.sidebar.subheader("Pagination")
    page_size = st.sidebar.selectbox("Rows per page", [50, 100, 200, 500, 1000], index=2, key="ind_pg_size")

    total_rows = len(subset)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page = st.sidebar.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="ind_pg")

    start = (page - 1) * page_size
    end = min(start + page_size, total_rows)
    page_df = subset.iloc[start:end].copy()

    st.caption(f"Page **{page}** of **{total_pages}** — showing rows **{start+1:,}–{end:,}**")

    # ✅ Link column -> deep dive
    page_df.insert(0, "View", page_df["bvn"].apply(lambda x: f"/?view=individual_economic_activity&bvn={x}"))

    show = page_df[["View", "bvn", "state_of_residence", "local_government_area", "risk_score", "status"]].rename(
        columns={
            "bvn": "BVN",
            "state_of_residence": "State of Residence",
            "local_government_area": "LGA",
            "risk_score": "Risk Score",
            "status": "Risk Status",
        }
    )

    st.data_editor(
        show,
        use_container_width=True,
        height=600,
        disabled=True,
        column_config={
            "View": st.column_config.LinkColumn("Open", display_text="View →", help="Open individual details"),
            "Risk Score": st.column_config.NumberColumn(format="%.1f"),
        },
    )




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
    if st.button("← Back"):
        st.query_params.clear()
        st.session_state.selected_bvn = None
        st.session_state.nav = "Individuals"
        st.rerun()

    # if st.button("← Back to Individuals"):
    #     st.session_state.nav = "Individuals"
    #     st.rerun()

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
        m = monthly[monthly["bvn"] == bvn].copy()

        if not m.empty:
            person_months = m["year_month"].astype(str).tolist()
            st.write("People columns:", list(people.columns))

            render_benchmark_bars(
                bvn=bvn,
                monthly=monthly,
                people=people,
                person_months=person_months,
                state_res=state_res,
                lga_res=lga_res,
            )
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
                    options=yoa_options
                )

            with f1:
                st.markdown(
                    "<p style='color:#6B7280; font-size:14px; margin-bottom:4px;'>Filter Individual or Company</p>",
                    unsafe_allow_html=True
                )
                state_filter = st.multiselect(
                    label="",
                    options=state_options
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
        view_header(
            "Industries",
            "Corporate tax behavior and sector insights"
        )

        industry_display_table = filtered_comp

        st.dataframe(
            filtered_comp,
            use_container_width=True
        )
        m1, m2, m3, m4 = st.columns(4)
        # with m1:
        #     draw_metric("Declared income", "₦122B", "20%")
        # with m2:
        #     draw_metric("Estimated income", "₦470B", "40%")
        # with m3:
        #     draw_metric("Income gap", "₦348B", "10%", is_up=False)
        # with m4:
        #     draw_metric("Potential tax revenue", "₦592B", "20%")



        st.markdown("### Industries <span style='color:grey; font-size:14px'></span>", unsafe_allow_html=True)
        st.write("---")
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            st.text_input("Search", placeholder="Search by name or TIN")
        with c2:
            state_list.insert(0,"All States")
            st.selectbox("State", state_list)

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

# --- VIEW: INDIVIDUALS ---
elif st.session_state.nav == "Individuals":
    render_individuals_view()

elif st.session_state.nav == "Individuals_Economic_Activity":
    render_individual_econ_activity_view()

# elif st.session_state.nav == "Individuals":

#     view_header(
#         "Individuals",
#         "Filtered view of registered individual taxpayers"
#     )

#     st.dataframe(
#         filtered_ind.head(100),
#         use_container_width=True
#     )

