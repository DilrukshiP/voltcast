-- Every issue time must have exactly 48 rows, one for each half-hour step.
-- This test returns the issue times with another count. It passes when it returns no rows.

select
    issue_time,
    count(*) as row_count
from {{ ref('forecast_grid') }}
group by issue_time
having count(*) != 48 or count(distinct horizon_steps) != 48
