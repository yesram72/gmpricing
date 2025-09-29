import streamlit as st
import pandas as pd
from extract_dha_xml import extract_dha_tables

st.set_page_config(page_title="DHA Report Extractor", layout="wide")
st.title("DHA Report PDF/XML Extractor")

uploaded_file = st.file_uploader("Upload DHA Report XML", type=["xml"])

if uploaded_file:
    # Save uploaded file temporarily
    with open("uploaded_dha.xml", "wb") as f:
        f.write(uploaded_file.getbuffer())
    tables = extract_dha_tables("uploaded_dha.xml")

    # Extract header info from XML or ask user for input
    customer = st.text_input("Customer Name", value="")
    policy_effective = st.text_input("Policy Effective Date", value="")
    policy_expiry = st.text_input("Policy Expiry Date", value="")
    reporting_date = tables.get("report_date", "")
    num_days = st.text_input("Number of days", value="")

    header_df = pd.DataFrame({
        "Customer": [customer],
        "Policy effective date": [policy_effective],
        "Policy expiry date": [policy_expiry],
        "Reporting Date": [reporting_date],
        "Number of days": [num_days]
    })

    st.subheader("Header Information")
    st.dataframe(header_df)

    # Section 6
    st.subheader("Population census (beginning of reporting period)")
    if tables.get("population_census_beginning") is not None:
        st.dataframe(tables["population_census_beginning"])
    else:
        st.info("Section 6: Population census (beginning) not found in XML.")

    # Section 7
    st.subheader("Population census (end of reporting period)")
    if tables.get("population_census_end") is not None:
        st.dataframe(tables["population_census_end"])
    else:
        st.info("Section 7: Population census (end) not found in XML.")

    # Section 17
    st.subheader("Total claims Processed per service month (by AED value)")
    if tables.get("claims_by_month") is not None:
        st.dataframe(tables["claims_by_month"])
    else:
        st.info("Section 17: Claims by month not found in XML.")

    # Section 8
    st.subheader("Claims data by member type (value AED)")
    if tables.get("claims_by_member") is not None:
        st.dataframe(tables["claims_by_member"])
    else:
        st.info("Section 8: Claims by member type not found in XML.")

else:
    st.info("Please upload a DHA XML report to begin.")
