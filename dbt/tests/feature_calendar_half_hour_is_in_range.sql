-- half_hour_of_day must be a whole number from 0 to 47, and each day must use all 48 values.
-- This test returns values outside the range. It passes when it returns no rows.

select
    half_hour_of_day,
    count(*) as row_count
from {{ ref('feature_calendar') }}
group by half_hour_of_day
having half_hour_of_day < 0 or half_hour_of_day > 47
