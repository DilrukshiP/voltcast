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
