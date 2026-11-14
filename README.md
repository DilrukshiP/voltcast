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

Results will be added here once the evaluation is complete.
