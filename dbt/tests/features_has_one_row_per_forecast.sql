-- The training table must have exactly one row for each row of the forecast grid:
-- the same number of rows, and no pair of issue time and target time twice.
-- This test returns one row for each problem. It passes when it returns no rows.

select
    'row count differs from the forecast grid' as problem
from (
    select
        (select count(*) from {{ ref('forecast_grid') }}) as grid_rows,
        (select count(*) from {{ ref('features') }}) as feature_rows
) as counts
where grid_rows != feature_rows

union all

select
    'a forecast appears more than once' as problem
from {{ ref('features') }}
group by issue_time, target_time
having count(*) > 1
