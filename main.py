import streamlit as st
import pandas as pd
import tempfile
import os
import shutil

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
    if section in ["section6", "section7"]:
        expected_cols = ["0-15", "16-25", "26-35", "36-50", "51-65", "Over 65", "Total"]
        if all(col in df.columns for col in expected_cols):
            return df
    if section == "section8":
        expected_cols = ["IP", "OP", "Pharmacy", "Dental", "Optical", "Totals"]
        if all(col in df.columns for col in expected_cols):
            return df
    if section == "section17":
        expected_cols = ["Year", "Month ending date", "Value"]
        if all(col in df.columns for col in expected_cols):
            return df
    return None

def extract_tables_pdfplumber(pdf_path):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = table[0]
                rows = table[1:]
                try:
                    df = pd.DataFrame(rows, columns=header)
                except Exception:
                    df = pd.DataFrame(rows)
                results.append(df)
    return results

def extract_tables_camelot(pdf_path):
    try:
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
    except Exception:
        return []
    results = []
    for table in tables:
        try:
            results.append(table.df)
        except Exception:
            pass
    return results

def extract_tables_tabula(pdf_path):
    try:
        results = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True)
        return results or []
    except Exception:
        return []

def extract_tables_ocr(pdf_path):
    # Guard: skip OCR if Poppler (pdfinfo/pdftoppm) or Tesseract not available yet
    missing = []
    if not shutil.which("pdfinfo") or not shutil.which("pdftoppm"):
        missing.append("Poppler")
    if not shutil.which("tesseract"):
        missing.append("Tesseract")
    if missing:
        st.warning(f"OCR skipped: {', '.join(missing)} not found on server yet.")
        return []

    try:
        images = convert_from_path(pdf_path)
    except Exception as e:
        st.warning(f"OCR skipped (convert_from_path failed): {e}")
        return []

    dfs = []
    for img in images:
        try:
            text = pytesseract.image_to_string(img)
        except Exception as te:
            st.warning(f"OCR failed on a page (tesseract): {te}")
            continue

        lines = [line for line in text.split('\n') if line.strip()]
        for i, line in enumerate(lines):
            if "Population census (at beginning" in line:
                table_lines = lines[i:i+5]
                if len(table_lines) >= 2:
                    try:
                        df = pd.DataFrame([row.split() for row in table_lines[1:]],
                                          columns=table_lines[0].split())
                        dfs.append(("section6", df))
                    except Exception:
                        pass
            if "Population census (at end" in line:
                table_lines = lines[i:i+5]
                if len(table_lines) >= 2:
                    try:
                        df = pd.DataFrame([row.split() for row in table_lines[1:]],
                                          columns=table_lines[0].split())
                        dfs.append(("section7", df))
                    except Exception:
                        pass
            if "Total claims Processed per service month" in line:
                table_lines = lines[i+1:i+10]
                if table_lines:
                    try:
                        df = pd.DataFrame([row.split() for row in table_lines],
                                          columns=["Year", "Month ending date", "Value"])
                        dfs.append(("section17", df))
                    except Exception:
                        pass
            if "Claims data by member type" in line:
                table_lines = lines[i+1:i+5]
                if table_lines:
                    try:
                        df = pd.DataFrame([row.split() for row in table_lines],
                                          columns=["IP", "OP", "Pharmacy", "Dental", "Optical", "Totals"])
                        dfs.append(("section8", df))
                    except Exception:
                        pass
    return dfs

def get_section_table(dfs, section):
    for df in dfs:
        mdf = match_table(df, None, section)
        if mdf is not None:
            return mdf
    return None

st.set_page_config(page_title="DHA Report PDF Extractor", layout="wide")
st.title("DHA Report PDF Extractor")

# Sidebar options
st.sidebar.header("Options")
show_all_tables = st.sidebar.checkbox("Show ALL extracted tables (with CSV downloads)", value=False)
enable_ocr = st.sidebar.checkbox("Enable OCR fallback if sections are missing", value=True)

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

    plumber_tables = extract_tables_pdfplumber(pdf_path)
    camelot_tables = extract_tables_camelot(pdf_path)
    tabula_tables = extract_tables_tabula(pdf_path)

    all_tables = plumber_tables + camelot_tables + tabula_tables

    extracted = {}
    for section in section_names:
        extracted[section] = get_section_table(all_tables, section)

    missing_sections = [s for s, df in extracted.items() if df is None]
    ocr_tables = []
    if enable_ocr and missing_sections:
        ocr_tables = extract_tables_ocr(pdf_path)
        for sec, df in ocr_tables:
            if sec in missing_sections:
                extracted[sec] = df

    # Optional: show ALL extracted tables with CSV downloads
    if show_all_tables:
        st.header("All Extracted Tables")
        sources = [
            ("pdfplumber", plumber_tables),
            ("camelot", camelot_tables),
            ("tabula", tabula_tables),
        ]
        for source, tables in sources:
            if tables:
                st.subheader(f"{source} tables ({len(tables)})")
                for idx, df in enumerate(tables, start=1):
                    with st.expander(f"{source} table {idx} (rows={len(df)}, cols={len(df.columns)})", expanded=False):
                        st.dataframe(df)
                        csv = df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            label=f"Download {source} table {idx} as CSV",
                            data=csv,
                            file_name=f"{source}_table_{idx}.csv",
                            mime="text/csv",
                            key=f"dl_{source}_{idx}"
                        )

        if ocr_tables:
            st.subheader(f"OCR tables ({len(ocr_tables)})")
            for idx, (sec, df) in enumerate(ocr_tables, start=1):
                with st.expander(f"OCR table {idx} (matched to: {section_names.get(sec, sec)})", expanded=False):
                    st.dataframe(df)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label=f"Download OCR table {idx} as CSV",
                        data=csv,
                        file_name=f"ocr_table_{idx}.csv",
                        mime="text/csv",
                        key=f"dl_ocr_{idx}"
                    )

    # Show targeted sections
    st.header("Targeted Sections")
    for section, label in section_names.items():
        st.subheader(label)
        if extracted[section] is not None:
            st.dataframe(extracted[section])
        else:
            st.info(f"{label} not found in PDF.")

    os.unlink(pdf_path)
else:
    st.info("Please upload a DHA PDF report to begin.")

st.caption("For best results, use DHA PDF reports with clear table structures. If tables are scanned images, OCR is attempted but may be less accurate.")
