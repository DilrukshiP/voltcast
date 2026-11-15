-- Both baselines beside the actual price, for every row of the forecast grid.
--
-- Naive baseline: the actual price at the same time one day earlier.
-- For every step from 1 to 48, that half hour has already ended at the issue time.
-- AEMO baseline: see the model aemo_baseline.
--
-- An error is the absolute difference between a forecast and the actual price.
-- The AEMO error is empty where AEMO gave no forecast.

select
    grid.issue_time,
    grid.target_time,
    grid.horizon_steps,
    actual.price_dollars_per_mwh as actual_price_dollars_per_mwh,
    actual.price_dollars_per_mwh > {{ var('spike_threshold') }} as actual_is_spike,
    yesterday.price_dollars_per_mwh as naive_forecast_price_dollars_per_mwh,
    aemo.aemo_forecast_price_dollars_per_mwh,
    abs(yesterday.price_dollars_per_mwh - actual.price_dollars_per_mwh) as naive_abs_error,
    abs(aemo.aemo_forecast_price_dollars_per_mwh - actual.price_dollars_per_mwh) as aemo_abs_error
from {{ ref('forecast_grid') }} as grid
left join {{ ref('prices_half_hourly') }} as actual
    on grid.target_time = actual.target_time
left join {{ ref('prices_half_hourly') }} as yesterday
    on grid.target_time - interval '24 hours' = yesterday.target_time
left join {{ ref('aemo_baseline') }} as aemo
    on grid.issue_time = aemo.issue_time
    and grid.target_time = aemo.target_time
