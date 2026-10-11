from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = ROOT / "data" / "processed"

# Baselines the coefficients are read against
BASE_FORMAT = "Supermarket"
BASE_STATE = "Selangor"

FE_TOLERANCE = 1e-10
FE_MAX_SWEEPS = 200


def within(values, groups):
    # Subtract the group mean: the fixed-effects "within" transformation
    return values - values.groupby(groups).transform("mean")


def load():
    fact = pd.read_parquet(
        PROCESSED_DIR / "fact_price_monthly.parquet",
        columns=["month", "premise_code", "item_code", "price"],
    )
    premise = pd.read_parquet(
        PROCESSED_DIR / "dim_premise.parquet",
        columns=["premise_code", "store_format", "state"],
    )
    df = fact.merge(premise, on="premise_code", validate="many_to_one")
    df["log_price"] = np.log(df["price"])
    # One fixed effect per item per month: shops are only compared on the same item
    # in the same month
    df["item_month"] = df.groupby(["item_code", "month"]).ngroup()
    return df


def fit_format_and_state(df):
    # log(price) = item-month effect + store format + state + error.
    # Demeaning both sides within item-month absorbs the item-month effects
    # (Frisch-Waugh-Lovell), leaving a regression small enough for OLS.
    formats = pd.get_dummies(df["store_format"], dtype=float).drop(columns=BASE_FORMAT)
    states = pd.get_dummies(df["state"], dtype=float).drop(columns=BASE_STATE)
    formats.columns = [f"format: {c}" for c in formats.columns]
    states.columns = [f"state: {c}" for c in states.columns]

    y = within(df["log_price"], df["item_month"])
    x_format = within(formats, df["item_month"])
    x_state = within(states, df["item_month"])
    x_both = pd.concat([x_format, x_state], axis=1)

    # A shop's prices are not independent draws, so errors are clustered by shop
    model = sm.OLS(y, x_both).fit(
        cov_type="cluster", cov_kwds={"groups": df["premise_code"].to_numpy()}
    )
    ci = model.conf_int()
    coefficients = pd.DataFrame(
        {
            "term": model.params.index,
            "premium_pct": 100 * (np.exp(model.params) - 1),
            "ci_low_pct": 100 * (np.exp(ci[0]) - 1),
            "ci_high_pct": 100 * (np.exp(ci[1]) - 1),
            "std_error_log": model.bse,
            "p_value": model.pvalues,
        }
    ).reset_index(drop=True)
    coefficients.insert(0, "factor", coefficients["term"].str.split(": ").str[0])
    coefficients["term"] = coefficients["term"].str.split(": ").str[1]
    coefficients["baseline"] = np.where(
        coefficients["factor"] == "format", BASE_FORMAT, BASE_STATE
    )

    r2 = {
        "format": sm.OLS(y, x_format).fit().rsquared,
        "state": sm.OLS(y, x_state).fit().rsquared,
        "format_and_state": model.rsquared,
    }
    return coefficients, r2, y


def shop_fixed_effects_r2(df, y):
    # Replace format and state with one fixed effect per shop. With two sets of fixed
    # effects on an unbalanced panel there is no one-step demeaning, so alternate
    # between the two until the residual stops changing.
    residual = y.copy()
    previous = np.inf
    for sweep in range(1, FE_MAX_SWEEPS + 1):
        residual = within(residual, df["premise_code"])
        residual = within(residual, df["item_month"])
        ss = float((residual**2).sum())
        if abs(previous - ss) < FE_TOLERANCE * ss:
            break
        previous = ss
    print(f"[OK] shop fixed effects converged after {sweep} sweeps")
    return 1 - ss / float((y**2).sum())


def run():
    df = load()
    coefficients, r2, y = fit_format_and_state(df)
    r2_shop = shop_fixed_effects_r2(df, y)

    # Where the price differences for the same item in the same month come from
    variance = pd.DataFrame(
        [
            ("Store format alone", r2["format"]),
            ("State alone", r2["state"]),
            ("Store format and state together", r2["format_and_state"]),
            ("The individual shop, beyond its format and state", r2_shop - r2["format_and_state"]),
            ("The residual: same shop, different item or month", 1 - r2_shop),
        ],
        columns=["source", "share_of_variance"],
    )
    variance["share_pct"] = (100 * variance["share_of_variance"]).round(1)
    variance["share_of_variance"] = variance["share_of_variance"].round(4)

    coefficients = coefficients.round(
        {"premium_pct": 2, "ci_low_pct": 2, "ci_high_pct": 2, "std_error_log": 5, "p_value": 4}
    )
    coefficients.to_csv(PROCESSED_DIR / "model_coefficients.csv", index=False)
    variance.to_csv(PROCESSED_DIR / "model_variance.csv", index=False)

    print(f"[OK] {len(df):,} observations, {df['item_month'].nunique():,} item-month effects, "
          f"{df['premise_code'].nunique():,} shop clusters")
    print(coefficients.to_string(index=False))
    print(variance.to_string(index=False))


if __name__ == "__main__":
    run()
