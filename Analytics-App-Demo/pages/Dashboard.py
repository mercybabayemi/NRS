import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="NRS Analytics", layout="wide")

DATA_DIR = Path("~/NRS/Analytics-App-Demo/data")

@st.cache_data
def load_people():
    return pd.read_csv(DATA_DIR / "nigeria_people_dataset.csv", dtype={"bvn": str})

@st.cache_data
def load_risk():
    return pd.read_csv(DATA_DIR / "risk_flags_dataset.csv", dtype={"bvn": str})

st.title("NRS Analytics Demo")
st.caption("A simple view for stakeholders: start here, then drill into Individuals and Profiles.")

people = load_people()
risk = load_risk()

# Join to count flagged by state/LGA
df = people.merge(risk[["bvn", "status", "risk_score"]], on="bvn", how="left")
df["status"] = df["status"].fillna("Unknown")

total_people = len(df)
flagged = (df["status"].astype(str).str.lower() == "flagged").sum()
review = (df["status"].astype(str).str.lower() == "review").sum()
compliant = (df["status"].astype(str).str.lower() == "compliant").sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Individuals", f"{total_people:,}")
c2.metric("Flagged", f"{flagged:,}")
c3.metric("Review", f"{review:,}")
c4.metric("Compliant", f"{compliant:,}")

st.divider()

st.subheader("Where risks are concentrated")

state_view = (
    df.assign(is_flagged=df["status"].astype(str).str.lower().eq("flagged"))
      .groupby("state_of_residence", as_index=False)["is_flagged"].sum()
      .rename(columns={"is_flagged": "Flagged Count"})
      .sort_values("Flagged Count", ascending=False)
      .head(10)
)

st.bar_chart(state_view.set_index("state_of_residence")["Flagged Count"])

st.divider()

if st.button("Go to Individuals →", type="primary"):
    st.switch_page("Individuals Economic Activity.py")
