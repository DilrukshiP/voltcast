-- The score table must have exactly one row for each row of the forecast grid.
-- This test returns one row if the two row counts differ. It passes when it returns no rows.

with counts as (
    select
        (select count(*) from {{ ref('forecast_grid') }}) as grid_rows,
        (select count(*) from {{ ref('baseline_scores') }}) as score_rows
)

select
    grid_rows,
    score_rows
from counts
where grid_rows != score_rows
