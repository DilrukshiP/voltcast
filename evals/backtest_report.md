# Backtest report: median price model

This file is written by `python -m voltcast.evals.backtest_report`. Do not edit it by hand.

Walk-forward backtest for Victoria (VIC1), 2024-08 to 2026-06. A new model was trained for each of the 23 months, on data from before that month only.

## Summary

- Forecasts compared: 743,880
- Mean absolute error: model 31.25, AEMO pre-dispatch 53.00, same time yesterday 63.66
- Change in mean absolute error: -41.0% against AEMO, -50.9% against same time yesterday
- Median absolute error: model 14.40, AEMO 15.64 (-8.0%)
- Months in which the model has a lower mean error than AEMO: 23 of 23

Errors are in dollars per MWh. A negative change means the model's error is lower.

## By horizon

| Horizon | Forecasts compared | Naive MAE | AEMO MAE | Model MAE | Naive median | AEMO median | Model median |
|---|---|---|---|---|---|---|---|
| 0.5 to 4 hours | 133,932 | 62.99 | 31.99 | 28.56 | 33.13 | 11.99 | 12.61 |
| 4.5 to 12 hours | 265,656 | 63.16 | 48.83 | 30.82 | 33.17 | 15.32 | 14.48 |
| 12.5 to 16 hours | 131,724 | 63.30 | 52.44 | 31.49 | 33.21 | 16.32 | 14.71 |
| 16.5 to 24 hours | 212,568 | 64.92 | 71.79 | 33.32 | 33.24 | 18.39 | 15.31 |
| All horizons | 743,880 | 63.66 | 53.00 | 31.25 | 33.19 | 15.64 | 14.40 |

## By month

| Test month | Forecasts compared | Naive MAE | AEMO MAE | Model MAE | Model against AEMO |
|---|---|---|---|---|---|
| 2024-08 | 33,000 | 179.10 | 171.11 | 89.19 | -47.9% |
| 2024-09 | 31,920 | 42.03 | 32.97 | 17.85 | -45.9% |
| 2024-10 | 33,000 | 46.40 | 30.39 | 25.17 | -17.2% |
| 2024-11 | 31,920 | 60.96 | 49.86 | 30.58 | -38.7% |
| 2024-12 | 33,000 | 50.44 | 60.59 | 27.38 | -54.8% |
| 2025-01 | 33,000 | 49.52 | 29.97 | 24.64 | -17.8% |
| 2025-02 | 29,760 | 69.66 | 109.75 | 33.22 | -69.7% |
| 2025-03 | 33,000 | 45.46 | 25.52 | 20.31 | -20.4% |
| 2025-04 | 31,920 | 42.64 | 41.21 | 21.85 | -47.0% |
| 2025-05 | 33,000 | 41.06 | 34.89 | 20.23 | -42.0% |
| 2025-06 | 31,920 | 305.58 | 278.74 | 167.79 | -39.8% |
| 2025-07 | 33,000 | 62.25 | 44.69 | 26.29 | -41.2% |
| 2025-08 | 33,000 | 52.34 | 47.07 | 26.08 | -44.6% |
| 2025-09 | 31,920 | 55.98 | 48.64 | 23.55 | -51.6% |
| 2025-10 | 33,000 | 54.68 | 38.45 | 23.55 | -38.7% |
| 2025-11 | 31,920 | 43.82 | 24.17 | 21.11 | -12.7% |
| 2025-12 | 33,000 | 39.88 | 29.25 | 19.79 | -32.3% |
| 2026-01 | 33,000 | 44.50 | 24.18 | 20.84 | -13.8% |
| 2026-02 | 29,760 | 34.65 | 22.42 | 19.04 | -15.1% |
| 2026-03 | 33,000 | 30.97 | 15.46 | 13.97 | -9.6% |
| 2026-04 | 31,920 | 36.68 | 16.00 | 13.61 | -14.9% |
| 2026-05 | 33,000 | 39.26 | 21.42 | 16.25 | -24.2% |
| 2026-06 | 31,920 | 37.80 | 27.90 | 17.50 | -37.3% |

## By market state

A spike is a half hour with an actual price above 300 dollars per MWh.

| Market state | Forecasts compared | Naive MAE | AEMO MAE | Model MAE | Model against AEMO |
|---|---|---|---|---|---|
| No spike | 738,971 | 51.72 | 37.35 | 21.79 | -41.6% |
| Spike | 4,909 | 1,860.37 | 2,408.88 | 1,454.27 | -39.6% |

## How to read this report

- Naive: the actual price at the same time one day earlier.
- AEMO: the pre-dispatch forecast from the newest run published before the issue time.
- Model: the VoltCast median model.
- Only forecasts that AEMO covers are compared, so all three use the same rows.
- The final holdout period is not part of this report.
