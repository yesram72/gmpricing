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
import numpy as np

# Optional EasyOCR (lazy import only when needed)
EASYOCR_AVAILABLE = True
try:
    import easyocr  # noqa: F401
except Exception:
    EASYOCR_AVAILABLE = False

# -----------------------------
# Constants (fixed table shapes)
# -----------------------------
AGE_BANDS = ["0-15", "16-25", "26-35", "36-50", "51-65", "Over 65"]
CLAIM_COLS = ["IP", "OP", "Pharmacy", "Dental", "Optical", "Totals"]
MONTHS = [
    "JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"
]

CENSUS6_ROWS = {"6a": "Male", "6b": "Single females", "6c": "Married females"}
CENSUS7_ROWS = {"7a": "Male", "7b": "Single females", "7c": "Married females"}
CLAIMS8_ROWS = {"8a": "Employee", "8b": "Spouse", "8c": "Dependents", "8d": "Totals"}
SECTION17_CODES = [f"17{chr(ord('a')+i)}" for i in range(13)]  # 17a..17m

# -----------------------------
# Utilities
# -----------------------------
def n(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9+\-]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_num(x):
    if x is None:
        return None
    s = str(x).strip()
    if s in ("", "-", "—", "–"):
        return None
    s = s.replace(",", "")
    s = re.sub(r"[^0-9\-\.]+", "", s)
    try:
        return float(s)
    except Exception:
        return None

def first_row_as_header_if_numeric(df: pd.DataFrame) -> pd.DataFrame:
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
    t = n(header_text)
    if "over" in t and "65" in t:
        return "Over 65"
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

def detect_row_code_and_label(row_vals, expected_codes: set[str]):
    candidates = [str(v) for v in row_vals[:3] if str(v).strip()]
    # exact code in its own cell
    for i, v in enumerate(candidates):
        nv = n(v)
        for code in expected_codes:
            if nv == code:
                label = candidates[i + 1] if i + 1 < len(candidates) else ""
                return code, label
    # combined like "6a Male"
    for v in candidates:
        nv = n(v)
        for code in expected_codes:
            if nv.startswith(code):
                label = v[len(code):].strip(" :-\t")
                return code, label
    return None, None

# -----------------------------
# Anchored extraction (engines)
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
        if not code or code in found:
            continue
        month_txt = row.get(m["month"]) if m.get("month") in row else after or ""
        year_val = row.get(m["year"]) if m.get("year") in row else ""
        value_val = row.get(m["value"]) if m.get("value") in row else None
        found[code] = {"Month ending date": str(month_txt).strip(), "Year": str(year_val).strip(), "Value": parse_num(value_val)}

    if not found:
        return None

    rows = [found[c] for c in SECTION17_CODES if c in found]
    if not rows:
        return None

    out = pd.DataFrame(rows, columns=["Month ending date", "Year", "Value"])
    total_val = pd.to_numeric(out["Value"], errors="coerce").sum()
    out = pd.concat([out, pd.DataFrame([{"Month ending date": "TOTAL", "Year": "", "Value": total_val}])], ignore_index=True)
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
# EasyOCR fallback (line-based, code-anchored)
# -----------------------------
def _easyocr_reader():
    reader = st.session_state.get("_easyocr_reader")
    if reader is None:
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False)
        st.session_state["_easyocr_reader"] = reader
    return reader

def _ocr_lines_easyocr(img):
    reader = _easyocr_reader()
    res = reader.readtext(np.array(img), detail=1, paragraph=False)
    # res: list of ((x,y) quad, text, conf)
    items = []
    for bbox, text, conf in res:
        try:
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            cy = sum(ys) / len(ys)
            cx = sum(xs) / len(xs)
            items.append((cy, cx, text))
        except Exception:
            continue
    items.sort(key=lambda t: (t[0], t[1]))
    lines = []
    if not items:
        return lines
    current = [items[0]]
    for it in items[1:]:
        if abs(it[0] - current[-1][0]) <= 12:  # same-line threshold
            current.append(it)
        else:
            line_text = " ".join([x[2] for x in sorted(current, key=lambda t: t[1])])
            lines.append(line_text)
            current = [it]
    line_text = " ".join([x[2] for x in sorted(current, key=lambda t: t[1])])
    lines.append(line_text)
    return lines

