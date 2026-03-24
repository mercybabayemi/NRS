import streamlit as st
import os
import pandas as pd

@st.cache_data
def load_data():
    try:
        # Adding error handling for file existence
        data_dir = "~/NRS/analysis/data_v2"

        def read_safe(file):
            path = os.path.join(data_dir, file)
            return pd.read_csv(path) if os.path.exists(path) else pd.DataFrame()

        individuals_updated = pd.read_csv("~/NRS/analysis/data_v2/individuals_400k.csv")
        industries_updated = pd.read_csv("~/NRS/analysis/data_v2/companies_400k_enriched.csv")
        taxes_updated = pd.read_csv("~/NRS/analysis/data_v2//taxes_400k_law_based.csv")
        # aml_flags_individual = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/aml_flags.csv")
        # aml_flags_companies = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/aml_flags_companies.csv")
        # spend_events = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/parquet/spend_events.parquet")
        transactions_updated = pd.read_csv("~/NRS/analysis/data_v2/transactions_650k_linked_institutions.csv")
        banks = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/banks_financial.csv")
        assets_updated = pd.read_csv("~/NRS/analysis/data_v2/assets_400k.csv")
        # spend_aggregates = pd.read_csv("~/NRS/nrs_streamlit_app/generate_data/output/spend_aggregates.csv")
        relationships_updated = pd.read_csv("~/NRS/analysis/data_v2/relationships_400k_v2_dedup.csv")

        #2. Ensure date columns are datetime objects
        for df in [individuals_updated, industries_updated, taxes_updated, transactions_updated, banks, assets_updated,
                   relationships_updated]:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])

    except FileNotFoundError:
        st.error("CSV files not found. Check your file paths!")
        return None, None, None, None, None, None, None

    # 3. Basic Cleaning: Remove leading/trailing whitespace from column names
    individuals_updated.columns = individuals_updated.columns.str.strip()
    industries_updated.columns = industries_updated.columns.str.strip()
    taxes_updated.columns = taxes_updated.columns.str.strip()
    transactions_updated.columns = transactions_updated.columns.str.strip()
    banks.columns = banks.columns.str.strip()
    assets_updated.columns = assets_updated.columns.str.strip()
    relationships_updated.columns = relationships_updated.columns.str.strip()

    return individuals_updated, industries_updated, taxes_updated, transactions_updated, banks, assets_updated, relationships_updated