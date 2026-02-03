import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Individuals", layout="wide")

DATA_DIR = Path("data")

@st.cache_data
def load_people():
    return pd.read_csv(DATA_DIR / "nigeria_people_dataset.csv", dtype={"bvn": str})

@st.cache_data
def load_risk_flags():
    df = pd.read_csv(DATA_DIR / "risk_flags_dataset.csv", dtype={"bvn": str})
    df["risk_score"] = pd.to_numeric(df["risk_score"], errors="coerce")
    return df

people = load_people()
risk = load_risk_flags()

# Merge (NO names)
directory = (
    people.merge(risk[["bvn", "assessment_year", "risk_score", "status"]], on="bvn", how="left")
)

directory["status"] = directory["status"].fillna("Unknown")
directory["risk_score"] = directory["risk_score"].fillna(-1)

st.title("Individuals")

# ---------- Sidebar filters ----------
st.sidebar.header("Filters")

states = ["All"] + sorted(directory["state_of_residence"].dropna().unique().tolist())
selected_state = st.sidebar.selectbox("State of residence", states)

subset = directory.copy()
if selected_state != "All":
    subset = subset[subset["state_of_residence"] == selected_state].copy()

lgas = ["All"] + sorted(subset["local_government_area"].dropna().unique().tolist())
selected_lga = st.sidebar.selectbox("LGA (tax area)", lgas)

if selected_lga != "All":
    subset = subset[subset["local_government_area"] == selected_lga].copy()

statuses = ["All"] + sorted(subset["status"].dropna().unique().tolist())
selected_status = st.sidebar.selectbox("Risk status", statuses)

if selected_status != "All":
    subset = subset[subset["status"] == selected_status].copy()

search = st.sidebar.text_input("Search (BVN)", "").strip().lower()
if search:
    subset = subset[subset["bvn"].str.contains(search, na=False)].copy()

st.write(f"Showing **{len(subset):,}** individuals")

# ---------- Sorting ----------
status_order = {"Flagged": 0, "Review": 1, "Compliant": 2, "Unknown": 3}
subset["status_rank"] = subset["status"].map(status_order).fillna(99)

subset_sorted = subset.sort_values(["status_rank", "risk_score"], ascending=[True, False])

# ---------- Pagination ----------
st.sidebar.divider()
st.sidebar.subheader("Pagination")

page_size = st.sidebar.selectbox("Rows per page", [50, 100, 200, 500, 1000], index=3)
total_rows = len(subset_sorted)
total_pages = max(1, (total_rows + page_size - 1) // page_size)

page = st.sidebar.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)

start = (page - 1) * page_size
end = min(start + page_size, total_rows)

page_df = subset_sorted.iloc[start:end].copy()

st.caption(f"Page **{page}** of **{total_pages}** — showing rows **{start+1:,}–{end:,}**")

# ---------- Link to Profile ----------
# IMPORTANT: This assumes your file is pages/Profile.py -> route /Profile
page_df.insert(0, "Open Profile", page_df["bvn"].apply(lambda x: f"/Profile?bvn={x}"))

# ---------- Display columns (pretty names) ----------
show_df = page_df[[
    "Open Profile",
    "bvn",
    "state_of_residence",
    "local_government_area",
    "risk_score",
    "status",
]].rename(columns={
    "bvn": "BVN",
    "state_of_residence": "State of Residence",
    "local_government_area": "LGA",
    "risk_score": "Risk Score",
    "status": "Risk Status",
})

st.data_editor(
    show_df,
    use_container_width=True,
    height=560,
    disabled=True,
    column_config={
        "Open Profile": st.column_config.LinkColumn(
            "Open",
            help="Open profile",
            display_text="View →"
        ),
        "Risk Score": st.column_config.NumberColumn(
            format="%.1f",
            help="Higher score = higher risk"
        ),
    }
)
