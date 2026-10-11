-- 03_fact.sql
-- Grain: one row per shop, item and month.
-- Shops are surveyed on different days and a different number of times, so daily rows
-- are collapsed to the shop's median price for the month before any comparison.

create or replace table fact_price_monthly as
with monthly as (
    select
        p.month,
        p.premise_code,
        p.item_code,
        median(p.price)         as price,
        min(p.price)            as price_min,
        max(p.price)            as price_max,
        count(*)                as days_observed,
        count(distinct p.price) as distinct_prices
    from stg_price as p
    semi join dim_item    as i on i.item_code = p.item_code
    semi join dim_premise as s on s.premise_code = p.premise_code
    where not p.is_outlier
    group by p.month, p.premise_code, p.item_code
)
select
    monthly.*,
    -- Like-for-like benchmark: the typical shop's price for this item this month
    exp(avg(ln(price)) over item_month)               as benchmark_price,
    -- Log gap to the benchmark. Averaging this and exponentiating gives a geometric
    -- mean, so an expensive item cannot dominate a cheap one.
    ln(price) - avg(ln(price)) over item_month        as log_price_gap,
    count(*) over item_month                          as shops_pricing_item,
    -- The same shop's price for the same item one month earlier. Left null when the
    -- pair was not surveyed in the previous month, so gaps are never read as changes.
    case
        when lag(month) over pair = month - interval 1 month then lag(price) over pair
    end                                               as price_previous_month
from monthly
window
    item_month as (partition by item_code, month),
    pair as (partition by premise_code, item_code order by month);

-- Keep the dimensions to members that own at least one fact row
delete from dim_item    where item_code    not in (select item_code from fact_price_monthly);
delete from dim_premise where premise_code not in (select premise_code from fact_price_monthly);
