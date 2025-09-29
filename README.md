# DHA PDF Extractor App

This Streamlit app extracts key tables from DHA PDF reports (text-based or scanned/image) and outputs them as Pandas DataFrames for analysis.

---

## ⚡️ Streamlit Cloud Deployment Only

This project is **deployed and runs exclusively on Streamlit Cloud**.  
There is no local/server install or setup required or supported.

---

## How it Works

- Upload a DHA PDF report.
- The app automatically extracts four key tables:
  - Section 6: Population census (beginning of reporting period)
  - Section 7: Population census (end of reporting period)
  - Section 17: Total claims processed per service month
  - Section 8: Claims data by member type (value AED)
- Tables are displayed as DataFrames in the browser.

---

## System Dependencies for Streamlit Cloud

Certain table extraction features require **system-level packages** that are NOT installed via `pip` or Python!

### These are pre-configured for Streamlit Cloud via `packages.txt`:

```
poppler-utils

tesseract-ocr

ghostscript
```

- **Do not install locally.**  
  These are installed automatically by Streamlit Cloud at deployment time.
- If you fork or redeploy, ensure `packages.txt` is present in your repo root.

---

## Troubleshooting Common Errors

### ❗️ PDFInfoNotInstalledError (pdf2image)

If you see:
```
pdf2image.exceptions.PDFInfoNotInstalledError: Unable to get page count. Is poppler installed and in PATH?
```
**This means Streamlit Cloud is still installing dependencies, or your app was restarted before setup finished.**

- Wait for deployment to finish.
- Check `packages.txt` is in your repo.
- If error persists, go to "Manage app" in Streamlit Cloud and click "Restart" or "Re-deploy".

### Other OCR/Table Extraction Errors

- Make sure your PDF is clear and tables are not heavily distorted.
- OCR fallback is best-effort and may yield imperfect results on poor scans.

---

## File Structure

- `main.py` — Streamlit app (PDF upload, table extraction, DataFrame display)
- `requirements.txt` — All Python dependencies (installed by Streamlit Cloud)
- `packages.txt` — **System packages for Streamlit Cloud** (do not use locally)
- `.streamlit/config.toml` — Optional UI config

---

## No Local Installation

- **Do NOT attempt to run this app locally.**
- All dependency installation, environment setup, and app execution are handled by Streamlit Cloud.

---

## For New Maintainers & Hand-off

- All changes should be made in the repo.
- All system dependencies are managed by `packages.txt`.
- If adding new extraction features, update `requirements.txt` and (if needed) `packages.txt`.
- Always test by uploading a PDF in the deployed Streamlit Cloud app.

---

## Support

For issues, open a GitHub Issue or contact the repo owner.
