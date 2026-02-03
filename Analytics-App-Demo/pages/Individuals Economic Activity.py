# app.py  (SINGLE-PAGE ROUTING)
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import random
from pathlib import Path

# -----------------------
# Page config
# -----------------------
st.set_page_config(page_title="Analytics App Demo", layout="wide")
DATA_DIR = Path("data")

# -----------------------
# Helpers
# -----------------------
def require_file(filename: str) -> Path:
    path = DATA_DIR / filename
    if not path.exists():
        st.error(f"Missing file: {path}. Put **{filename}** inside your **data/** folder.")
        st.stop()
    return path

def qp_get(key: str, default=None):
    v = st.query_params.get(key, default)
    if isinstance(v, list):
        v = v[0] if v else default
    return v

def route_to(view: str, bvn: str | None = None):
    st.query_params["view"] = view
    if bvn:
        st.query_params["bvn"] = bvn
    else:
        if "bvn" in st.query_params:
            del st.query_params["bvn"]
    st.rerun()

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

def safe_num(series, default=0.0):
    try:
        v = float(series)
        if np.isnan(v):
            return default
        return v
    except Exception:
        return default

# -----------------------
# Loaders (cached)
# -----------------------
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
    path = require_file("accounts_dataset.csv")
    return pd.read_csv(path, dtype={"bvn": str, "account_id": str})

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

    # Universal category field
    if "category_v2" in df.columns:
        df["category_use"] = df["category_v2"].fillna("Other Spending")
    elif "category" in df.columns:
        df["category_use"] = df["category"].fillna("Other Spending")
    else:
        df["category_use"] = "Other Spending"

    # Direction safety
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

# -----------------------
# Load all data once
# -----------------------
people = load_people()
demo = load_demographics()
risk = load_risk_flags()

accounts = load_accounts()
txns = load_transactions()
monthly = load_monthly()
employment = load_employment()
employers = load_employers()

# -----------------------
# ROUTER
# -----------------------
view = qp_get("view", "individuals")
bvn_qp = qp_get("bvn", None)

# =======================
# VIEW: Individuals
# =======================
def render_individuals():
    st.title("Individuals")

    # Merge directory (NO names)
    directory = (
        people.merge(demo[["bvn"]], on="bvn", how="left")
              .merge(risk[["bvn", "risk_score", "status"]], on="bvn", how="left")
    )
    directory["status"] = directory["status"].fillna("Unknown")
    directory["risk_score"] = pd.to_numeric(directory["risk_score"], errors="coerce").fillna(-1)

    st.sidebar.header("Filters")

    if "state_of_residence" not in directory.columns:
        st.error("Missing column state_of_residence in nigeria_people_dataset.csv")
        st.stop()
    if "local_government_area" not in directory.columns:
        st.error("Missing column local_government_area in nigeria_people_dataset.csv")
        st.stop()

    states = ["All"] + sorted(directory["state_of_residence"].dropna().unique().tolist())
    selected_state = st.sidebar.selectbox("State of residence", states, key="f_state")

    subset = directory.copy()
    if selected_state != "All":
        subset = subset[subset["state_of_residence"] == selected_state].copy()

    lgas = ["All"] + sorted(subset["local_government_area"].dropna().unique().tolist())
    selected_lga = st.sidebar.selectbox("LGA (tax area)", lgas, key="f_lga")

    if selected_lga != "All":
        subset = subset[subset["local_government_area"] == selected_lga].copy()

    statuses = ["All"] + sorted(subset["status"].dropna().unique().tolist())
    selected_status = st.sidebar.selectbox("Risk status", statuses, key="f_status")

    if selected_status != "All":
        subset = subset[subset["status"] == selected_status].copy()

    search = st.sidebar.text_input("Search (BVN)", "", key="f_search").strip().lower()
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
    page_size = st.sidebar.selectbox("Rows per page", [50, 100, 200, 500, 1000], index=2, key="pg_size")
    total_rows = len(subset)
    total_pages = max(1, (total_rows + page_size - 1) // page_size)
    page = st.sidebar.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1, key="pg_num")

    start = (page - 1) * page_size
    end = min(start + page_size, total_rows)
    page_df = subset.iloc[start:end].copy()

    st.caption(f"Page **{page}** of **{total_pages}** — showing rows **{start+1:,}–{end:,}**")

    # Clickable link column -> routes to individual_details
    page_df.insert(0, "Open", page_df["bvn"].apply(lambda x: f"/?view=individual_details&bvn={x}"))

    show_cols = ["Open", "bvn", "state_of_residence", "local_government_area", "risk_score", "status"]
    pretty = {
        "bvn": "BVN",
        "state_of_residence": "State (Residence)",
        "local_government_area": "LGA (Residence)",
        "risk_score": "Risk Score",
        "status": "Risk Status",
    }

    table = page_df[show_cols].rename(columns=pretty)

    st.data_editor(
        table,
        use_container_width=True,
        height=600,
        disabled=True,
        column_config={
            "Open": st.column_config.LinkColumn("View", display_text="View →", help="Open individual details")
        }
    )

