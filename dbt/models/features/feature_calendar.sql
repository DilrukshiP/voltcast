-- Calendar features for every row of the forecast grid.
-- They are calculated from the clock only, so they need no data source.
--
-- A half hour is described by its start time. Example: the half hour that ends at 00:00
-- on Tuesday starts at 23:30 on Monday, so it counts as Monday, half hour number 47.

with grid as (
    select
        issue_time,
        target_time,
        horizon_steps,
        target_time - interval '30 minutes' as target_start
    from {{ ref('forecast_grid') }}
)

select
    issue_time,
    target_time,
    horizon_steps,
    cast(hour(target_start) * 2 + minute(target_start) / 30 as integer) as half_hour_of_day,
    cast(isodow(target_start) as integer) as day_of_week,
    isodow(target_start) >= 6 as is_weekend,
    cast(month(target_start) as integer) as month_of_year,
    cast(hour(issue_time) as integer) as issue_hour
from grid
