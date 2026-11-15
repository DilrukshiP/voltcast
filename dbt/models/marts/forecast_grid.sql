-- Every forecast that VoltCast makes, as one row: an issue time and a target time.
-- A forecast is issued every hour, on the hour, and covers the next 24 hours
-- in 48 half-hour steps. Step 1 ends 30 minutes after the issue time, step 48 ends 24 hours after.
-- The grid stops at the last issue time for which all 48 actual prices exist.

with bounds as (
    select
        cast('{{ env_var("VOLTCAST_HISTORY_START", "2024-02-01") }}' as timestamp) as first_issue_time,
        max(target_time) - interval '24 hours' as last_issue_time
    from {{ ref('prices_half_hourly') }}
),

issue_times as (
    select unnest(generate_series(first_issue_time, last_issue_time, interval '1 hour')) as issue_time
    from bounds
),

steps as (
    select unnest(generate_series(1, 48)) as horizon_steps
)

select
    issue_times.issue_time,
    issue_times.issue_time + steps.horizon_steps * interval '30 minutes' as target_time,
    steps.horizon_steps
from issue_times
cross join steps
