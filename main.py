import streamlit as st
import pandas as pd
import tempfile
import os

# PDF extraction libraries
import pdfplumber
import camelot
import tabula
from pdf2image import convert_from_path
import pytesseract

# Helper for table matching
def match_table(df, template, section):
    """
    Attempt to match df columns to template columns for a given section.
    Returns reformatted DataFrame if match is possible, else None.
    """
    template_cols = {
        "section6": ["Male", "Single females", "Married females", "Total"],
        "section7": ["Male", "Single females", "Married females", "Total"],
        "section8": ["Employee", "Spouse", "Dependents", "Totals"],
        "section17": ["Year", "Month ending date", "Value"]
    }

    # For census tables, check for typical column names (0-15, 16-25, ...)
    if section in ["section6", "section7"]:
        expected_cols = ["0-15", "16-25", "26-35", "36-50", "51-65", "Over 65", "Total"]
        if all(col in df.columns for col in expected_cols):
            return df
    # For section 8: claims by member type
    if section == "section8":
        expected_cols = ["IP", "OP", "Pharmacy", "Dental", "Optical", "Totals"]
        if all(col in df.columns for col in expected_cols):
            return df
    # For section 17: claims per month
    if section == "section17":
        expected_cols = ["Year", "Month ending date", "Value"]
        if all(col in df.columns for col in expected_cols):
            return df
    return None

def extract_tables_pdfplumber(pdf_path):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                df = pd.DataFrame(table[1:], columns=table[0])
                results.append(df)
    return results

def extract_tables_camelot(pdf_path):
    tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    results = []
    for table in tables:
        results.append(table.df)
    return results

def extract_tables_tabula(pdf_path):
    results = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
    return results

def extract_tables_ocr(pdf_path):
    # Convert PDF to images
    images = convert_from_path(pdf_path)
    dfs = []
    for img in images:
        text = pytesseract.image_to_string(img)
        # crude table parsing: split by lines, then columns by whitespace/tab
        lines = [line for line in text.split('\n') if line.strip()]
        # Try to detect if line looks like table header
        for i, line in enumerate(lines):
            if "Population census (at beginning" in line:
                # Section 6
                table_lines = lines[i:i+5]
                df = pd.DataFrame([row.split() for row in table_lines[1:]],
                                    columns=table_lines[0].split())
                dfs.append(("section6", df))
            if "Population census (at end" in line:
                # Section 7
                table_lines = lines[i:i+5]
                df = pd.DataFrame([row.split() for row in table_lines[1:]],
                                    columns=table_lines[0].split())
                dfs.append(("section7", df))
            if "Total claims Processed per service month" in line:
                # Section 17
                table_lines = lines[i+1:i+10]
                df = pd.DataFrame([row.split() for row in table_lines],
                                    columns=["Year", "Month ending date", "Value"])
                dfs.append(("section17", df))
            if "Claims data by member type" in line:
                # Section 8
                table_lines = lines[i+1:i+5]
                df = pd.DataFrame([row.split() for row in table_lines],
                                    columns=["IP", "OP", "Pharmacy", "Dental", "Optical", "Totals"])
                dfs.append(("section8", df))
    return dfs

def get_section_table(dfs, section):
    # Try to find a matching table for a section
    for df in dfs:
        mdf = match_table(df, None, section)
        if mdf is not None:
            return mdf
    return None

st.set_page_config(page_title="DHA Report PDF Extractor", layout="wide")
st.title("DHA Report PDF Extractor")

uploaded_file = st.file_uploader("Upload DHA Report PDF", type=["pdf"])

section_names = {
    "section6": "Population census (beginning of reporting period)",
    "section7": "Population census (end of reporting period)",
    "section17": "Total claims Processed per service month (by AED value)",
    "section8": "Claims data by member type (value AED)"
}

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    # Try extraction using pdfplumber
    plumber_tables = extract_tables_pdfplumber(pdf_path)

    # Try camelot (stream flavor)
    try:
        camelot_tables = extract_tables_camelot(pdf_path)
    except Exception:
        camelot_tables = []

    # Try tabula
    try:
        tabula_tables = extract_tables_tabula(pdf_path)
    except Exception:
        tabula_tables = []

    # Collect all tables
    all_tables = plumber_tables + camelot_tables + tabula_tables

    # Section extraction
    extracted = {}
    for section in section_names:
        extracted[section] = get_section_table(all_tables, section)

    # If any missing, try OCR fallback
    missing_sections = [s for s, df in extracted.items() if df is None]
    if missing_sections:
        ocr_tables = extract_tables_ocr(pdf_path)
        for sec, df in ocr_tables:
            if sec in missing_sections:
                extracted[sec] = df

    # Show DataFrames for each section
    for section, label in section_names.items():
        st.subheader(label)
        if extracted[section] is not None:
            st.dataframe(extracted[section])
        else:
            st.info(f"{label} not found in PDF.")

    # cleanup temp file
    os.unlink(pdf_path)
else:
    st.info("Please upload a DHA PDF report to begin.")

st.caption("For best results, use DHA PDF reports with clear table structures. If tables are scanned images, OCR is attempted but may be less accurate.")
