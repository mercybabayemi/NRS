import streamlit as st
import os
import pandas as pd

@st.cache_data
def load_data():
    # Adding error handling for file existence
    data_dir = "~/NRS/analysis/data_v2"

    def read_safe(file):
        path = os.path.join(data_dir, file)
        return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

    individuals_updated = pd.read_csv("~/NRS/analysis/data_v2/individuals_400k.csv")
    industries_updated = pd.read_csv("~/NRS/analysis/data_v2/companies_400k_enriched.csv")
    # taxes = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/taxes.csv")
    # aml_flags_individual = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/aml_flags.csv")
    # aml_flags_companies = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/aml_flags_companies.csv")
    # spend_events = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/parquet/spend_events.parquet")
    transactions_updated = pd.read_csv("~/NRS/analysis/data_v2/transactions_400k_linked.csv")
    banks = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/banks_financial.csv")
    assets_updated = pd.read_csv("~/NRS/analysis/data_v2/assets_400k.csv")
    #spend_aggregates = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/spend_aggregates.csv")
    #relationships = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/parquet/relationships.parquet")

    # Ensure date columns are datetime objects
    for df in [individuals_updated, industries_updated, transactions_updated, banks, assets_updated]:
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

    return individuals_updated, industries_updated, transactions_updated, banks, assets_updated
