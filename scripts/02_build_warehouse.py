import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
PROCESSED_DIR = ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"

# Star schema tables go to parquet for Power BI; the small marts also go to CSV so they
# can be read on GitHub
STAR_TABLES = ["dim_item", "dim_premise", "dim_month", "fact_price_monthly"]
MART_TABLES = [
    "mart_format_index",
    "mart_state_index",
    "mart_format_index_monthly",
    "mart_item_dispersion",
    "mart_basket",
    "mart_repricing",
    "quality_audit",
]


def build():
    con = duckdb.connect(str(WAREHOUSE))
    # The SQL files use paths relative to the project root
    con.execute(f"set file_search_path = '{ROOT.as_posix()}'")

    for sql_file in sorted(SQL_DIR.glob("0*.sql")):
        started = time.perf_counter()
        con.execute(sql_file.read_text(encoding="utf-8"))
        print(f"[OK] {sql_file.name:<20} {time.perf_counter() - started:5.1f}s")

    for table in STAR_TABLES + MART_TABLES:
        rows = con.execute(f"select count(*) from {table}").fetchone()[0]
        out_file = PROCESSED_DIR / f"{table}.parquet"
        # Sorted output compresses far better, which keeps the fact table small enough to commit
        order = "order by item_code, month, premise_code" if table == "fact_price_monthly" else ""
        con.execute(f"copy (select * from {table} {order}) to '{out_file.as_posix()}' (format parquet)")
        if table in MART_TABLES:
            con.execute(
                f"copy {table} to '{out_file.with_suffix('.csv').as_posix()}' (header, delimiter ',')"
            )
        print(f"[OK] {table:<26} -> data/processed ({rows:,} rows)")

    con.close()


if __name__ == "__main__":
    build()
