import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"

failures = []


def check(condition, message):
    print(f"[{'PASS' if condition else 'FAIL'}] {message}")
    if not condition:
        failures.append(message)


def read(name):
    return pd.read_parquet(PROCESSED_DIR / f"{name}.parquet")


def validate():
    fact = read("fact_price_monthly")
    item = read("dim_item")
    premise = read("dim_premise")
    month = read("dim_month")
    audit = read("quality_audit").set_index("step")["row_count"]

    # Keys and referential integrity
    check(item["item_code"].is_unique, "dim_item: item_code is a unique key")
    check(premise["premise_code"].is_unique, "dim_premise: premise_code is a unique key")
    check(month["month"].is_unique, "dim_month: month is a unique key")
    check(
        not fact.duplicated(["month", "premise_code", "item_code"]).any(),
        "fact_price_monthly: one row per shop, item and month",
    )
    check(set(fact["item_code"]) == set(item["item_code"]), "every item has fact rows, and the reverse")
    check(
        set(fact["premise_code"]) == set(premise["premise_code"]),
        "every shop has fact rows, and the reverse",
    )
    check(set(fact["month"]) == set(month["month"]), "every month has fact rows, and the reverse")

    # Dimension cleaning
    check(premise["store_format"].notna().all(), "dim_premise: every shop has a store format")
    check(premise["store_format"].nunique() == 5, "dim_premise: exactly five store formats")
    check(premise["state"].nunique() == 16, "dim_premise: all 16 states and territories present")
    check(item["item_group"].notna().all(), "dim_item: every item has an item group")

    # Measures
    check(fact["price"].gt(0).all(), "fact_price_monthly: all prices are positive")
    check(
        (fact["price"].between(fact["price_min"], fact["price_max"])).all(),
        "fact_price_monthly: monthly median lies between the month's min and max",
    )
    ratio = fact["price"] / fact["benchmark_price"]
    check(
        np.allclose(np.log(ratio), fact["log_price_gap"]),
        "fact_price_monthly: log_price_gap = ln(price / benchmark_price)",
    )
    gap_mean = fact.groupby(["item_code", "month"])["log_price_gap"].mean().abs().max()
    check(gap_mean < 1e-9, "fact_price_monthly: log gaps average to zero within every item-month")

    # The audit trail has to add up
    check(
        audit[1] == audit[2] + audit[3] + audit[4] + audit[5],
        "quality_audit: rows downloaded = rows removed + rows kept",
    )
    check(
        audit[5] == fact["days_observed"].sum(),
        "quality_audit: rows kept = daily rows behind the fact table",
    )
    check(audit[6] == len(fact), "quality_audit: fact row count matches")

    # Marts agree with the fact table
    formats = read("mart_format_index")
    overall = formats[formats["item_group"] == "All items"]
    check(
        overall["observations"].sum() == len(fact),
        "mart_format_index: 'All items' rows cover every fact row once",
    )
    states = read("mart_state_index")
    check(states["observations"].sum() == len(fact), "mart_state_index: covers every fact row once")
    basket = read("mart_basket")
    check((basket["items_priced"] == 16).all(), "mart_basket: every basket prices all 16 items")
    check(
        set(basket.loc[basket["cut"] == "State", "member"]) == set(premise["state"]),
        "mart_basket: a complete basket exists for every state",
    )

    # Model outputs
    variance = pd.read_csv(PROCESSED_DIR / "model_variance.csv")
    check(
        abs(variance["share_of_variance"].iloc[2:].sum() - 1) < 1e-3,
        "model_variance: format and state + shop + residual = 100%",
    )

    print(f"\n{len(fact):,} fact rows | {len(premise):,} shops | {len(item):,} items | {len(month)} months")
    if failures:
        print(f"{len(failures)} check(s) failed")
        sys.exit(1)
    print("All checks passed")


if __name__ == "__main__":
    validate()
