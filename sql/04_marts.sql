-- 04_marts.sql
-- Answer-shaped tables built on the star schema. Each one is small enough to read.

-- Q1. Same item, same month: how far is each store format from the typical shop?
-- GROUPING SETS adds an 'All items' row per format alongside the item groups.
create or replace table mart_format_index as
select
    s.store_format,
    s.store_format_order,
    coalesce(i.item_group, 'All items')             as item_group,
    count(distinct f.premise_code)                  as shops,
    count(*)                                        as observations,
    round(100 * exp(avg(f.log_price_gap)), 2)       as price_index,
    round(100 * (exp(avg(f.log_price_gap)) - 1), 2) as premium_pct
from fact_price_monthly as f
join dim_premise as s on s.premise_code = f.premise_code
join dim_item    as i on i.item_code = f.item_code
group by grouping sets (
    (s.store_format, s.store_format_order, i.item_group),
    (s.store_format, s.store_format_order)
);

-- Q2. The same comparison by state, ranked cheapest to dearest
create or replace table mart_state_index as
select
    s.state,
    s.region,
    count(distinct f.premise_code)                  as shops,
    count(*)                                        as observations,
    round(100 * exp(avg(f.log_price_gap)), 2)       as price_index,
    round(100 * (exp(avg(f.log_price_gap)) - 1), 2) as premium_pct,
    rank() over (order by avg(f.log_price_gap))     as rank_cheapest
from fact_price_monthly as f
join dim_premise as s on s.premise_code = f.premise_code
group by s.state, s.region;

-- Q3. Does the gap between formats move through the year?
create or replace table mart_format_index_monthly as
select
    f.month,
    s.store_format,
    s.store_format_order,
    count(distinct f.premise_code)            as shops,
    round(100 * exp(avg(f.log_price_gap)), 2) as price_index
from fact_price_monthly as f
join dim_premise as s on s.premise_code = f.premise_code
group by f.month, s.store_format, s.store_format_order;

-- Q4. Which items have one price everywhere, and which depend on where you shop?
-- The P90/P10 spread is the extra a shopper pays at a dear shop over a cheap one.
create or replace table mart_item_dispersion as
select
    i.item_code,
    i.item,
    i.unit,
    i.item_group,
    i.item_category,
    count(distinct f.premise_code)                                 as shops,
    round(exp(avg(ln(f.price))), 2)                                as typical_price,
    round(stddev_samp(f.log_price_gap), 4)                         as sd_log_gap,
    round(100 * (exp(quantile_cont(f.log_price_gap, 0.9)
                   - quantile_cont(f.log_price_gap, 0.1)) - 1), 1) as p90_p10_spread_pct
from fact_price_monthly as f
join dim_item as i on i.item_code = f.item_code
group by i.item_code, i.item, i.unit, i.item_group, i.item_category
-- A spread needs enough shops behind it to mean anything
having count(distinct f.premise_code) >= 100;

-- Q5. What does a fixed basket of staples cost by format and by state?
-- One unit of each of sixteen widely stocked items. Each item is priced at the
-- geometric mean across shops and months, so the basket never depends on any single
-- shop carrying everything.
create or replace table basket_item as
select item_code
from (values
    (1),     -- AYAM BERSIH - STANDARD, 1kg
    (1110),  -- TELUR AYAM GRED B, 30 biji
    (1476),  -- IKAN KEMBUNG, 1kg
    (918),   -- MINYAK MASAK PAKET, 1kg (price-controlled)
    (1589),  -- GULA PUTIH BERTAPIS KASAR, 1kg (price-controlled)
    (917),   -- TEPUNG GANDUM CAP SAUH, 1kg
    (129),   -- BAWANG BESAR KUNING/HOLLAND, 1kg
    (1564),  -- BAWANG PUTIH IMPORT (CHINA), 1kg
    (1131),  -- UBI KENTANG IMPORT (CHINA), 1kg
    (114),   -- TOMATO, 1kg
    (1558),  -- SAWI HIJAU, 1kg
    (191),   -- SARDIN CAP AYAM (SOS TOMATO), 425 g
    (1976),  -- MAGGI MI SEGERA PERISA KARI, 5 x 79g
    (883),   -- KRIMER MANIS BERVITAMIN CAP F&N, 500 g
    (1611),  -- SANTAN KELAPA JENAMA KARA, 200 ml
    (2114)   -- MILO (PAKET), 900 g
) as b(item_code);

create or replace table mart_basket as
with item_price as (
    select 'Store format' as cut, s.store_format as member, f.item_code,
           exp(avg(ln(f.price))) as price
    from fact_price_monthly as f
    join dim_premise as s on s.premise_code = f.premise_code
    semi join basket_item as b on b.item_code = f.item_code
    group by s.store_format, f.item_code
    union all
    select 'State', s.state, f.item_code, exp(avg(ln(f.price)))
    from fact_price_monthly as f
    join dim_premise as s on s.premise_code = f.premise_code
    semi join basket_item as b on b.item_code = f.item_code
    group by s.state, f.item_code
    union all
    select 'Malaysia', 'Malaysia', f.item_code, exp(avg(ln(f.price)))
    from fact_price_monthly as f
    semi join basket_item as b on b.item_code = f.item_code
    group by f.item_code
),
basket as (
    select cut, member, count(*) as items_priced, sum(price) as basket_cost
    from item_price
    group by cut, member
)
select
    cut,
    member,
    items_priced,
    round(basket_cost, 2) as basket_cost,
    round(basket_cost - max(basket_cost) filter (where cut = 'Malaysia') over (), 2)
        as vs_malaysia_rm
from basket
-- A basket missing an item would look cheap for the wrong reason
where items_priced = (select count(*) from basket_item);

-- Q6. Who actually changes prices? Share of shop-item pairs whose monthly price moved
-- from the month before, using the lagged price carried on the fact table.
create or replace table mart_repricing as
select
    s.store_format,
    s.store_format_order,
    i.item_group,
    count(*) as pairs,
    round(100.0 * count(*) filter (where f.price <> f.price_previous_month) / count(*), 1)
        as pct_repriced,
    round(100.0 * count(*) filter (where f.price < f.price_previous_month) / count(*), 1)
        as pct_cut,
    round(100.0 * count(*) filter (where f.price > f.price_previous_month) / count(*), 1)
        as pct_raised
from fact_price_monthly as f
join dim_premise as s on s.premise_code = f.premise_code
join dim_item    as i on i.item_code = f.item_code
where f.price_previous_month is not null
group by s.store_format, s.store_format_order, i.item_group;
