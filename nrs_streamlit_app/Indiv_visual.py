import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ---------------- LOAD DATA ----------------
@st.cache_data
def load_data():
    individuals = pd.read_csv("generate_data/output/individuals.csv")
    companies = pd.read_csv("generate_data/output/companies.csv")
    taxes = pd.read_csv("generate_data/output/taxes.csv")
    aml_flags_individual = pd.read_csv("generate_data/output/aml_flags.csv")
    aml_flags_companies = pd.read_csv("generate_data/output/aml_flags_companies.csv")
    spend_events = pd.read_csv("generate_data/output/spend_events.csv")
    transactions = pd.read_csv("generate_data/output/transactions.csv")
    banks = pd.read_csv("generate_data/output/banks_financial.csv")
    assets = pd.read_csv("generate_data/output/assets.csv")
    spend_aggregrates = pd.read_csv("generate_data/output/spend_aggregates.csv")
    relationships = pd.read_csv("generate_data/output/relationships.csv")
    return (individuals, companies, taxes, aml_flags_individual,
            aml_flags_companies, spend_events, transactions,
            banks, assets, spend_aggregrates, relationships)

(individuals, companies, taxes, aml_flags,
 aml_flags_companies, spend_events, transactions,
 banks, assets, spend_aggregrates, relationships) = load_data()

# ---------------- PAGE LAYOUT ----------------
st.set_page_config(page_title="Nigeria Tax Compliance & Economic Dashboard", layout="wide")
st.title("🇳🇬 NRS 2026 – Tax Compliance, Risk & Economic Activity Dashboard")
st.markdown("""
Enhanced dashboard: **Compliance Index**, **Revenue Leakage**, **HNI Asset-Gaps**, **AML Risk Weighting**.
""")

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

# ---------------- DATA PREP & METRICS ----------------
# Merge individual PIT taxes
ind_tax = pd.merge(
    individuals,
    taxes[taxes['tax_type']=='PIT'],
    left_on='individual_id',
    right_on='entity_id'
)
ind_tax_filtered = ind_tax[ind_tax['state_of_residence'].isin(region_filter)]
companies_filtered = companies[companies['industry_sector'].isin(industry_filter)]

# ---- Individual Compliance Index ----
ind_tax_filtered['payment_ratio'] = ind_tax_filtered.apply(
    lambda row: min(row['paid_amount']/row['calculated_amount'],1) if row['calculated_amount']>0 else 1, axis=1)
ind_tax_filtered['filing_ratio'] = 1  # Assume filed if in taxes.csv
ind_tax_filtered['reporting_accuracy'] = ind_tax_filtered.apply(
    lambda row: min(row['declared_income']/row['estimated_income'],1) if row['estimated_income']>0 else 1, axis=1)
ind_tax_filtered['compliance_index'] = (
    0.6*ind_tax_filtered['payment_ratio'] +
    0.3*ind_tax_filtered['filing_ratio'] +
    0.1*ind_tax_filtered['reporting_accuracy']
)*100
# AML risk adjustment (+20 penalty)
ind_tax_filtered['compliance_index_adj'] = ind_tax_filtered['compliance_index'] - (
    ind_tax_filtered['individual_id'].isin(aml_flags['entity_id'])*20)
ind_tax_filtered['compliance_index_adj'] = ind_tax_filtered['compliance_index_adj'].clip(0,100)

# ---- Revenue Leakage ----
ind_tax_filtered['revenue_leakage'] = ind_tax_filtered['estimated_income'] - ind_tax_filtered['declared_income']

# ---- HNI Asset Gap ----
assets_grouped = assets.groupby('owner_id')['estimated_value'].sum().reset_index()
assets_grouped.rename(columns={'owner_id':'individual_id','estimated_value':'total_assets'}, inplace=True)
ind_tax_filtered = pd.merge(ind_tax_filtered, assets_grouped, on='individual_id', how='left')
ind_tax_filtered['total_assets'] = ind_tax_filtered['total_assets'].fillna(0)
ind_tax_filtered['hni_asset_gap_ratio'] = ind_tax_filtered['total_assets']/ind_tax_filtered['estimated_income']

# ---- Company Compliance Index ----
companies_filtered['cit_ratio'] = companies_filtered['cit_due']/companies_filtered['turnover']
companies_filtered['vat_ratio'] = companies_filtered['vat_paid']/companies_filtered['turnover']
companies_filtered['dev_levy_ratio'] = companies_filtered['development_levy_due']/companies_filtered['turnover']
companies_filtered['compliance_index'] = (0.4*companies_filtered['cit_ratio'] +
                                         0.3*companies_filtered['vat_ratio'] +
                                         0.3*companies_filtered['dev_levy_ratio'])*100
companies_filtered['compliance_index_adj'] = companies_filtered['compliance_index'] - (
    companies_filtered['company_id'].isin(aml_flags_companies['entity_id'])*20)
companies_filtered['compliance_index_adj'] = companies_filtered['compliance_index_adj'].clip(0,100)

companies_filtered['revenue_leakage'] = companies_filtered['turnover'] - (
    companies_filtered['cit_due'] + companies_filtered['vat_paid'] + companies_filtered['development_levy_due'])

# ---------------- VISUALIZATIONS ----------------
st.header("1️⃣ Individual Tax Compliance & Revenue Leakage")

