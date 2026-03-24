from analysis.components.load_data import load_data
import streamlit as st
import pandas as pd


def audit_data(individuals_df, industries_df, taxes_df, transaction_df, banks_df, assets_df, relationships_df):
    st.subheader("📋 Data Quality Audit")

    # Check 1: Shape & Nulls
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Industry Data Stats**")
        st.write(f"Dimensions: {industries_df.shape}")
        # st.write(f"Missing IDs: {df_indus['industry_id'].isnull().sum()}")  # Replace with your ID name
        # st.write(f"information: {industries_df.info} %n")

    with col2:
        st.write("**Individual Data Stats**")
        st.write(f"Dimensions: {individuals_df.shape}")
        # # st.write(f"Missing IDs: {df_ind['link_id'].isnull().sum()}")  # Replace with your ID name
        # st.write(f"information: {individuals_df.info}")

    # Check 2: Data Types (The 'Hidden' Bug)
    st.write("**Column Type Comparison**")
    type_comparison = pd.DataFrame({
        "Industry Col Type": industries_df.dtypes.astype(str),
        "Individual Col Type": individuals_df.dtypes.astype(str)
    })
    st.table(type_comparison.head(31))

    st.table(industries_df.head(5))
    st.table(individuals_df.head(5))