import streamlit as st
import pandas as pd
import PyPDF2
from datetime import datetime

st.set_page_config(page_title="DHA Report Extractor", layout="wide")
st.title("DHA Report PDF Extractor")

uploaded_file = st.file_uploader("Upload DHA Report PDF", type="pdf")

if uploaded_file:
    # Placeholder: extract text from PDF
    reader = PyPDF2.PdfReader(uploaded_file)
    pdf_text = ""
    for page in reader.pages:
        pdf_text += page.extract_text() or ""

    # --- Placeholder extraction (to be replaced with actual parsing logic) ---
    # For demo, use static/dummy data as per your spec

    # HEADER (demo values)
    customer = "Demo Scheme"
    policy_effective = "2025-06-01"
    policy_expiry = "2025-12-31"
    reporting_date = datetime.now().strftime("%Y-%m-%d")
    num_days = (datetime.strptime(policy_expiry, "%Y-%m-%d") - datetime.now()).days

    header_df = pd.DataFrame({
        "Customer": [customer],
        "Policy effective date": [policy_effective],
        "Policy expiry date": [policy_expiry],
        "Reporting Date": [reporting_date],
        "Number of days": [num_days]
    })

    st.subheader("Header Information")
    st.dataframe(header_df)

    # TABLE (demo values)
    table_df = pd.DataFrame({
        "Month": ["2024 SEPTEMBER", "2024 OCTOBER", "2024 NOVEMBER", "2024 DECEMBER",
                  "2025 JANUARY", "2025 FEBRUARY", "2025 MARCH", "2025 APRIL", "2025 MAY", "TOTAL"],
        "Value": [911791, 991189, 996378, 777027, 826596, 908013, 666542, 640463, 393375, "########"]
    })

    st.subheader("Total claims Processed per service month (by AED value)")
    st.dataframe(table_df)

    # Add more tables for census/claims by member as needed
else:
    st.info("Please upload a DHA PDF report to begin.")