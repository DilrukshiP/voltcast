-- The AEMO baseline: for every row of the forecast grid, the price that AEMO's
-- pre-dispatch forecast gave, using only what was public at the issue time.
--
-- Step 1: for each issue time, find the newest AEMO run published before it.
-- Step 2: take that run's forecast for the target time.
-- If AEMO has no usable forecast, the price is empty and the row is still kept.

with runs as (
    select distinct
        run_id,
        published_at
    from {{ ref('stg_predispatch') }}
),

issue_times as (
    select distinct issue_time
    from {{ ref('forecast_grid') }}
),

newest_run as (
    select
        issue_times.issue_time,
        runs.run_id,
        runs.published_at
    from issue_times
    asof left join runs
        on issue_times.issue_time > runs.published_at
)

select
    grid.issue_time,
    grid.target_time,
    grid.horizon_steps,
    newest_run.run_id as aemo_run_id,
    newest_run.published_at as aemo_published_at,
    date_diff('minute', newest_run.published_at, grid.issue_time) as aemo_run_age_minutes,
    forecasts.forecast_price_dollars_per_mwh as aemo_forecast_price_dollars_per_mwh
from {{ ref('forecast_grid') }} as grid
left join newest_run
    on grid.issue_time = newest_run.issue_time
left join {{ ref('stg_predispatch') }} as forecasts
    on newest_run.run_id = forecasts.run_id
    and grid.target_time = forecasts.target_time
