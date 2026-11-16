-- Features from past prices and demand, for every row of the forecast grid.
-- Every value here comes from a half hour that had already ended at the issue time.
--
-- Part 1, "recent" features: one set of values per issue time, the same for all 48 steps.
--   They describe the market up to and including the half hour that ends at the issue time.
-- Part 2, "same time" features: the value at the same time of day 1, 2 and 7 days before
--   the target. The newest of these, 1 day before, ends at or before the issue time
--   for every step from 1 to 48.
--
-- The windows count rows, so they need a price table with no gaps.
-- The test prices_half_hourly_has_no_gaps guarantees that.

with prices as (
    select
        target_time,
        price_dollars_per_mwh as price,
        demand_mw as demand
    from {{ ref('prices_half_hourly') }}
),

recent as (
    select
        target_time as known_at,
        price as price_last,
        avg(price) over last_3_hours as price_mean_3h,
        avg(price) over last_24_hours as price_mean_24h,
        min(price) over last_24_hours as price_min_24h,
        max(price) over last_24_hours as price_max_24h,
        stddev_samp(price) over last_24_hours as price_std_24h,
        avg(price) over last_7_days as price_mean_7d,
        demand as demand_last,
        avg(demand) over last_24_hours as demand_mean_24h,
        count(*) over last_7_days as half_hours_in_7d_window
    from prices
    window
        last_3_hours as (order by target_time rows between 5 preceding and current row),
        last_24_hours as (order by target_time rows between 47 preceding and current row),
        last_7_days as (order by target_time rows between 335 preceding and current row)
)

select
    grid.issue_time,
    grid.target_time,
    grid.horizon_steps,
    recent.price_last,
    recent.price_mean_3h,
    recent.price_mean_24h,
    recent.price_min_24h,
    recent.price_max_24h,
    recent.price_std_24h,
    recent.price_mean_7d,
    recent.demand_last,
    recent.demand_mean_24h,
    recent.half_hours_in_7d_window,
    one_day_ago.price as price_1d_ago,
    two_days_ago.price as price_2d_ago,
    seven_days_ago.price as price_7d_ago,
    one_day_ago.demand as demand_1d_ago,
    seven_days_ago.demand as demand_7d_ago
from {{ ref('forecast_grid') }} as grid
left join recent
    on grid.issue_time = recent.known_at
left join prices as one_day_ago
    on grid.target_time - interval '1 day' = one_day_ago.target_time
left join prices as two_days_ago
    on grid.target_time - interval '2 days' = two_days_ago.target_time
left join prices as seven_days_ago
    on grid.target_time - interval '7 days' = seven_days_ago.target_time
