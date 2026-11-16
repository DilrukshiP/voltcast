-- The "no future data" rule for the AEMO features.
-- Both runs must be published before the issue time, and the previous run before the newest run.
-- This test returns the rows that break the rule. It passes when it returns no rows.

select
    issue_time,
    aemo_newest_run_published_at,
    aemo_previous_run_published_at
from {{ ref('feature_aemo') }}
where aemo_newest_run_published_at >= issue_time
   or aemo_previous_run_published_at >= issue_time
   or aemo_previous_run_published_at >= aemo_newest_run_published_at
