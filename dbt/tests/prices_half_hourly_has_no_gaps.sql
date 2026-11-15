-- Each half hour must follow the one before it by exactly 30 minutes.
-- This test returns the half hours that come after a gap. It passes when it returns no rows.

with ordered as (
    select
        target_time,
        lag(target_time) over (order by target_time) as previous_target_time
    from {{ ref('prices_half_hourly') }}
)

select
    previous_target_time,
    target_time
from ordered
where previous_target_time is not null
  and target_time - previous_target_time != interval '30 minutes'
