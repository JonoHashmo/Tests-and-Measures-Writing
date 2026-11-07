#!/bin/bash
set -euo pipefail
MEASURE_WEB_DIR="$(cd "$(dirname "$0")" && pwd)"
MEASURE_WEB_ENV="${TMPDIR:-/tmp}/measure-browser-venv"
cd "$MEASURE_WEB_DIR/.."
if ! command -v python3 >/dev/null 2>&1; then
    printf 'Python 3.10 or later is required.\n'
    read -r -p 'Press Return to close. ' _measure_reply
    exit 1
fi
if [ ! -x "$MEASURE_WEB_ENV/bin/python" ]; then
    python3 -m venv "$MEASURE_WEB_ENV"
fi
if ! "$MEASURE_WEB_ENV/bin/python" -c 'import streamlit, docx, openpyxl, pdfplumber' >/dev/null 2>&1; then
    "$MEASURE_WEB_ENV/bin/python" -m pip install -r measure/requirements.txt
fi
exec "$MEASURE_WEB_ENV/bin/python" -m streamlit run measure/web_app.py --server.address localhost --browser.gatherUsageStats false --server.disconnectedSessionTTL 0
