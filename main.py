import streamlit as st
import pandas as pd
import tempfile
import os
import re
import shutil

# PDF extraction libraries
import pdfplumber
import camelot
import tabula
from pdf2image import convert_from_path
import pytesseract


def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # If the first two rows look like headers, try to merge them
    if len(df) >= 2:
        first = df.iloc[0].astype(str).tolist()
        second = df.iloc[1].astype(str).tolist()
        # Heuristic: many non-numeric strings in first two rows => combine
        nonnum_first = sum(1 for x in first if re.search(r"[A-Za-z]", x))
        nonnum_second = sum(1 for x in second if re.search(r"[A-Za-z]", x))
        if nonnum_first >= max(2, len(first) // 2) and nonnum_second >= max(2, len(second) // 2):
            merged = []
            for a, b in zip(first, second):
                a_norm = a.strip()
                b_norm = b.strip()
                if a_norm and b_norm and a_norm != b_norm:
                    merged.append(f"{a_norm} {b_norm}")
                else:
                    merged.append(a_norm or b_norm)
            try:
                df.columns = merged
                df = df.iloc[2:].reset_index(drop=True)
                return df
            except Exception:
                pass

    # Default: use first row as header if headers look generic (0,1,2,...)
    if list(df.columns) == list(range(len(df.columns))):
        try:
            header = df.iloc[0].tolist()
            df = pd.DataFrame(df.iloc[1:].values, columns=header).reset_index(drop=True)
        except Exception:
            pass

    # Normalize column names
    df.columns = [normalize_text(c) for c in df.columns]
    return df


def header_keywords(section: str) -> set:
    # Canonical keywords per section (normalized)
    if section in ("section6", "section7"):
        # Population census tables: columns typically genders/status and totals
        return {"male", "single", "married", "female", "females", "total"}
    if section == "section8":
        # Claims by member type (value AED)
        return {"ip", "op", "pharmacy", "dental", "optical", "total", "totals"}
    if section == "section17":
        # Total claims processed per service month
        return {"year", "month", "month ending", "date", "value", "amount", "aed"}
    return set()


def compute_match_score(df: pd.DataFrame, section: str) -> float:
    if df is None or df.empty:
        return 0.0
    cols = [normalize_text(c) for c in df.columns]
    # Split multi-word headers into tokens
    tokens = set()
    for c in cols:
        tokens.update([t for t in c.split() if t])

    expected = header_keywords(section)
    if not expected:
        return 0.0

    overlap = len(tokens & expected)
    # Score by fraction of expected keywords found
    return overlap / max(1, len(expected))


def try_pdfplumber(pdf_path: str) -> list[pd.DataFrame]:
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables() or []
            for t in tables:
                if not t or len(t) < 2:
                    continue
                header = t[0]
                rows = t[1:]
                try:
                    df = pd.DataFrame(rows, columns=header)
                except Exception:
                    df = pd.DataFrame(rows)
                df = normalize_columns(df)
                results.append(df)
    return results


def try_camelot(pdf_path: str) -> list[pd.DataFrame]:
    results = []
    # Try lattice then stream with some tuning
    for flavor, params in (
        ("lattice", dict(line_scale=40)),
        ("stream", dict(row_tol=10, column_tol=10)),
    ):
        try:
            tables = camelot.read_pdf(
                pdf_path,
                pages="all",
                flavor=flavor,
                strip_text="\n",
                **params,
            )
            for tb in tables:
                df = tb.df
                df = normalize_columns(df)
                results.append(df)
        except Exception:
            continue
    return results


def try_tabula(pdf_path: str) -> list[pd.DataFrame]:
    results = []
    # Try both modes; Tabula requires Java
    for lattice in (True, False):
        try:
            dfs = tabula.read_pdf(
                pdf_path,
                pages="all",
                multiple_tables=True,
                lattice=lattice,
                stream=not lattice,
                guess=True,
            )
            for df in dfs or []:
                df = normalize_columns(df)
                results.append(df)
        except Exception:
            continue
    return results


def extract_tables_ocr(pdf_path: str) -> list[tuple[str, pd.DataFrame]]:
    # Guard: skip OCR if system binaries not ready
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

    out = []
    for img in images:
        try:
            text = pytesseract.image_to_string(img)
        except Exception as te:
            st.warning(f"OCR failed on a page (tesseract): {te}")
            continue

        # Very simple parsing; OCR is fuzzy, so we keep this as best-effort
        lines = [l for l in text.split("\n") if l.strip()]
        blob = "\n".join(lines).lower()

        # Heuristic buckets
        if "population census (at beginning" in blob:
            # Placeholder: leave table as raw OCR lines shown as a single-column df
            df = pd.DataFrame({"ocr_text": lines})
            out.append(("section6", df))
        if "population census (at end" in blob:
            df = pd.DataFrame({"ocr_text": lines})
            out.append(("section7", df))
        if "total claims processed per service month" in blob:
            df = pd.DataFrame({"ocr_text": lines})
            out.append(("section17", df))
        if "claims data by member type" in blob:
            df = pd.DataFrame({"ocr_text": lines})
            out.append(("section8", df))
    return out


def get_best_matches(dfs: list[pd.DataFrame], section: str, topk: int = 1) -> list[tuple[float, pd.DataFrame]]:
    scored = []
    for df in dfs:
        score = compute_match_score(df, section)
        if score > 0:
            scored.append((score, df))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:topk]


