# VoltCast

VoltCast forecasts Victorian wholesale electricity prices for the next 24 hours, using AEMO market data and weather forecasts.

**Status:** in development. See [TASKS.md](TASKS.md) for progress.

## What it will do

- Download actual prices, AEMO's own forecasts and weather forecasts every hour
- Forecast the 30-minute price for the next 24 hours, with an uncertainty band
- Detect price spikes above $300 per MWh
- Measure forecast value in dollars with a battery trading simulator
- Compare every result with two baselines: AEMO pre-dispatch and "same time yesterday"

## Planned stack

Python, DuckDB, dbt, Dagster, LightGBM, MLflow, FastAPI, Docker, Prometheus, Grafana, GitHub Actions.

## Results

In a 23-month walk-forward backtest (August 2024 to June 2026), a new model was trained for each month on earlier data only. Errors are in dollars per MWh, on 743,880 forecasts from 0.5 to 24 hours ahead.

| Forecast | Mean absolute error | Median absolute error |
|---|---|---|
| Same time yesterday | 63.66 | 33.19 |
| AEMO pre-dispatch | 53.00 | 15.64 |
| VoltCast median model | 31.25 | 14.40 |

- The model's mean absolute error is 41.0% lower than AEMO's pre-dispatch forecast and 50.9% lower than "same time yesterday".
- The model has a lower mean error than AEMO in 23 of 23 months.
- Known limit: in the first 4 hours, AEMO's median error is lower than the model's (11.99 against 12.61), and all three forecasts have large errors during real price spikes.

Full tables by horizon, month and market state: [evals/backtest_report.md](evals/backtest_report.md). Baselines on the whole development period: [evals/baseline_report.md](evals/baseline_report.md).

The final holdout period (from July 2026) has not been scored yet.
