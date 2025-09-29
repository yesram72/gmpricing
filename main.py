import streamlit as st
import pandas as pd
import tempfile
import os
import re
import shutil

# Engines
import pdfplumber
import camelot
import tabula
from pdf2image import convert_from_path
import pytesseract

# -----------------------------
# Constants (fixed table shapes)
# -----------------------------
AGE_BANDS = ["0-15", "16-25", "26-35", "36-50", "51-65", "Over 65"]
CLAIM_COLS = ["IP", "OP", "Pharmacy", "Dental", "Optical", "Totals"]

CENSUS6_ROWS = {
    "6a": "Male",
    "6b": "Single females",
    "6c": "Married females",
}
CENSUS7_ROWS = {
    "7a": "Male",
    "7b": "Single females",
    "7c": "Married females",
}
CLAIMS8_ROWS = {
    "8a": "Employee",
    "8b": "Spouse",
    "8c": "Dependents",
    "8d": "Totals",
}
# Section 17: codes 17a..17m (up to 13 rows)
SECTION17_CODES = [f"17{chr(ord('a')+i)}" for i in range(13)]

# -----------------------------
# Utilities
# -----------------------------
def n(s: str) -> str:
    """Normalize text for matching."""
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9+\-]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_num(x):
    """Parse numeric cell with commas, dashes and blanks."""
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "-", "—", "–"):
        return None
    # keep digits, minus and dot; we'll strip commas next
    s = re.sub(r"[^0-9\-\.]+", "", s)
    s = s.replace(",", "")
    try:
        return float(s)
    except Exception:
        return None

def first_row_as_header_if_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """If columns are positional (0..n), use the first row as header."""
    if list(df.columns) == list(range(len(df.columns))) and len(df) > 1:
        header = df.iloc[0].astype(str).tolist()
        df = pd.DataFrame(df.iloc[1:].values, columns=header)
    return df

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = first_row_as_header_if_numeric(df)
    df.columns = [n(c) for c in df.columns]
    return df.reset_index(drop=True)

def age_band_key(header_text: str):
    """Map a header token to a canonical age band, if possible."""
    t = n(header_text)
    if "over" in t and "65" in t:
        return "Over 65"
    # 0-15, 16-25, etc. (support dash variants and no-dash)
    m = re.search(r"(\d{1,2})\s*[-–]?\s*(\d{1,2})", t)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        key = f"{a}-{b}"
        if key in AGE_BANDS:
            return key
    if re.search(r"\b65\+?\b", t):
        return "Over 65"
    return None

def map_age_columns(df: pd.DataFrame):
    mapping = {}
    for c in df.columns:
        k = age_band_key(c)
        if k:
            mapping[k] = c
    if "Over 65" not in mapping:
        for c in df.columns:
            if "65" in n(c) and "over" in n(c):
                mapping["Over 65"] = c
                break
    return mapping

def map_claim_columns(df: pd.DataFrame):
    mapping = {}
    for c in df.columns:
        cn = n(c)
        if cn in ("ip", "inpatient"):
            mapping["IP"] = c
        elif cn in ("op", "outpatient"):
            mapping["OP"] = c
        elif "pharmacy" in cn:
            mapping["Pharmacy"] = c
        elif "dental" in cn:
            mapping["Dental"] = c
        elif "optical" in cn or "optic" in cn:
            mapping["Optical"] = c
        elif cn in ("total", "totals", "grand total") or "total" in cn:
            mapping["Totals"] = c
    return mapping

def map_m17_columns(df: pd.DataFrame):
    """Map columns for Section 17: Month ending date, Year, Value."""
    mapping = {}
    for c in df.columns:
        cn = n(c)
        if ("month" in cn and "ending" in cn) or cn.startswith("month"):
            mapping["month"] = c
        elif cn == "year" or cn.endswith(" year") or "year" in cn.split():
            mapping["year"] = c
        elif "value" in cn or "amount" in cn or "aed" in cn:
            mapping["value"] = c
    return mapping

# -----------------------------
# Row-code detection
# -----------------------------
def detect_row_code_and_label(row_vals, expected_codes: set[str]):
    """Find a row code like '6a' or '17a' from first few cells; return (code, label_text_after_code)."""
    candidates = [str(v) for v in row_vals[:3] if str(v).strip()]
    # separate cell exact match
    for i, v in enumerate(candidates):
        nv = n(v)
        for code in expected_codes:
            if nv == code:
                label = ""
                if i + 1 < len(candidates):
                    label = candidates[i + 1]
                return code, label
    # combined like "6a Male" or "17a SEPTEMBER"
    for v in candidates:
        nv = n(v)
        for code in expected_codes:
            if nv.startswith(code):
                label = v[len(code):].strip(" :-\t")
                return code, label
    return None, None

