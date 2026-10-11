-- 02_dimensions.sql
-- Conformed dimensions for the star schema. English labels are added next to the
-- Malay source values so the report reads in one language.

create or replace table dim_item as
select
    i.item_code,
    i.item,
    i.unit,
    i.item_group    as item_group_bm,
    case i.item_group
        when 'BARANGAN SEGAR'         then 'Fresh food'
        when 'BARANGAN KERING'        then 'Dry goods'
        when 'BARANGAN BERBUNGKUS'    then 'Packaged food'
        when 'MINUMAN'                then 'Beverages'
        when 'PRODUK KEBERSIHAN'      then 'Household & personal care'
        when 'SUSU DAN BARANGAN BAYI' then 'Baby products'
        else i.item_group
    end             as item_group,
    i.item_category
from stg_item as i
-- Only items that were actually priced in the window
where exists (
    select 1 from stg_price as p
    where p.item_code = i.item_code and not p.is_outlier
);

create or replace table dim_premise as
select
    s.premise_code,
    s.premise,
    s.premise_type  as store_format_bm,
    case s.premise_type
        when 'Hypermarket'              then 'Hypermarket'
        when 'Pasar Raya / Supermarket' then 'Supermarket'
        when 'Pasar Mini'               then 'Mini market'
        when 'Kedai Runcit'             then 'Sundry shop'
        when 'Pasar Basah'              then 'Wet market'
    end             as store_format,
    -- Largest format first, for sorting visuals
    case s.premise_type
        when 'Hypermarket'              then 1
        when 'Pasar Raya / Supermarket' then 2
        when 'Pasar Mini'               then 3
        when 'Kedai Runcit'             then 4
        when 'Pasar Basah'              then 5
    end             as store_format_order,
    s.state,
    case
        when s.state in ('Sabah', 'Sarawak', 'W.P. Labuan') then 'East Malaysia'
        else 'Peninsular Malaysia'
    end             as region,
    s.district
from stg_premise as s
-- Restaurants and food courts sit in the lookup but have no grocery prices, and the
-- single wholesaler (Borong) is not a retail format
where s.premise_type in (
        'Hypermarket', 'Pasar Raya / Supermarket', 'Pasar Mini', 'Kedai Runcit', 'Pasar Basah'
    )
    and exists (
        select 1 from stg_price as p
        where p.premise_code = s.premise_code and not p.is_outlier and not p.is_unknown_item
    );

create or replace table dim_month as
select
    month,
    strftime(month, '%b %Y')             as month_label,
    year(month)                          as year,
    month(month)                         as month_number,
    count(distinct date)                 as days_surveyed,
    row_number() over (order by month)   as month_index
from stg_price
group by month;
