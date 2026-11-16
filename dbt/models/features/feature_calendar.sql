-- Calendar features for every row of the forecast grid.
-- They are calculated from the clock and from a fixed list of Victorian public holidays.
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
    grid.issue_time,
    grid.target_time,
    grid.horizon_steps,
    cast(hour(grid.target_start) * 2 + minute(grid.target_start) / 30 as integer) as half_hour_of_day,
    cast(isodow(grid.target_start) as integer) as day_of_week,
    isodow(grid.target_start) >= 6 as is_weekend,
    holidays.holiday_date is not null as is_public_holiday,
    cast(month(grid.target_start) as integer) as month_of_year,
    cast(hour(grid.issue_time) as integer) as issue_hour
from grid
left join {{ ref('vic_public_holidays') }} as holidays
    on cast(grid.target_start as date) = holidays.holiday_date
