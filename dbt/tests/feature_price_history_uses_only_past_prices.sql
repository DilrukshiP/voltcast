-- The "no future data" rule for the recent price features.
-- This test calculates three features a second time, in the plainest possible way:
-- with an explicit filter that keeps only half hours that ended at or before the issue time.
-- If the model used any later half hour, its values would differ from these.
-- The test returns the issue times where they differ. It passes when it returns no rows.

with issue_times as (
    select distinct
        issue_time,
        price_mean_24h,
        price_max_24h,
        price_mean_7d
    from {{ ref('feature_price_history') }}
),

recalculated as (
    select
        issue_times.issue_time,
        avg(prices.price_dollars_per_mwh) filter (
            where prices.target_time > issue_times.issue_time - interval '24 hours'
        ) as price_mean_24h,
        max(prices.price_dollars_per_mwh) filter (
            where prices.target_time > issue_times.issue_time - interval '24 hours'
        ) as price_max_24h,
        avg(prices.price_dollars_per_mwh) as price_mean_7d
    from issue_times
    inner join {{ ref('prices_half_hourly') }} as prices
        on prices.target_time <= issue_times.issue_time
        and prices.target_time > issue_times.issue_time - interval '7 days'
    group by issue_times.issue_time
)

select
    issue_times.issue_time,
    issue_times.price_mean_24h,
    recalculated.price_mean_24h as recalculated_price_mean_24h
from issue_times
inner join recalculated
    on issue_times.issue_time = recalculated.issue_time
where abs(issue_times.price_mean_24h - recalculated.price_mean_24h) > 0.000001
   or abs(issue_times.price_max_24h - recalculated.price_max_24h) > 0.000001
   or abs(issue_times.price_mean_7d - recalculated.price_mean_7d) > 0.000001
