#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ -x .venv/Scripts/python.exe ]; then
    PYTHON=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then
    PYTHON=.venv/bin/python
else
    PYTHON=python
fi

echo "[1/5] Syncing PriceCatcher files from data.gov.my..."
"$PYTHON" scripts/01_ingest.py

echo "[2/5] Building the SQL warehouse (staging, star schema, marts)..."
"$PYTHON" scripts/02_build_warehouse.py

echo "[3/5] Fitting the fixed-effects price model..."
"$PYTHON" scripts/03_model.py

echo "[4/5] Validating processed outputs..."
"$PYTHON" scripts/04_validate.py

echo "[5/5] Drawing the README chart..."
"$PYTHON" scripts/05_build_chart.py

echo "[COMPLETE] Processed files ready in data/processed/"
