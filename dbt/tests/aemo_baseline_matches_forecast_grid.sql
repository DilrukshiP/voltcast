-- The baseline must have exactly one row for each row of the forecast grid.
-- This test returns pairs that are repeated. It passes when it returns no rows.

select
    issue_time,
    target_time,
    count(*) as row_count
from {{ ref('aemo_baseline') }}
group by issue_time, target_time
having count(*) > 1
