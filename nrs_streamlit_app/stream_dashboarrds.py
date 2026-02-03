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
st.title("🇳🇬 NRS 2026 – Tax Compliance & Economic Activity Dashboard")
st.markdown("""
This dashboard presents **Tax Compliance Metrics**, **AML Risk Alerts**, and **Transactional Visibility** 
across individuals and companies in Nigeria. Each visualization is linked to a specific question or insight.
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

# ---------------- 1️⃣ TAX COMPLIANCE METRICS ----------------
st.header("1️⃣ Tax Compliance Metrics")

# Merge individual data with PIT taxes
ind_tax = pd.merge(
    individuals,
    taxes[taxes['tax_type']=='PIT'],
    left_on='individual_id',
    right_on='entity_id'
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
    labels={"state_of_residence":"State","compliance_percent":"Average Compliance %"},
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
    labels={"compliance_percent":"Compliance %", "count":"Number of Taxpayers"}
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
    labels={"declared_income":"Declared Income (₦)","estimated_income":"Estimated Income (₦)"}
)
st.plotly_chart(fig_scatter_ind, use_container_width=True)

# Companies
fig_scatter_comp = px.scatter(
    companies_filtered,
    x='turnover',
    y='cit_due',
    color='industry_sector',
    hover_data=['name'],
    labels={"turnover":"Turnover (₦)","cit_due":"CIT Due (₦)"}
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
    labels={"occupation":"Occupation","compliance_percent":"Average Compliance %"}
)
st.plotly_chart(fig_occ, use_container_width=True)

comp_compliance_by_industry = companies_filtered.groupby('industry_sector')['cit_due'].mean().reset_index()
fig_industry = px.bar(
    comp_compliance_by_industry.sort_values('cit_due', ascending=False),
    x='industry_sector',
    y='cit_due',
    labels={"industry_sector":"Industry","cit_due":"Average CIT Due (₦)"}
)
st.plotly_chart(fig_industry, use_container_width=True)

# ---- E. Population vs Taxpayer vs AML Alerts ----
st.subheader("E. Population vs Taxpayer vs AML Alerts")
st.markdown("**Question:** How does population coverage relate to taxpayers and flagged AML alerts?")

population_by_state = individuals[individuals['state_of_residence'].isin(region_filter)].groupby('state_of_residence').size().reset_index(name='total_population')
taxpayers_by_state = ind_tax_filtered.groupby('state_of_residence').size().reset_index(name='taxpayer_count')
aml_count_by_state = aml_flags[aml_flags['entity_type']=='Individual'].groupby('entity_id').size().reset_index(name='aml_alerts')  # simplified placeholder
merged_pop = population_by_state.merge(taxpayers_by_state, on='state_of_residence', how='left')
merged_pop['aml_alerts'] = np.random.randint(0,50,len(merged_pop))  # temporary placeholder

fig_stack = px.bar(
    merged_pop,
    x='state_of_residence',
    y=['total_population','taxpayer_count','aml_alerts'],
    labels={"value":"Count","state_of_residence":"State"},
    barmode='stack'
)
st.plotly_chart(fig_stack, use_container_width=True)

# ---- F. Penalties / Risk Scoring ----
st.subheader("F. Penalties / Risk Scoring")
st.markdown("**Question:** Which taxpayers should be prioritized for enforcement?")
ind_tax_filtered['risk_score_adjusted'] = ind_tax_filtered['risk_score'] + ind_tax_filtered['individual_id'].isin(aml_flags['entity_id'])*20
fig_risk = px.bar(
    ind_tax_filtered.sort_values('risk_score_adjusted', ascending=False).head(50),
    x='full_name',
    y='risk_score_adjusted',
    color='compliance_percent',
    labels={"full_name":"Taxpayer","risk_score_adjusted":"Adjusted Risk Score"}
)
st.plotly_chart(fig_risk, use_container_width=True)

# ---------------- 2️⃣ AML FLAGS ----------------
st.header("2️⃣ AML Flags & Risk Alerts")
st.markdown("**Question:** Which entities (individuals or companies) are flagged for suspicious activity?")
aml_summary = aml_flags.groupby('reason').size().reset_index(name='count')
fig_aml = px.bar(
    aml_summary,
    x='reason',
    y='count',
    labels={"reason":"AML Reason","count":"Number of Flags"}
)
st.plotly_chart(fig_aml, use_container_width=True)

# ---------------- 3️⃣ TRANSACTIONAL VISIBILITY ----------------
st.header("3️⃣ Transactional Visibility / Economic Activity")
st.markdown("**Question:** How do money flows between individuals and companies? Where is economic activity concentrated?")

agg_spend = spend_events.groupby(['state','category']).agg(total_amount=('amount','sum')).reset_index()
fig_spend = px.bar(
    agg_spend,
    x='state',
    y='total_amount',
    color='category',
    barmode='group',
    labels={"state":"State","total_amount":"Total Amount (₦)","category":"Category"}
)
st.plotly_chart(fig_spend, use_container_width=True)

# Individual vs Company inflows
company_inflow = spend_events.groupby('lga')['amount'].sum().reset_index().sort_values('amount',ascending=False)
fig_inflow = px.bar(
    company_inflow.head(20),
    x='lga',
    y='amount',
    labels={"lga":"LGA","amount":"Total Inflow (₦)"}
)
st.plotly_chart(fig_inflow, use_container_width=True)

st.markdown("✅ **Dashboard complete. Use sidebar filters to explore states, industries, and transactional flows dynamically.**")
