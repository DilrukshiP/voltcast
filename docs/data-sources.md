# VoltCast Data Sources

This document records what we learned in the data checks (steps 0.7a, 0.7b and 0.7c). The check scripts are in `scripts/`. All three checks used August 2026 data for Victoria.

## One clock for the whole system

Every time in VoltCast is in **market time**: UTC+10 all year, with no daylight saving. AEMO uses this clock for all regions, including Victoria. Victorian clock time is one hour ahead of it during daylight saving.

## 1. Actual prices and demand

| Item | Value |
|---|---|
| Provider | AEMO, monthly archive on NEMWEB |
| How we download | The `nemosis` library |
| Tables | `DISPATCHPRICE` (price), `DISPATCHREGIONSUM` (demand) |
| Columns we use | `SETTLEMENTDATE`, `REGIONID`, `INTERVENTION`, `RRP`, `TOTALDEMAND` |
| Resolution | 5 minutes |
| Filters | `REGIONID` is `VIC1`, `INTERVENTION` is 0 |

Findings:

- One week had 2016 rows with no gaps, duplicates or missing values.
- `SETTLEMENTDATE` is the end of the interval. The first interval of a day is marked 00:05.
- Negative prices are normal. The check week had a minimum of -60.00 dollars per MWh.
- The library also downloads the month before the start date.
- Our target, the 30-minute price, is the average of six 5-minute prices.
- Known simplification: during rare AEMO interventions a second set of rows exists (`INTERVENTION` is 1). We keep the normal market run for both price and demand. For demand, the other run is slightly more exact in those periods.
- Saved files: one Parquet file per month in `data/raw/actuals/`, with the columns `region`, `interval_end`, `price` and `demand`. A month is saved only if it passes every quality check.

## 2. AEMO pre-dispatch price forecasts

| Item | Value |
|---|---|
| Provider | AEMO, monthly archive on NEMWEB, folder `PREDISP_ALL_DATA` |
| How we download | Our own code with `requests`. It reads the folder page and finds links that contain the table name. |
| Table | `PREDISPATCHPRICE` |
| Columns we use | `PREDISPATCHSEQNO` (run id), `REGIONID`, `INTERVENTION`, `RRP`, `DATETIME`, `LASTCHANGED` |
| Resolution | A new run every 30 minutes, one row per forecast half hour |
| Our names | `DATETIME` becomes `target_time`, `LASTCHANGED` becomes `published_at` |

Findings:

- One month is one zip file of 5.6 MB. It held all 1488 runs (31 days times 48 runs).
- Every run is kept. One target time had up to 79 forecasts made at different times.
- A run is published about 1.5 minutes after the half hour starts.
- Monthly files start at 04:00, because the AEMO market day runs from 04:00 to 04:00.
- **A run covers only 16 to 39.5 hours ahead.** Our horizon is 24 hours, so at some issue times AEMO has no forecast for our last hours.
- Forecast prices can be extreme. The check month had a maximum of 22985.96 dollars per MWh.

Decisions:

- We do not use the `nemseer` library. Its last release was in 2023 and it does not support Python 3.12 or newer.
- We find files by reading the folder page, because AEMO changed its file names in August 2024 and may change them again.
- We compare with the AEMO baseline only on rows where an AEMO forecast exists, and we report the share of rows covered.

## 3. Weather forecasts

| Item | Value |
|---|---|
| Provider | Open-Meteo, Previous Runs API (free for non-commercial use, no API key) |
| How we download | Our own code with `requests` |
| Location | Melbourne, latitude -37.81, longitude 144.96 |
| Variables | `temperature_2m`, `wind_speed_10m`, `shortwave_radiation` |
| Version we use | Columns ending in `_previous_day1`: the forecast made one day before the target hour |
| Resolution | 1 hour |
| Timezone setting | `Australia/Brisbane`, which is the same clock as market time |
| History | From January 2024 |

Findings:

- One week had 168 rows with no gaps or missing values.
- The day-ahead forecast differs from the newest value (mean difference 0.46 degrees for temperature). So it is a real older forecast.

Decisions:

- We use the day-ahead columns because a forecast made 24 hours before the target hour always exists at our issue time. It cannot contain future data.
- We do not use the Historical Forecast API, because it returns the newest model runs, which are fresher than what we would have had at the issue time.
- Weather is hourly and prices are half-hourly. Both half hours of an hour get the same weather value.

## Summary

| Source | Publish time available | History | Main limit |
|---|---|---|---|
| Actual prices and demand | Yes, the interval end | Many years | None found |
| AEMO pre-dispatch | Yes, `LASTCHANGED` | Many years | Covers 16 to 39.5 hours ahead, not always 24 |
| Weather forecasts | Fixed at one day before the target | From January 2024 | Older than needed for short horizons |

The shortest history is the weather source, so the earliest possible start of our training data is January 2024.
