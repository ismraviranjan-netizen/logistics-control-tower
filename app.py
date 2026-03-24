import streamlit as st
import pandas as pd

st.set_page_config(page_title="My Control Tower", layout="wide")

st.title("Logistics Control Tower")
st.write("This is my first Streamlit app built from Google Colab.")

data = {
    "Shipment ID": ["SHP-101", "SHP-102", "SHP-103"],
    "Origin": ["Delhi", "Mumbai", "Pune"],
    "Destination": ["Jaipur", "Bangalore", "Hyderabad"],
    "Delay (hrs)": [2, 0, 5],
    "Risk": ["Medium", "Low", "High"]
}

df = pd.DataFrame(data)

st.subheader("Shipment Visibility")
st.dataframe(df, use_container_width=True)

st.subheader("Risk Summary")
st.bar_chart(df["Risk"].value_counts())
