-- 01_staging.sql
-- Raw PriceCatcher files -> typed, de-duplicated staging tables with quality flags.
-- Nothing is deleted here: bad rows are flagged so the audit in 05_quality.sql can count them.

-- Items: drop the -1 placeholder row the source uses for "unknown"
create or replace table stg_item as
select
    item_code,
    trim(item)          as item,
    trim(unit)          as unit,
    trim(item_group)    as item_group,
    trim(item_category) as item_category
from read_parquet('data/raw/lookup_item.parquet')
where item_code > 0;

-- Premises: 'Pasar Basah ' appears with a trailing space in the source, which splits
-- wet markets into two store formats unless it is trimmed
create or replace table stg_premise as
select
    premise_code,
    trim(premise)      as premise,
    trim(premise_type) as premise_type,
    trim(state)        as state,
    trim(district)     as district
from read_parquet('data/raw/lookup_premise.parquet')
where premise_code > 0;

-- Daily prices, with the reference price each row is judged against
create or replace table stg_price as
with priced as (
    select
        p.date,
        date_trunc('month', p.date)::date as month,
        p.premise_code,
        p.item_code,
        p.price,
        median(p.price) over (
            partition by p.item_code, date_trunc('month', p.date)
        ) as item_month_median
    from read_parquet('data/raw/pricecatcher_*.parquet') as p
)
select
    priced.*,
    i.item_code is null    as is_unknown_item,
    s.premise_code is null as is_unknown_premise,
    -- Keying errors show up as misplaced decimals (RM5,390 for a kilo of onions) or
    -- RM0.01 placeholders. Anything beyond 3x either side of the month's national
    -- median for the same item is treated as an error, not a price.
    not (priced.price / priced.item_month_median between 1.0 / 3 and 3) as is_outlier
from priced
left join stg_item    as i on i.item_code = priced.item_code
left join stg_premise as s on s.premise_code = priced.premise_code;
