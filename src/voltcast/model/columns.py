"""The columns of the training table `features`, by role.

Only the columns in `FEATURE_COLUMNS` may be given to a model as inputs.
"""

KEY_COLUMNS: list[str] = ["issue_time", "target_time"]

# The value to predict. It comes from after the issue time, so it is never an input.
TARGET_COLUMN: str = "actual_price"

FEATURE_COLUMNS: list[str] = [
    "horizon_steps",
    # past prices and demand
    "price_last",
    "price_mean_3h",
    "price_mean_24h",
    "price_min_24h",
    "price_max_24h",
    "price_std_24h",
    "price_mean_7d",
    "demand_last",
    "demand_mean_24h",
    "price_1d_ago",
    "price_2d_ago",
    "price_7d_ago",
    "demand_1d_ago",
    "demand_7d_ago",
    # AEMO pre-dispatch forecast
    "aemo_forecast_price",
    "aemo_has_forecast",
    "aemo_forecast_price_previous_run",
    "aemo_forecast_change",
    "aemo_run_max_price",
    "aemo_run_mean_price",
    "aemo_run_steps_ahead",
    # weather forecast
    "temperature_c",
    "wind_speed_kmh",
    "solar_radiation_wm2",
    "weather_lead_days",
    # calendar
    "half_hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_public_holiday",
    "month_of_year",
    "issue_hour",
]
