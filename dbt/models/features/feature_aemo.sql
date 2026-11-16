-- Features from AEMO's pre-dispatch forecast, for every row of the forecast grid.
-- Only runs that were published before the issue time are used.
--
-- "Newest run": the last run published before the issue time. It is the run of aemo_baseline.
-- "Previous run": the run published just before the newest run, usually 30 minutes earlier.

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

recent_runs as (
    select
        issue_times.issue_time,
        runs.run_id,
        runs.published_at,
        row_number() over (
            partition by issue_times.issue_time
            order by runs.published_at desc
        ) as recency
    from issue_times
    inner join runs
        on runs.published_at < issue_times.issue_time
        and runs.published_at >= issue_times.issue_time - interval '3 hours'
),

previous_run as (
    select
        issue_time,
        run_id,
        published_at
    from recent_runs
    where recency = 2
),

newest_run_summary as (
    select
        recent_runs.issue_time,
        max(forecasts.forecast_price_dollars_per_mwh) as aemo_run_max_price,
        avg(forecasts.forecast_price_dollars_per_mwh) as aemo_run_mean_price,
        count(*) as aemo_run_steps_ahead
    from recent_runs
    inner join {{ ref('stg_predispatch') }} as forecasts
        on recent_runs.run_id = forecasts.run_id
        and forecasts.target_time > recent_runs.issue_time
    where recent_runs.recency = 1
    group by recent_runs.issue_time
)

select
    grid.issue_time,
    grid.target_time,
    grid.horizon_steps,
    baseline.aemo_forecast_price_dollars_per_mwh as aemo_forecast_price,
    baseline.aemo_forecast_price_dollars_per_mwh is not null as aemo_has_forecast,
    previous_forecasts.forecast_price_dollars_per_mwh as aemo_forecast_price_previous_run,
    baseline.aemo_forecast_price_dollars_per_mwh
        - previous_forecasts.forecast_price_dollars_per_mwh as aemo_forecast_change,
    newest_run_summary.aemo_run_max_price,
    newest_run_summary.aemo_run_mean_price,
    newest_run_summary.aemo_run_steps_ahead,
    baseline.aemo_published_at as aemo_newest_run_published_at,
    previous_run.published_at as aemo_previous_run_published_at
from {{ ref('forecast_grid') }} as grid
left join {{ ref('aemo_baseline') }} as baseline
    on grid.issue_time = baseline.issue_time
    and grid.target_time = baseline.target_time
left join previous_run
    on grid.issue_time = previous_run.issue_time
left join {{ ref('stg_predispatch') }} as previous_forecasts
    on previous_run.run_id = previous_forecasts.run_id
    and grid.target_time = previous_forecasts.target_time
left join newest_run_summary
    on grid.issue_time = newest_run_summary.issue_time
