-- One row per hour. Each variable has two versions:
-- `day1` is the forecast made about one day before the target hour,
-- `day2` is the forecast made about two days before.

select
    target_time,
    temperature_day1 as temperature_c_day1,
    temperature_day2 as temperature_c_day2,
    wind_speed_day1 as wind_speed_kmh_day1,
    wind_speed_day2 as wind_speed_kmh_day2,
    solar_radiation_day1 as solar_radiation_wm2_day1,
    solar_radiation_day2 as solar_radiation_wm2_day2
from {{ source('raw', 'weather') }}
