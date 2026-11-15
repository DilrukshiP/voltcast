-- The "no future data" rule for the naive baseline: the half hour it copies
-- must have ended at or before the issue time.
-- This test returns the rows that break the rule. It passes when it returns no rows.

select
    issue_time,
    target_time
from {{ ref('baseline_scores') }}
where target_time - interval '24 hours' > issue_time
