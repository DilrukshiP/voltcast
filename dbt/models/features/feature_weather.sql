-- Weather forecast features for every row of the forecast grid.
--
-- Weather is hourly and the grid is half-hourly. Both half hours inside one clock hour
-- get the value of that hour. Example: the half hours ending 10:30 and 11:00
-- both get the weather value for 10:00.
--
-- Which forecast version is used depends on how far ahead the target is:
--   up to 12 hours ahead:  the forecast made about one day before the target
--   more than 12 hours:    the forecast made about two days before the target
-- This keeps every value older than the issue time, with a margin of several hours.

with grid as (
    select
        issue_time,
        target_time,
        horizon_steps,
        date_trunc('hour', target_time - interval '30 minutes') as weather_time,
        case
            when horizon_steps <= {{ var('weather_day1_max_steps') }} then 1
            else 2
        end as weather_lead_days
    from {{ ref('forecast_grid') }}
)

select
    grid.issue_time,
    grid.target_time,
    grid.horizon_steps,
    grid.weather_lead_days,
    case
        when grid.weather_lead_days = 1 then weather.temperature_c_day1
        else weather.temperature_c_day2
    end as temperature_c,
    case
        when grid.weather_lead_days = 1 then weather.wind_speed_kmh_day1
        else weather.wind_speed_kmh_day2
    end as wind_speed_kmh,
    case
        when grid.weather_lead_days = 1 then weather.solar_radiation_wm2_day1
        else weather.solar_radiation_wm2_day2
    end as solar_radiation_wm2
from grid
left join {{ ref('stg_weather') }} as weather
    on grid.weather_time = weather.target_time
