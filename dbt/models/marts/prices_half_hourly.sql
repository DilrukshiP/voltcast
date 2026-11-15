-- One row per half hour: the forecast target of VoltCast.
-- The half-hour price is the average of the six 5-minute prices inside it.
-- No half hour is removed here. An incomplete half hour is kept and reported by a test.

select
    region,
    target_time,
    avg(price_dollars_per_mwh) as price_dollars_per_mwh,
    min(price_dollars_per_mwh) as min_price_dollars_per_mwh,
    max(price_dollars_per_mwh) as max_price_dollars_per_mwh,
    avg(demand_mw) as demand_mw,
    count(*) as interval_count
from {{ ref('stg_actuals') }}
group by region, target_time
