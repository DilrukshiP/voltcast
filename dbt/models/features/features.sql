-- The table that the model is trained on: one row per forecast in the grid,
-- with all 32 features and the value to predict.
--
-- `actual_price` is the answer. It is the only column here that comes from after
-- the issue time, and it must never be used as a model input.

select
    grid.issue_time,
    grid.target_time,
    grid.horizon_steps,

    -- the value to predict
    actual.price_dollars_per_mwh as actual_price,

    -- past prices and demand
    price_history.price_last,
    price_history.price_mean_3h,
    price_history.price_mean_24h,
    price_history.price_min_24h,
    price_history.price_max_24h,
    price_history.price_std_24h,
    price_history.price_mean_7d,
    price_history.demand_last,
    price_history.demand_mean_24h,
    price_history.price_1d_ago,
    price_history.price_2d_ago,
    price_history.price_7d_ago,
    price_history.demand_1d_ago,
    price_history.demand_7d_ago,

    -- AEMO pre-dispatch forecast
    aemo.aemo_forecast_price,
    aemo.aemo_has_forecast,
    aemo.aemo_forecast_price_previous_run,
    aemo.aemo_forecast_change,
    aemo.aemo_run_max_price,
    aemo.aemo_run_mean_price,
    aemo.aemo_run_steps_ahead,

    -- weather forecast
    weather.temperature_c,
    weather.wind_speed_kmh,
    weather.solar_radiation_wm2,
    weather.weather_lead_days,

    -- calendar
    calendar.half_hour_of_day,
    calendar.day_of_week,
    calendar.is_weekend,
    calendar.is_public_holiday,
    calendar.month_of_year,
    calendar.issue_hour
from {{ ref('forecast_grid') }} as grid
left join {{ ref('prices_half_hourly') }} as actual
    on grid.target_time = actual.target_time
left join {{ ref('feature_price_history') }} as price_history
    on grid.issue_time = price_history.issue_time
    and grid.target_time = price_history.target_time
left join {{ ref('feature_aemo') }} as aemo
    on grid.issue_time = aemo.issue_time
    and grid.target_time = aemo.target_time
left join {{ ref('feature_weather') }} as weather
    on grid.issue_time = weather.issue_time
    and grid.target_time = weather.target_time
left join {{ ref('feature_calendar') }} as calendar
    on grid.issue_time = calendar.issue_time
    and grid.target_time = calendar.target_time
