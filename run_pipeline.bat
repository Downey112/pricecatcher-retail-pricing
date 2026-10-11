@echo off
setlocal
cd /d "%~dp0"

set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

echo [1/5] Syncing PriceCatcher files from data.gov.my...
"%PYTHON%" scripts\01_ingest.py || exit /b 1

echo [2/5] Building the SQL warehouse (staging, star schema, marts)...
"%PYTHON%" scripts\02_build_warehouse.py || exit /b 1

echo [3/5] Fitting the fixed-effects price model...
"%PYTHON%" scripts\03_model.py || exit /b 1

echo [4/5] Validating processed outputs...
"%PYTHON%" scripts\04_validate.py || exit /b 1

echo [5/5] Drawing the README chart...
"%PYTHON%" scripts\05_build_chart.py || exit /b 1

echo [COMPLETE] Processed files ready in data\processed\