# =======================
# VIEW: Individual Details
# =======================
def render_individual_details(bvn: str):
    st.title("Individual Details")

    # Back button (top)
    if st.button("← Back to Individuals"):
        route_to("individuals")

    # Pull person
    p_df = people[people["bvn"] == bvn]
    if p_df.empty:
        st.error("BVN not found in people dataset.")
        return
    p = p_df.iloc[0]

    d_df = demo[demo["bvn"] == bvn]
    d = d_df.iloc[0] if not d_df.empty else None

    r_df = risk[risk["bvn"] == bvn]
    r = r_df.iloc[0] if not r_df.empty else None

    state_res = str(p.get("state_of_residence", "")).strip()
    lga_res = str(p.get("local_government_area", "")).strip()
    income_src = str(p.get("source_of_income", "")).strip()

    name = "Unknown Name"
    emp_status = ""
    if d is not None:
        first = str(d.get("first_name", "")).strip()
        last = str(d.get("last_name", "")).strip()
        name = (f"{first} {last}").strip() or "Unknown Name"
        emp_status = str(d.get("employment_status", "")).strip()

    # Header
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Financial Overview", "Spending", "Transactions", "Accounts", "Employment"]
    )

    # -----------------------
    # Financial Overview (simple)
    # -----------------------
    with tab1:
        m = monthly[monthly["bvn"] == bvn].copy()
        if m.empty:
            st.warning("No monthly metrics found for this BVN.")
        else:
            m = m.sort_values("year_month")
            total_inflows = float(m["total_inflows"].sum()) if "total_inflows" in m.columns else 0.0
            total_outflows = float(m["total_outflows"].sum()) if "total_outflows" in m.columns else 0.0
            avg_ratio = float(m["spending_ratio"].dropna().mean()) if "spending_ratio" in m.columns else np.nan

            k1, k2, k3 = st.columns(3)
            k1.metric("Total Inflows", naira(total_inflows))
            k2.metric("Total Outflows", naira(total_outflows))
            k3.metric("Avg Spending Ratio", fmt_ratio(avg_ratio))

            st.markdown("### Inflows vs Outflows (Bar)")
            totals = pd.DataFrame({"Type": ["Inflows", "Outflows"], "Amount": [total_inflows, total_outflows]})
            fig = px.bar(totals, x="Type", y="Amount", text="Amount")
            fig.update_traces(texttemplate="₦%{text:,.0f}", textposition="outside")
            fig.update_layout(yaxis_title="Amount (₦)", xaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    # -----------------------
    # Spending (category bars + monthly stacked)
    # Uses synthetic quietly if sparse
    # -----------------------
    with tab2:
        # Base outflows
        t_all = txns[txns["bvn"] == bvn].copy()
        t_all["txn_datetime"] = pd.to_datetime(t_all["txn_datetime"], errors="coerce")
        t_all = t_all.dropna(subset=["txn_datetime"]).copy()

        out_real = t_all[t_all["direction"].astype(str).str.lower() == "outflow"].copy()
        if out_real.empty:
            st.warning("No outflow/spending transactions found for this BVN.")
        else:
            out_real["month"] = month_label(out_real["txn_datetime"])
            months = sorted(out_real["month"].dropna().unique().tolist())

            if not months:
                st.warning("No month information found.")
            else:
                cA, cB = st.columns(2)
                with cA:
                    start_month = st.selectbox("From month", months, index=0, key=f"sp_from_{bvn}")
                with cB:
                    end_month = st.selectbox("To month", months, index=len(months) - 1, key=f"sp_to_{bvn}")

                out_real = out_real[(out_real["month"] >= start_month) & (out_real["month"] <= end_month)].copy()

                acct_id = None
                if "account_id" in out_real.columns and not out_real["account_id"].dropna().empty:
                    acct_id = str(out_real["account_id"].dropna().iloc[0])

                # Quiet enrichment if too few categories/txns
                real_cat_count = out_real["category_use"].nunique(dropna=True)
                real_txn_count = len(out_real)

                use = out_real.copy()
                if real_cat_count < 6 or real_txn_count < 40:
                    syn_key = f"syn::{bvn}::{start_month}::{end_month}"
                    if syn_key not in st.session_state:
                        st.session_state[syn_key] = generate_synthetic_spend_for_bvn(bvn, start_month, end_month, acct_id)
                    syn_df = st.session_state[syn_key]
                    if not syn_df.empty:
                        use = pd.concat([use, syn_df], ignore_index=True)

                # KPIs
                total_spend = float(use["amount"].sum())
                k1, k2, k3 = st.columns(3)
                k1.metric("Total Spend (Selected Period)", naira(total_spend))
                k2.metric("Spend Transactions", f"{len(use):,}")
                k3.metric("Spend Categories", f"{use['category_use'].nunique():,}")

                # Total spend by category
                st.markdown("### Total Spend by Category")
                cat_totals = (use.groupby("category_use", as_index=False)["amount"].sum()
                               .sort_values("amount", ascending=False))
                cat_totals["Category"] = cat_totals["category_use"].apply(title_case_label)

                top_n = 12
                plot_df = cat_totals.head(top_n).copy()
                if len(cat_totals) > top_n:
                    other_sum = float(cat_totals.iloc[top_n:]["amount"].sum())
                    plot_df = pd.concat([plot_df, pd.DataFrame([{"category_use": "Other", "amount": other_sum, "Category": "Other"}])])

                fig_bar = px.bar(plot_df, x="Category", y="amount", text="amount")
                fig_bar.update_traces(texttemplate="₦%{text:,.0f}", textposition="outside")
                fig_bar.update_layout(xaxis_title="", yaxis_title="Amount (₦)")
                st.plotly_chart(fig_bar, use_container_width=True)

                tbl = cat_totals[["Category", "amount"]].copy()
                tbl["Total Spend"] = tbl["amount"].apply(naira)
                st.dataframe(tbl[["Category", "Total Spend"]], use_container_width=True, height=360)

                # Monthly spend by category (table + stacked)
                st.markdown("### Monthly Spend by Category")
                monthly_cat = use.groupby(["month", "category_use"], as_index=False)["amount"].sum()

                pivot = (monthly_cat.pivot_table(index="month", columns="category_use", values="amount",
                                                 aggfunc="sum", fill_value=0.0).sort_index())

                # only keep columns that exist
                top_cols = cat_totals["category_use"].head(8).tolist()
                existing_cols = [c for c in top_cols if c in pivot.columns]
                pivot_small = pivot[existing_cols] if existing_cols else pivot

                pivot_display = pivot_small.copy()
                pivot_display.columns = [title_case_label(c) for c in pivot_display.columns]
                pivot_display["Total"] = pivot_display.sum(axis=1)

                st.dataframe(pivot_display.applymap(naira), use_container_width=True, height=420)

                stack_df = monthly_cat.copy()
                if existing_cols:
                    stack_df = stack_df[stack_df["category_use"].isin(existing_cols)].copy()
                stack_df["Category"] = stack_df["category_use"].apply(title_case_label)

                fig_stack = px.bar(stack_df, x="month", y="amount", color="Category", barmode="stack")
                fig_stack.update_layout(xaxis_title="Month", yaxis_title="Amount (₦)")
                st.plotly_chart(fig_stack, use_container_width=True)

    # -----------------------
    # Transactions (simple list)
    # -----------------------
    with tab3:
        t_all = txns[txns["bvn"] == bvn].copy()
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

            cols = []
            for c in ["Date/Time", "Direction", "Amount (₦)", "Category", "channel", "merchant_name", "narration", "account_id"]:
                if c in t_show.columns:
                    cols.append(c)
            st.dataframe(t_show[cols].head(400), use_container_width=True, height=560)

    # -----------------------
    # Accounts
    # -----------------------
    with tab4:
        a = accounts[accounts["bvn"] == bvn].copy()
        if a.empty:
            st.warning("No accounts found.")
        else:
            rename = {
                "bank_name": "Bank",
                "masked_account_number": "Account (Masked)",
                "account_type": "Account Type",
                "currency": "Currency",
                "opened_date": "Opened Date",
                "status": "Account Status",
            }
            show = a.rename(columns=rename)
            st.dataframe(show, use_container_width=True)

    # -----------------------
    # Employment
    # -----------------------
    with tab5:
        e = employment[employment["bvn"] == bvn].copy()
        if e.empty:
            st.info("No employment records found.")
        else:
            e = e.merge(employers, on="employer_id", how="left")
            if "start_date" in e.columns:
                e["start_date"] = pd.to_datetime(e["start_date"], errors="coerce").dt.date
            if "end_date" in e.columns:
                e["end_date"] = pd.to_datetime(e["end_date"].replace("", pd.NA), errors="coerce").dt.date

            rename = {
                "employer_name": "Employer",
                "industry": "Industry",
                "job_title": "Job Title",
                "employment_type": "Employment Type",
                "start_date": "Start Date",
                "end_date": "End Date",
                "is_current": "Current?",
                "work_state": "Work State",
                "work_lga": "Work LGA",
            }
            show = e.rename(columns=rename)
            st.dataframe(show, use_container_width=True)

    st.divider()
    if st.button("← Back to Individuals", key="bottom_back"):
        route_to("individuals")


# -----------------------
# Dispatch
# -----------------------
if view == "individual_details":
    if not bvn_qp:
        render_individuals()
    else:
        render_individual_details(str(bvn_qp).strip())
else:
    render_individuals()
