-- Every half hour must be built from exactly six 5-minute intervals.
-- This test returns the half hours with another count. It passes when it returns no rows.

select
    target_time,
    interval_count
from {{ ref('prices_half_hourly') }}
where interval_count != 6