# Compliance Index Distribution
fig_comp_dist = px.histogram(
    ind_tax_filtered, x='compliance_index_adj', nbins=10,
    labels={'compliance_index_adj':'Compliance Index (Adj)','count':'Number of Taxpayers'},
    color=pd.cut(ind_tax_filtered['revenue_leakage'], bins=5),
    title="Individual Compliance Index Distribution & Revenue Leakage"
)
st.plotly_chart(fig_comp_dist, use_container_width=True)

# Revenue Leakage by HNI
fig_hni_leak = px.scatter(
    ind_tax_filtered, x='estimated_income', y='revenue_leakage',
    color='hni_badge', hover_data=['full_name'],
    size='total_assets',
    labels={"estimated_income":"Estimated Income (₦)",
            "revenue_leakage":"Revenue Leakage (₦)",
            "hni_badge":"HNI"},
    title="Revenue Leakage vs Estimated Income (HNI highlighted, size = assets)"
)
st.plotly_chart(fig_hni_leak, use_container_width=True)

# ---------------- Company Compliance ----------------
st.header("2️⃣ Company Tax Compliance & Revenue Leakage")

fig_comp_industry = px.bar(
    companies_filtered.sort_values('compliance_index_adj',ascending=False),
    x='industry_sector', y='compliance_index_adj', color='revenue_leakage',
    labels={"industry_sector":"Industry","compliance_index_adj":"Compliance Index (Adj)","revenue_leakage":"Revenue Leakage (₦)"},
    title="Company Compliance Index by Industry & Revenue Leakage"
)
st.plotly_chart(fig_comp_industry, use_container_width=True)

# Scatter: Turnover vs Revenue Leakage
fig_comp_scatter = px.scatter(
    companies_filtered, x='turnover', y='revenue_leakage',
    size='staff_strength', color='industry_sector',
    hover_data=['name'],
    labels={"turnover":"Turnover (₦)","revenue_leakage":"Revenue Leakage (₦)"},
    title="Company Revenue Leakage vs Turnover (Bubble = staff strength)"
)
st.plotly_chart(fig_comp_scatter, use_container_width=True)

# ---------------- AML ALERTS ----------------
st.header("3️⃣ AML Flags & Risk Alerts")
aml_summary_ind = aml_flags.groupby('reason').size().reset_index(name='count')
fig_aml_ind = px.bar(aml_summary_ind, x='reason', y='count',
                     labels={"reason":"AML Reason","count":"Number of Flags"},
                     title="Individual AML Alerts")
st.plotly_chart(fig_aml_ind, use_container_width=True)

aml_summary_comp = aml_flags_companies.groupby('reason').size().reset_index(name='count')
fig_aml_comp = px.bar(aml_summary_comp, x='reason', y='count',
                      labels={"reason":"AML Reason","count":"Number of Flags"},
                      title="Company AML Alerts")
st.plotly_chart(fig_aml_comp, use_container_width=True)

# ---------------- TRANSACTIONAL VISIBILITY ----------------
st.header("4️⃣ Transactional Visibility & Economic Activity")
agg_spend = spend_events.groupby(['state','category']).agg(total_amount=('amount','sum')).reset_index()
fig_spend = px.bar(
    agg_spend, x='state', y='total_amount', color='category', barmode='group',
    labels={"state":"State","total_amount":"Total Amount (₦)","category":"Category"},
    title="Aggregated Spend Events by State & Category"
)
st.plotly_chart(fig_spend, use_container_width=True)

company_inflow = spend_events.groupby('lga')['amount'].sum().reset_index().sort_values('amount',ascending=False)
fig_inflow = px.bar(
    company_inflow.head(20), x='lga', y='amount',
    labels={"lga":"LGA","amount":"Total Inflow (₦)"},
    title="Top 20 LGAs by Company Inflow"
)
st.plotly_chart(fig_inflow, use_container_width=True)

import plotly.graph_objects as go

# ---------------- 5️⃣ Sankey Flow: Individual Spend to Companies ----------------
st.header("5️⃣ Individual → Company Spend Flow")
st.markdown("**Question:** How does money flow from individuals to companies? Identify concentration or unusual patterns.")

# Aggregate top spend per LGA-category-company
top_spend = spend_events.groupby(['lga','category']).agg(total_amount=('amount','sum')).reset_index()

# For simplicity, pick top 50 flows
top_spend = top_spend.sort_values('total_amount', ascending=False).head(50)

# Define nodes
all_nodes = list(pd.concat([top_spend['lga'], top_spend['category']]).unique())
node_map = {name:i for i,name in enumerate(all_nodes)}

# Define links: LGA → Category
source = top_spend['lga'].map(node_map)
target = top_spend['category'].map(node_map)
value = top_spend['total_amount']

# Build Sankey diagram using graph_objects
fig_sankey = go.Figure(data=[go.Sankey(
    node=dict(
        pad=15,
        thickness=20,
        line=dict(color="black", width=0.5),
        label=all_nodes,
        color="lightblue"
    ),
    link=dict(
        source=source,
        target=target,
        value=value
    ))])

fig_sankey.update_layout(title_text="Top 50 Individual → Category Money Flows", font_size=10)
st.plotly_chart(fig_sankey, use_container_width=True)

st.markdown("✅ **Interactive dashboard with Compliance Index, Revenue Leakage, HNI Asset Gaps, AML Alerts & Transactional Visibility is complete. Use sidebar filters to explore dynamically.**")
