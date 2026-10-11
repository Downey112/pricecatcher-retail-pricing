import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://storage.data.gov.my/pricecatcher"
LOOKUPS = {
    "lookup_item": {"item_code", "item", "unit", "item_group", "item_category"},
    "lookup_premise": {"premise_code", "premise", "premise_type", "state", "district"},
}
PRICE_COLUMNS = {"date", "premise_code", "item_code", "price"}

# Twelve complete months, so every calendar month appears exactly once
FIRST_MONTH = "2025-10"
LAST_MONTH = "2026-09"

MAX_ATTEMPTS = 6
TIMEOUT = 120


def fetch(url):
    # storage.data.gov.my resets connections intermittently, so retry with backoff
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            last_error = error
            print(f"[RETRY] {url} attempt {attempt}/{MAX_ATTEMPTS}: {error}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"Could not download {url}") from last_error


def save(name, expected_columns, force):
    out_file = RAW_DIR / f"{name}.parquet"
    # Closed months do not change, so a file already on disk is kept
    if out_file.exists() and not force:
        print(f"[SKIP] {name:<24} already in {out_file.parent.relative_to(ROOT)}")
        return

    df = pd.read_parquet(io.BytesIO(fetch(f"{BASE_URL}/{name}.parquet")))
    missing = expected_columns - set(df.columns)
    if missing:
        raise ValueError(f"{name}: expected columns missing: {sorted(missing)}")
    if df.empty:
        raise ValueError(f"{name}: downloaded table is empty")

    # Write to a temp file first so a failed run never leaves a half-written file
    tmp_file = out_file.with_suffix(".parquet.tmp")
    df.to_parquet(tmp_file, index=False)
    tmp_file.replace(out_file)
    print(f"[OK]   {name:<24} -> {out_file.relative_to(ROOT)} ({df.shape[0]:,} rows)")


def sync_storage(force=False):
    for name, columns in LOOKUPS.items():
        # Lookups are revised in place, so they are always refreshed
        save(name, columns, force=True)
    for month in pd.period_range(FIRST_MONTH, LAST_MONTH, freq="M"):
        save(f"pricecatcher_{month}", PRICE_COLUMNS, force)


if __name__ == "__main__":
    sync_storage(force="--force" in sys.argv)
