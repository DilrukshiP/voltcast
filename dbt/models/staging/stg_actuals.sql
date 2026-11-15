-- One row per 5-minute interval, with clear column names.
-- `target_time` is the end of the half hour that the interval belongs to.
-- Example: the intervals ending 00:05 to 00:30 all belong to the half hour ending 00:30.

select
    region,
    interval_end,
    time_bucket(interval '30 minutes', interval_end - interval '5 minutes')
        + interval '30 minutes' as target_time,
    price as price_dollars_per_mwh,
    demand as demand_mw
from {{ source('raw', 'actuals') }}
