-- A run must forecast each target half hour only once.
-- This test returns the pairs that appear more than once. It passes when it returns no rows.

select
    run_id,
    target_time,
    count(*) as row_count
from {{ ref('stg_predispatch') }}
group by run_id, target_time
having count(*) > 1
