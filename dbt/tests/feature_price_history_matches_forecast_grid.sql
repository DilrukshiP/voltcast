-- The feature table must have exactly one row for each row of the forecast grid.
-- This test returns one row if the two row counts differ. It passes when it returns no rows.

with counts as (
    select
        (select count(*) from {{ ref('forecast_grid') }}) as grid_rows,
        (select count(*) from {{ ref('feature_price_history') }}) as feature_rows
)

select
    grid_rows,
    feature_rows
from counts
where grid_rows != feature_rows