st.set_page_config(page_title="DHA Report PDF Extractor", layout="wide")
st.title("DHA Report PDF Extractor")

st.sidebar.header("Options")
show_all_tables = st.sidebar.checkbox("Show ALL extracted tables (with match scores)", value=False)
enable_ocr = st.sidebar.checkbox("Enable OCR fallback if sections are missing", value=True)

uploaded_file = st.file_uploader("Upload DHA Report PDF", type=["pdf"])

section_names = {
    "section6": "Population census (beginning of reporting period)",
    "section7": "Population census (end of reporting period)",
    "section17": "Total claims Processed per service month (by AED value)",
    "section8": "Claims data by member type (value AED)",
}

if uploaded_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        tmp_file.write(uploaded_file.read())
        pdf_path = tmp_file.name

    # Extract with multiple engines
    plumber_tables = try_pdfplumber(pdf_path)
    camelot_tables = try_camelot(pdf_path)
    tabula_tables = try_tabula(pdf_path)

    all_tables = plumber_tables + camelot_tables + tabula_tables

    # Try to find best match per section
    extracted: dict[str, pd.DataFrame | None] = {}
    diagnostics: dict[str, list[tuple[float, pd.DataFrame]]] = {}
    for section in section_names:
        best = get_best_matches(all_tables, section, topk=3)
        diagnostics[section] = best
        extracted[section] = best[0][1] if best else None

    # If missing, try OCR fallback
    missing_sections = [s for s, df in extracted.items() if df is None]
    ocr_tables = []
    if enable_ocr and missing_sections:
        ocr_tables = extract_tables_ocr(pdf_path)
        for sec, df in ocr_tables:
            if sec in missing_sections and df is not None and not df.empty:
                extracted[sec] = df

    # Optional: show all extracted tables with basic info
    if show_all_tables:
        st.header("All Extracted Tables")
        for label, tables in (("pdfplumber", plumber_tables), ("camelot", camelot_tables), ("tabula", tabula_tables)):
            if not tables:
                continue
            st.subheader(f"{label} tables ({len(tables)})")
            for idx, df in enumerate(tables, start=1):
                cols_preview = ", ".join(list(df.columns)[:10])
                with st.expander(f"{label} table {idx} | columns: {cols_preview}", expanded=False):
                    st.dataframe(df)
                    csv = df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        label=f"Download {label} table {idx} as CSV",
                        data=csv,
                        file_name=f"{label}_table_{idx}.csv",
                        mime="text/csv",
                        key=f"dl_{label}_{idx}",
                    )

        # Show best matches per section with scores
        st.subheader("Section match diagnostics")
        for section, label in section_names.items():
            st.markdown(f"**{label}**")
            cand = diagnostics.get(section, [])
            if not cand:
                st.write("No candidates.")
                continue
            for i, (score, df) in enumerate(cand, start=1):
                with st.expander(f"Candidate {i} (score: {score:.2f})", expanded=False):
                    st.dataframe(df)

    # Show final results by section
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

st.caption(
    "Tip: If targeted sections are not detected, enable 'Show ALL extracted tables' and review match diagnostics. "
    "OCR is best-effort and depends on scan quality."
)
