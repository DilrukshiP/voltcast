-- The "no future data" rule: a forecast must be published before the half hour it forecasts ends.
-- This test returns the rows that break the rule. It passes when it returns no rows.

select
    run_id,
    published_at,
    target_time
from {{ ref('stg_predispatch') }}
where published_at >= target_time
