import streamlit as st
import pandas as pd

def clean_data(loaded_indus, loaded_indiv):
    try:
        # 1. Standardize Join Key (TIN) and their ID
        # Mapping Individual's Employer to the Industry's Company ID
        loaded_indiv['employer_id'] = loaded_indiv['employer_id'].astype(str).str.replace('.0', '', regex=False)
        loaded_indus['company_id'] = loaded_indus['company_id'].astype(str)

        # Convert to string, strip spaces, and remove any decimals like '.0'
        loaded_indiv['tin'] = loaded_indiv['tin'].astype(str).str.replace(r'\.0$', '', regex=True)
        loaded_indus['tin'] = loaded_indus['tin'].astype(str).str.replace(r'\.0$', '', regex=True)

        # 2. Clean Currency Columns (Remove commas, df in , and convert to float)
        money_cols_to_fix = ['annual_income', 'assets_value', 'revenue', 'expenses', 'liabilities','tax_paid', 'net_income']

        for money_data in [loaded_indiv, loaded_indus]:
            for col in money_cols_to_fix:
                if col in money_data.columns:
                    money_data[col] = pd.to_numeric(money_data[col].astype(str).str.replace(',',''), errors='coerce')

        # 3. Rename Overlapping Columns for Clarity
        loaded_indus = loaded_indus.rename(columns={
            'name':'company_name',
            'tax_paid':'tax_paid',
        })

    except Exception as e:
        st.error(f"Error: {e}")
        return None, None, None, None, None, None, None
    return loaded_indiv, loaded_indus