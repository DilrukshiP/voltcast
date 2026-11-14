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
