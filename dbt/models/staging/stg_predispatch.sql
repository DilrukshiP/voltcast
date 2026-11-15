-- One row per AEMO forecast run and target half hour.
-- `horizon_minutes` is how far ahead the forecast looks: target_time minus published_at.

select
    region,
    run_id,
    published_at,
    target_time,
    date_diff('minute', published_at, target_time) as horizon_minutes,
    forecast_price as forecast_price_dollars_per_mwh
from {{ source('raw', 'predispatch') }}
