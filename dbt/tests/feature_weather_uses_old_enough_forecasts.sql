-- The "no future data" rule for weather.
-- A target more than 12 hours ahead must use the two-day forecast, never the one-day forecast.
-- The test also checks that the value in the table really is the version it claims to be.
-- It returns the rows that break either rule. It passes when it returns no rows.

select
    features.issue_time,
    features.target_time,
    features.horizon_steps,
    features.weather_lead_days
from {{ ref('feature_weather') }} as features
inner join {{ ref('stg_weather') }} as weather
    on date_trunc('hour', features.target_time - interval '30 minutes') = weather.target_time
where (features.horizon_steps > 24 and features.weather_lead_days != 2)
   or (features.weather_lead_days = 1 and features.temperature_c != weather.temperature_c_day1)
   or (features.weather_lead_days = 2 and features.temperature_c != weather.temperature_c_day2)
