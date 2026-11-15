-- The "no future data" rule for the baseline: a run may be used only if it was
-- published before the issue time. This test returns the rows that break the rule.
-- It passes when it returns no rows.

select
    issue_time,
    aemo_run_id,
    aemo_published_at
from {{ ref('aemo_baseline') }}
where aemo_published_at >= issue_time
