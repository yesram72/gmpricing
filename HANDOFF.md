# Handover: Liva UW workbench (Streamlit)

This document gives everything needed to understand the current state, run the app, and continue development.

Repository: https://github.com/yesram72/gmpricing
Owner: @yesram72

## Current status
- App framework: Streamlit
- Branch with working app: `feat/streamlit-main`
- Files added:
  - `main.py` — minimal Streamlit app with title "Liva UW workbench"
  - `requirements.txt` — includes `streamlit`
  - `.gitignore` — Python/Streamlit friendly ignores
- Open PR: Add Streamlit entrypoint (Liva UW workbench) + deps and .gitignore
  - Link: https://github.com/yesram72/gmpricing/pull/2
  - Note: If the PR is in Draft, click "Ready for review" before merging.

## How to run locally
1) Clone and select the branch
```bash
git clone https://github.com/yesram72/gmpricing.git
cd gmpricing
# If PR not merged yet, use the feature branch:
git checkout feat/streamlit-main
```

2) Create a virtual environment and install dependencies
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

3) Run Streamlit
```bash
streamlit run main.py
```

4) Open your browser to http://localhost:8501 — you should see the page titled "Liva UW workbench".

Troubleshooting
- If you see "module not found", ensure your venv is active and run: `pip install -r requirements.txt`.
- If port 8501 is busy, run: `streamlit run main.py --server.port 8502`.

## After merging the PR
If you prefer running from `main` after merging PR #2:
```bash
cd gmpricing
git checkout main
git pull
pip install -r requirements.txt
streamlit run main.py
```

## Optional configuration (recommended)
You can customize Streamlit via a config file. Suggested defaults:
```toml
# .streamlit/config.toml
[server]
headless = true
port = 8501
enableCORS = false
enableXsrfProtection = true

[theme]
base = "light"
primaryColor = "#4B8BBE"
font = "sans serif"
```
To use this, create the folder `.streamlit/` at the repo root and add `config.toml` with the contents above.

## Repo structure (current)
```text
.
├── .gitignore
├── main.py
└── requirements.txt
```

## How to extend the app
- Multi-page structure: create a `pages/` directory. Any `.py` files inside become additional pages.
```bash
mkdir -p pages
```
Example page file:
```python
# pages/01_Hello.py
import streamlit as st
st.title("Hello from a second page")
st.write("This page lives in pages/01_Hello.py")
```
- Sidebar navigation: use `st.sidebar` for filters, switches, file uploads.
- State management: `st.session_state` for cross-widget or cross-page state.

## Common commands
```bash
# Install deps
pip install -r requirements.txt

# Run app
activate-your-venv && streamlit run main.py

# Freeze exact versions (optional)
pip freeze > requirements.txt
```

## Suggested next steps
- Documentation:
  - Add a README.md with quickstart and screenshots.
  - Keep this HANDOFF.md updated as decisions are made.
- Configuration:
  - Add `.streamlit/config.toml` (see above) to pin server and theme defaults.
- Code quality:
  - Add `black`, `ruff` (or `flake8`), and `pre-commit` hooks.
- CI (optional but helpful):
  - GitHub Actions workflow to run lint/format and a basic import check on PRs.
- Features:
  - Set up a multipage skeleton under `pages/`.
  - Add an app layout with sidebar, tabs, or columns.

## Deploy options
- Streamlit Community Cloud (fastest):
  1. Go to https://streamlit.io/cloud and sign in with GitHub.
  2. New app → Repository: `yesram72/gmpricing`, Branch: `main` (or `feat/streamlit-main`), File: `main.py`.
  3. Click Deploy. The app builds and becomes available at a shareable URL.
  4. Add any secrets via the Cloud UI if needed later.
- Self-host (Docker or VM):
  - Example: `streamlit run main.py --server.address 0.0.0.0 --server.port 8501` behind a reverse proxy.

## Handy prompts for future assistants
- "Create a multipage Streamlit skeleton with a pages/ folder and an example page."
- "Add .streamlit/config.toml with light theme and port 8501, then open a PR."
- "Set up GitHub Actions to run black and ruff on push and PR."
- "Add a sidebar with inputs for [describe feature], update main.py."
- "Deploy this repo to Streamlit Community Cloud and document the steps." 

## Ownership and contacts
- Repo owner: @yesram72
- Primary branch: `main` (feature work currently on `feat/streamlit-main`)

---
This HANDOFF.md is intended for any developer or AI assistant to quickly pick up and continue work. If you need changes, update this file and/or the README in the same branch.