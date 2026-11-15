# Baseline report

This file is written by `python -m voltcast.evals.baselines`. Do not edit it by hand.

Development period: 2024-02-01 to 2026-07-01, Victoria (VIC1).
Data from 2026-07-01 on is the final holdout and is not used in this report.

## Actual half-hour prices

| Measure | Value |
|---|---|
| Half hours | 42,288 |
| Mean price | 75.74 |
| Median price | 61.34 |
| Lowest price | -463.45 |
| Highest price | 16,600.00 |
| Spikes (above 300) | 411 (0.97%) |
| Negative prices | 9,791 (23.15%) |

Prices are in dollars per MWh.

## Baseline errors by horizon

| Horizon | Forecasts | AEMO coverage | Naive MAE, all rows | Naive MAE | AEMO MAE | Naive median | AEMO median |
|---|---|---|---|---|---|---|---|
| 0.5 to 4 hours | 169,140 | 100.0% | 64.17 | 64.17 | 40.52 | 33.56 | 13.18 |
| 4.5 to 12 hours | 338,184 | 100.0% | 64.18 | 64.18 | 66.77 | 33.56 | 16.75 |
| 12.5 to 16 hours | 169,044 | 100.0% | 64.19 | 64.19 | 71.65 | 33.57 | 17.79 |
| 16.5 to 24 hours | 337,992 | 81.3% | 64.21 | 66.34 | 92.38 | 33.60 | 20.11 |
| All horizons | 1,014,360 | 93.8% | 64.19 | 64.81 | 70.36 | 33.57 | 17.10 |

How to read this table:

- An error is the absolute difference between a forecast and the actual price, in dollars per MWh.
- MAE is the mean of the errors. The median is the middle error.
- Naive: the actual price at the same time one day earlier.
- AEMO: the pre-dispatch forecast from the newest run published before the issue time.
- AEMO coverage: the share of forecasts for which AEMO gives a price.
- The last four columns use only the forecasts that AEMO covers, so both baselines are compared on the same rows.