# -----------------------------
# Anchored extraction for Sections 6,7,8
# -----------------------------
def extract_census(df_raw: pd.DataFrame, code_to_label: dict[str, str]):
    df = normalize_columns(df_raw)
    if df.empty:
        return None
    age_map = map_age_columns(df)
    if len(age_map) < 5:
        return None

    found = {}
    for _, row in df.iterrows():
        code, _ = detect_row_code_and_label(row.values.tolist(), set(code_to_label.keys()))
        if code and code not in found:
            found[code] = row

    if not all(c in found for c in code_to_label.keys()):
        return None

    out_rows = []
    for code, label in code_to_label.items():
        row = found[code]
        vals = {band: parse_num(row.get(age_map.get(band))) for band in AGE_BANDS}
        out_rows.append({"row": f"{code} {label}", **vals})
    out = pd.DataFrame(out_rows).set_index("row")[AGE_BANDS]
    # Add a Total column to mirror consolidated view
    out["Total"] = out[AGE_BANDS].sum(axis=1, skipna=True)
    return out

def extract_claims(df_raw: pd.DataFrame):
    df = normalize_columns(df_raw)
    if df.empty:
        return None
    claim_map = map_claim_columns(df)
    if len(set(claim_map.keys()) & set(CLAIM_COLS)) < 3:
        return None

    found = {}
    for _, row in df.iterrows():
        code, _ = detect_row_code_and_label(row.values.tolist(), set(CLAIMS8_ROWS.keys()))
        if code and code not in found:
            found[code] = row

    if not all(c in found for c in CLAIMS8_ROWS.keys()):
        return None

    rows = []
    for code, label in CLAIMS8_ROWS.items():
        row = found[code]
        vals = {}
        for col in CLAIM_COLS:
            src = claim_map.get(col)
            vals[col] = parse_num(row.get(src)) if src else None
        rows.append({"row": f"{code} {label}", **vals})
    out = pd.DataFrame(rows).set_index("row")[CLAIM_COLS]
    return out

# -----------------------------
# Anchored extraction for Section 17 (static layout)
# -----------------------------
def extract_section17(df_raw: pd.DataFrame):
    df = normalize_columns(df_raw)
    if df.empty:
        return None
    m = map_m17_columns(df)
    if not {"month", "year", "value"}.issubset(m.keys()):
        return None

    found = {}
    for _, row in df.iterrows():
        code, after = detect_row_code_and_label(row.values.tolist(), set(SECTION17_CODES))
        if not code:
            continue
        if code in found:
            continue
        month_txt = row.get(m["month"]) if m.get("month") in row else after or ""
        year_val = row.get(m["year"]) if m.get("year") in row else ""
        value_val = row.get(m["value"]) if m.get("value") in row else None
        found[code] = {
            "Month ending date": str(month_txt).strip(),
            "Year": str(year_val).strip(),
            "Value": parse_num(value_val),
        }

    if not found:
        return None

    # Order by code sequence 17a..17m and build DataFrame
    rows = []
    for code in SECTION17_CODES:
        if code in found:
            rows.append(found[code])
    if not rows:
        return None

    out = pd.DataFrame(rows, columns=["Month ending date", "Year", "Value"])  # fixed shape
    # Append TOTAL row like consolidated view
    total_val = pd.to_numeric(out["Value"], errors="coerce").sum()
    total_row = {"Month ending date": "TOTAL", "Year": "", "Value": total_val}
    out = pd.concat([out, pd.DataFrame([total_row])], ignore_index=True)
    return out

# -----------------------------
# Engines
# -----------------------------
def extract_tables_pdfplumber(pdf_path):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in (page.extract_tables() or []):
                if not table or len(table) < 2:
                    continue
                header, rows = table[0], table[1:]
                try:
                    df = pd.DataFrame(rows, columns=header)
                except Exception:
                    df = pd.DataFrame(rows)
                results.append(df)
    return results

def extract_tables_camelot(pdf_path):
    results = []
    for flavor, params in (("lattice", dict(line_scale=40)), ("stream", dict(row_tol=10, column_tol=10))):
        try:
            tables = camelot.read_pdf(pdf_path, pages="all", flavor=flavor, strip_text="\n", **params)
            for table in tables:
                results.append(table.df)
        except Exception:
            continue
    return results

