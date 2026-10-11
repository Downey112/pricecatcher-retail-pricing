-- 05_quality.sql
-- One row per data-quality rule: what the raw files contained and what was done about it.
-- The rules are applied in order, so each raw row is counted exactly once and the
-- removals add up to the difference between rows downloaded and rows kept.

create or replace table quality_audit as
with classified as (
    select
        case
            when p.is_unknown_item then 'unknown_item'
            when p.is_outlier      then 'outlier'
            when s.premise_code is null then 'not_retail'
            else 'kept'
        end as outcome
    from stg_price as p
    left join dim_premise as s on s.premise_code = p.premise_code
)
select 1 as step, 'Daily price rows downloaded' as measure, count(*) as row_count
from classified
union all
select 2, 'Removed: item code missing from the item lookup',
       count(*) filter (where outcome = 'unknown_item')
from classified
union all
select 3, 'Removed: keying errors (beyond 3x the monthly median for the item)',
       count(*) filter (where outcome = 'outlier')
from classified
union all
select 4, 'Removed: wholesale premises, not a retail format',
       count(*) filter (where outcome = 'not_retail')
from classified
union all
select 5, 'Daily rows kept', count(*) filter (where outcome = 'kept')
from classified
union all
select 6, 'Shop-item-month rows in fact_price_monthly', count(*)
from fact_price_monthly
order by step;
