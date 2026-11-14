# VoltCast Architecture

This document holds the design diagrams. Each diagram answers one question.

## 1. System context

Question: what does VoltCast talk to, and who uses it?

```mermaid
flowchart LR
    aemo["AEMO NEMWEB<br/>(external system)<br/>actual prices, demand,<br/>pre-dispatch forecasts"]
    weather["Open-Meteo<br/>(external system)<br/>weather forecasts"]

    voltcast["VoltCast<br/>forecasts Victorian electricity<br/>prices for the next 24 hours"]

    consumer["Forecast user<br/>(battery operator or energy analyst)"]
    maintainer["Maintainer<br/>(ML engineer)"]

    aemo -- "market data, every hour" --> voltcast
    weather -- "weather forecasts, every hour" --> voltcast
    voltcast -- "price forecasts and accuracy scores<br/>(API and demo page)" --> consumer
    voltcast -- "error, drift and latency metrics<br/>(dashboards)" --> maintainer
    maintainer -- "code changes and model approval" --> voltcast
```

Notes:

- VoltCast only reads from AEMO and Open-Meteo. It never writes to them.
- Both data sources are public and free, so the system needs no paid data licence.
- The forecast user and the maintainer see different outputs. The user sees forecasts. The maintainer sees system health.

## 2. Components

Question: what parts are inside VoltCast, and how does data move between them?

```mermaid
flowchart TB
    aemo["AEMO NEMWEB"]
    weather["Open-Meteo"]

    subgraph pipeline["Data pipeline (run by Dagster)"]
        ingest["Ingestion<br/>Python"]
        raw[("Raw store<br/>Parquet files")]
        dbt["Transform and data tests<br/>dbt"]
        wh[("Warehouse<br/>DuckDB")]
    end

    subgraph ml["Machine learning"]
        train["Training<br/>LightGBM"]
        registry[("Model registry<br/>MLflow")]
        forecast["Forecast job"]
        score["Scoring job"]
        battery["Battery simulator"]
    end

    subgraph serve["Serving"]
        api["API<br/>FastAPI"]
        demo["Demo page<br/>Streamlit"]
    end

    subgraph ops["Operations"]
        gha["GitHub Actions<br/>CI and schedules"]
        prom["Prometheus"]
        graf["Grafana"]
    end

    aemo --> ingest
    weather --> ingest
    ingest --> raw
    raw --> dbt
    dbt --> wh

    wh -- "feature table" --> train
    train -- "candidate model" --> registry
    registry -- "approved model" --> forecast
    wh -- "latest features" --> forecast
    forecast -- "forecasts" --> wh
    wh -- "forecasts and actual prices" --> score
    score -- "errors" --> wh
    wh -- "forecasts and actual prices" --> battery
    battery -- "revenue results" --> wh

    wh --> api
    wh --> demo

    api -- "latency metrics" --> prom
    score -- "live error and drift metrics" --> prom
    prom --> graf

    gha -. "hourly run" .-> ingest
    gha -. "weekly retrain" .-> train
```

Notes:

- The warehouse is the centre. Every job reads from it and writes back to it, so jobs do not call each other directly.
- Raw files are kept unchanged. If a transform has a bug, we fix the dbt model and rebuild, without downloading again.
- Training and forecasting are separate jobs joined only by the model registry. A new model is used only after it is approved there.
- The API and the demo page only read. They never run the model during a request, so responses are fast.
- Solid lines show data. Dotted lines show triggers.

## 3. Hourly forecast run

Question: what happens, in order, during one hourly run?

In this diagram, T is the issue time. It is the moment the forecast is made.