def extract_tables_tabula(pdf_path):
    results = []
    for lattice in (True, False):
        try:
            dfs = tabula.read_pdf(pdf_path, pages='all', multiple_tables=True, lattice=lattice, stream=not lattice, guess=True)
            results.extend(dfs or [])
        except Exception:
            continue
    return results

# -----------------------------
# OCR fallback (guarded)
# -----------------------------
def extract_tables_ocr(pdf_path):
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
        except Exception:
            continue
        lines = [l for l in text.split('\n') if l.strip()]
        dfs.append(pd.DataFrame({"ocr_text": lines}))
    return dfs

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="DHA Report PDF Extractor", layout="wide")
st.title("DHA Report PDF Extractor")

st.sidebar.header("Options")
show_all_tables = st.sidebar.checkbox("Show ALL extracted tables", value=False)
enable_ocr = st.sidebar.checkbox("Enable OCR fallback if sections are missing", value=True)

uploaded_file = st.file_uploader("Upload DHA Report PDF", type=["pdf"]) 

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    # Extract with multiple engines
    plumber_tables = extract_tables_pdfplumber(pdf_path)
    camelot_tables = extract_tables_camelot(pdf_path)
    tabula_tables = extract_tables_tabula(pdf_path)

    all_tables = plumber_tables + camelot_tables + tabula_tables

    # Anchored extraction by codes
    section6_df = None
    section7_df = None
    section8_df = None
    section17_df = None

    for df in all_tables:
        if section6_df is None:
            section6_df = extract_census(df, CENSUS6_ROWS)
        if section7_df is None:
            section7_df = extract_census(df, CENSUS7_ROWS)
        if section8_df is None:
            section8_df = extract_claims(df)
        if section17_df is None:
            section17_df = extract_section17(df)
        if all(x is not None for x in [section6_df, section7_df, section8_df, section17_df]):
            break

    # OCR fallback best-effort (not reconstructing anchored rows here)
    if enable_ocr and any(x is None for x in [section6_df, section7_df, section8_df, section17_df]):
        _ocr_tables = extract_tables_ocr(pdf_path)

    # Render results in consolidated order
    st.header("Data Input from DHA Report")

    st.subheader("Population census (at beginning of reporting period)")
    st.dataframe(section6_df if section6_df is not None else pd.DataFrame(columns=AGE_BANDS + ["Total"]))

    st.subheader("Population census (at end of reporting period)")
    st.dataframe(section7_df if section7_df is not None else pd.DataFrame(columns=AGE_BANDS + ["Total"]))

    st.subheader("Total claims Processed per service month (by AED value)")
    st.dataframe(section17_df if section17_df is not None else pd.DataFrame(columns=["Month ending date", "Year", "Value"]))

    st.subheader("Claims data by member type (value AED)")
    st.dataframe(section8_df if section8_df is not None else pd.DataFrame(columns=CLAIM_COLS))

    # CSV downloads
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if section6_df is not None:
            st.download_button("Download Section 6 CSV", section6_df.to_csv().encode("utf-8"), file_name="section6.csv", mime="text/csv")
    with c2:
        if section7_df is not None:
            st.download_button("Download Section 7 CSV", section7_df.to_csv().encode("utf-8"), file_name="section7.csv", mime="text/csv")
    with c3:
        if section17_df is not None:
            st.download_button("Download Section 17 CSV", section17_df.to_csv(index=False).encode("utf-8"), file_name="section17.csv", mime="text/csv")
    with c4:
        if section8_df is not None:
            st.download_button("Download Section 8 CSV", section8_df.to_csv().encode("utf-8"), file_name="section8.csv", mime="text/csv")

    # Optional debugging
    if show_all_tables:
        st.header("All Extracted Tables (raw)")
        for source, tables in (("pdfplumber", plumber_tables), ("camelot", camelot_tables), ("tabula", tabula_tables)):
            if tables:
                st.subheader(f"{source} tables ({len(tables)})")
                for idx, tdf in enumerate(tables, 1):
                    with st.expander(f"{source} table {idx}"):
                        st.dataframe(tdf)

    os.unlink(pdf_path)
else:
    st.info("Please upload a DHA PDF report to begin.")

st.caption("Anchored on codes 6a–6c, 7a–7c, 8a–8d and 17a–17m. Output tables are fixed in shape to match the consolidated view. Only numeric cells are extracted.")