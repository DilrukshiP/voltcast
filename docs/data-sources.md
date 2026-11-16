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
- Saved files: one Parquet file per month in `data/raw/predispatch/`, with the columns `region`, `run_id`, `published_at`, `target_time` and `forecast_price`. The downloaded zip files are kept in `data/raw/predispatch/archive/`.
- File names before August 2024 use an older style. The code accepts both styles, but the older style is confirmed only by documentation until we download those months.

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
| Versions we keep | Columns ending in `_previous_day1` and `_previous_day2`: the forecasts made about one and two days before the target hour |
| Resolution | 1 hour |
| Timezone setting | `Australia/Brisbane`, which is the same clock as market time |
| History | Complete from 20 January 2024. We use it from 1 February 2024. |

Findings:

- One week had 168 rows with no gaps or missing values.
- The day-ahead forecast differs from the newest value (mean difference 0.46 degrees for temperature). So it is a real older forecast.

Decisions:

- We keep the one-day and two-day versions and never the newest value. A weather model run becomes public some hours after it starts. So for a target almost 24 hours ahead, the one-day version may not have been public yet at our issue time. The feature model `feature_weather` uses the one-day version for targets up to 12 hours ahead and the two-day version beyond that, so no feature can contain future data.
- The reason for 12 hours: the one-day version comes from a run that started at least 24 hours before the target. If a run needs up to 8 hours to become public, it is public at least 16 hours before the target. We use it only up to 12 hours ahead, which leaves a margin of 4 hours. The 8 hours is our assumption, not a published figure.
- We do not use the Historical Forecast API, because it returns the newest model runs, which are fresher than what we would have had at the issue time.
- Weather is hourly and prices are half-hourly. Both half hours of an hour get the same weather value.

## Summary

| Source | Publish time available | History | Main limit |
|---|---|---|---|
| Actual prices and demand | Yes, the interval end | Many years | None found |
| AEMO pre-dispatch | Yes, `LASTCHANGED` | Many years | Covers 16 to 39.5 hours ahead, not always 24 |
| Weather forecasts | About one and two days before the target | Complete from 20 January 2024 | Older than needed for short horizons |

The shortest history is the weather source, so our training data starts on 1 February 2024.

## Full history backfill (step 1.4d)

We ran the backfill for January 2024 to September 2026, which is 33 months and 99 month files.

| Source | Months saved | Result |
|---|---|---|
| Actual prices and demand | 33 of 33 | Every month passed all checks |
| AEMO pre-dispatch | 33 of 33 | Every month passed all checks. Two months have missing runs. |
| Weather forecasts | 32 of 33 | January 2024 was rejected |

Findings:

- The seven pre-dispatch files from before August 2024 use the old file name style (`PUBLIC_DVD_...`). They downloaded and passed every check, so the old style is now confirmed on real data.
- September 2024 has 1438 pre-dispatch runs out of 1440, and November 2024 has 1439. AEMO did not publish 3 runs. The months are saved, and those issue times will have no AEMO forecast.
- Weather for January 2024 has empty values in 454 of 744 hours for the one-day forecast and 478 hours for the two-day forecast. The archive is complete from 20 January 2024.

Decisions:

- The first month of our history is February 2024. This is the first full month in which all three sources are complete. The setting `history_start` enforces it.
- The January 2024 files for actuals and pre-dispatch are kept. Features for the first days of February need prices from the days before.
- The whole raw store is 434 MB. About 200 MB is the NEMOSIS cache and about 200 MB is the AEMO pre-dispatch zip files.