```mermaid
sequenceDiagram
    participant S as Scheduler (GitHub Actions)
    participant I as Ingestion
    participant X as AEMO and Open-Meteo
    participant R as Raw store (Parquet)
    participant D as dbt
    participant W as Warehouse (DuckDB)
    participant F as Forecast job
    participant M as Model registry (MLflow)
    participant C as Scoring job

    S->>I: Start hourly run with issue time T
    I->>X: Request data published since the last run
    X-->>I: Prices, demand, pre-dispatch forecasts, weather forecasts
    I->>R: Save raw files with their publish time

    S->>D: Run transforms and data tests
    D->>R: Read raw files
    D->>W: Build feature rows for T using only inputs published before T

    alt Data tests pass
        S->>F: Run forecast
        F->>M: Load the approved model
        M-->>F: Model
        F->>W: Read feature rows for T
        F->>W: Write 48 forecasts, from T plus 30 minutes to T plus 24 hours

        S->>C: Run scoring
        C->>W: Read past forecasts whose target time now has an actual price
        C->>W: Write errors for those forecasts
    else Data tests fail
        D-->>S: Report failure
        Note over S,W: The run stops. The last good forecast stays in the warehouse.
    end
```

Notes:

- Every raw file is saved with its publish time. This is what makes the rule "no future data" possible to check.
- Data tests run before the model. Bad input stops the run, so the model never produces a forecast from broken data.
- If a run fails, the API still serves the last good forecast. An old forecast is better than a wrong one.
- Scoring always looks backward. A forecast made at T can be fully scored only 24 hours later, when all 48 actual prices exist.

## 4. Data model

Question: what tables does the warehouse hold, and how do they join?

Three time columns appear in many tables:

- `published_at`: when the source made the value public.
- `issue_time`: when VoltCast makes a forecast.
- `target_time`: the end of the half hour that a value describes.

```mermaid
erDiagram
    ACTUAL_PRICES {
        string region PK
        timestamp target_time PK
        float price
        float demand
        timestamp published_at
    }
    AEMO_PREDISPATCH {
        string region PK
        timestamp published_at PK
        timestamp target_time PK
        float forecast_price
        float forecast_demand
    }
    WEATHER_FORECASTS {
        string location PK
        timestamp published_at PK
        timestamp target_time PK
        float temperature
        float wind_speed
        float solar_radiation
    }
    FEATURES {
        string region PK
        timestamp issue_time PK
        timestamp target_time PK
        int horizon_steps
        float price_lag_features
        float aemo_forecast_price
        float weather_features
        float calendar_features
    }
    MODEL_VERSIONS {
        string model_version PK
        timestamp trained_at
        timestamp training_data_end
        string status
    }
    FORECASTS {
        string model_version PK
        string region PK
        timestamp issue_time PK
        timestamp target_time PK
        float price_p10
        float price_p50
        float price_p90
        float spike_probability
    }
    FORECAST_SCORES {
        string model_version PK
        string region PK
        timestamp issue_time PK
        timestamp target_time PK
        float actual_price
        float model_abs_error
        float aemo_abs_error
        float naive_abs_error
    }

    ACTUAL_PRICES ||--o{ FEATURES : "gives past prices to"
    AEMO_PREDISPATCH ||--o{ FEATURES : "gives latest run before issue_time to"
    WEATHER_FORECASTS ||--o{ FEATURES : "gives latest run before issue_time to"
    FEATURES ||--o{ FORECASTS : "is input for"
    MODEL_VERSIONS ||--o{ FORECASTS : "produces"
    FORECASTS ||--o| FORECAST_SCORES : "is scored in"
    ACTUAL_PRICES ||--o{ FORECAST_SCORES : "gives the real price to"
```

Notes:

- The two forecast source tables keep every run, not only the newest one. For one `target_time` there are many rows, one for each `published_at`.
- A feature row may use a source row only when `published_at` is earlier than `issue_time`. This join condition is the "no future data" rule written as SQL.
- One forecast row is one model, one issue time and one target time. So a single hourly run writes 48 rows.
- `FORECAST_SCORES` stores the model error beside both baseline errors for the same row, so every comparison uses exactly the same half hours.
- In `FEATURES`, the four columns ending in `_features` stand for groups of columns. The real names will be set in Sprint 2.
- Column names may change after the data check in step 0.7, when we see the real source files.
