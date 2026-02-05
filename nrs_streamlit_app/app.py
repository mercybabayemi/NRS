
import streamlit as st
import pandas as pd

st.title("CSV Data Explorer")

file = st.file_uploader("Upload a CSV file")

if file:
    df = pd.read_csv(file)
    st.write("Preview")
    st.dataframe(df.head())

    st.write("Basic Stats")
    st.write(df.describe())

    