def extract_with_easyocr(pdf_path):
    if not EASYOCR_AVAILABLE:
        return None, None, None, None
    try:
        images = convert_from_path(pdf_path, dpi=240)
    except Exception:
        return None, None, None, None

    census6_rows, census7_rows, claims8_rows, m17_rows = {}, {}, {}, {}
    code_pat = re.compile(r"^(6[abc]|7[abc]|8[abcd]|17[a-m])\b", flags=re.I)
    num_pat = re.compile(r"(\d[\d,]*)")

    for img in images:
        for ln in _ocr_lines_easyocr(img):
            ln_clean = ln.strip()
            m = code_pat.match(ln_clean)
            if not m:
                continue
            code = m.group(1).lower()
            nums = [parse_num(x) for x in num_pat.findall(ln_clean)]
            # census 6/7
            if code in CENSUS6_ROWS and len(nums) >= 6:
                census6_rows[code] = nums[:6]
            elif code in CENSUS7_ROWS and len(nums) >= 6:
                census7_rows[code] = nums[:6]
            # claims 8
            elif code in CLAIMS8_ROWS and len(nums) >= 5:
                claims8_rows[code] = nums[:6]
            # section 17
            elif code in SECTION17_CODES:
                upper = ln_clean.upper()
                month = next((mname for mname in MONTHS if mname in upper), "")
                year_match = re.search(r"\b(20\d{2}|19\d{2})\b", ln_clean)
                year = year_match.group(1) if year_match else ""
                value = nums[-1] if nums else None
                if month or year or value is not None:
                    m17_rows[code] = {"Month ending date": month, "Year": year, "Value": value}

    sec6 = sec7 = sec8 = sec17 = None
    if all(k in census6_rows for k in CENSUS6_ROWS.keys()):
        rows = []
        for k, label in CENSUS6_ROWS.items():
            vals = census6_rows.get(k)
            if not vals: break
            rows.append({"row": f"{k} {label}", **{band: vals[i] for i, band in enumerate(AGE_BANDS)}})
        if rows:
            sec6 = pd.DataFrame(rows).set_index("row")[AGE_BANDS]
            sec6["Total"] = sec6[AGE_BANDS].sum(axis=1, skipna=True)

    if all(k in census7_rows for k in CENSUS7_ROWS.keys()):
        rows = []
        for k, label in CENSUS7_ROWS.items():
            vals = census7_rows.get(k)
            if not vals: break
            rows.append({"row": f"{k} {label}", **{band: vals[i] for i, band in enumerate(AGE_BANDS)}})
        if rows:
            sec7 = pd.DataFrame(rows).set_index("row")[AGE_BANDS]
            sec7["Total"] = sec7[AGE_BANDS].sum(axis=1, skipna=True)

    if all(k in claims8_rows for k in CLAIMS8_ROWS.keys()):
        rows = []
        for k, label in CLAIMS8_ROWS.items():
            vals = claims8_rows.get(k)
            if not vals: break
            cols = ["IP", "OP", "Pharmacy", "Dental", "Optical", "Totals"]
            col_vals = {}
            for i, c in enumerate(cols):
                col_vals[c] = vals[i] if i < len(vals) else None
            if col_vals["Totals"] is None:
                tot = sum(v or 0 for v in [col_vals[c] for c in cols[:-1]])
                col_vals["Totals"] = tot
            rows.append({"row": f"{k} {label}", **col_vals})
        if rows:
            sec8 = pd.DataFrame(rows).set_index("row")[CLAIM_COLS]

    if m17_rows:
        ordered = [m17_rows[c] for c in SECTION17_CODES if c in m17_rows]
        if ordered:
            sec17 = pd.DataFrame(ordered, columns=["Month ending date", "Year", "Value"])
            total_val = pd.to_numeric(sec17["Value"], errors="coerce").sum()
            sec17 = pd.concat([sec17, pd.DataFrame([{"Month ending date": "TOTAL", "Year": "", "Value": total_val}])], ignore_index=True)

    return sec6, sec7, sec8, sec17

# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="DHA Report PDF Extractor", layout="wide")
st.title("Data Input from DHA Report")

st.sidebar.header("Options")
show_all_tables = st.sidebar.checkbox("Show ALL extracted tables", value=False)
enable_easyocr = st.sidebar.checkbox("Enable OCR fallback (EasyOCR) if sections are missing", value=True)

uploaded_file = st.file_uploader("Upload DHA Report PDF", type=["pdf"])\n
if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    # Try table engines first
    plumber_tables = extract_tables_pdfplumber(pdf_path)
    camelot_tables = extract_tables_camelot(pdf_path)
    tabula_tables = extract_tables_tabula(pdf_path)
    all_tables = plumber_tables + camelot_tables + tabula_tables

    section6_df = section7_df = section8_df = section17_df = None
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

    # EasyOCR fallback
    if enable_easyocr and any(x is None for x in [section6_df, section7_df, section8_df, section17_df]):
        if EASYOCR_AVAILABLE:
            o6, o7, o8, o17 = extract_with_easyocr(pdf_path)
            section6_df = section6_df or o6
            section7_df = section7_df or o7
            section8_df = section8_df or o8
            section17_df = section17_df or o17
        else:
            st.info("EasyOCR not installed. Install easyocr to enable OCR fallback.")

    # Render
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
            st.download_button("Download Section 6 CSV", section6_df.to_csv().encode("utf-8"), "section6.csv", "text/csv")
    with c2:
        if section7_df is not None:
            st.download_button("Download Section 7 CSV", section7_df.to_csv().encode("utf-8"), "section7.csv", "text/csv")
    with c3:
        if section17_df is not None:
            st.download_button("Download Section 17 CSV", section17_df.to_csv(index=False).encode("utf-8"), "section17.csv", "text/csv")
    with c4:
        if section8_df is not None:
            st.download_button("Download Section 8 CSV", section8_df.to_csv().encode("utf-8"), "section8.csv", "text/csv")

    # Optional: raw table diagnostics
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
