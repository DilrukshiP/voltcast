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

Model results will be added here once the evaluation is complete.

The two baselines are already scored on the development period (February 2024 to June 2026). The full table is in [evals/baseline_report.md](evals/baseline_report.md).

| Baseline | Mean absolute error | Median absolute error |
|---|---|---|
| Same time yesterday | 64.81 | 33.57 |
| AEMO pre-dispatch | 70.36 | 17.10 |

Errors are in dollars per MWh, over all horizons from 0.5 to 24 hours, on the forecasts that AEMO covers.
