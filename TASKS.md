# VoltCast Tasks

One step at a time. A box is ticked only after the step is verified.

## Sprint 0: Setup and design

- [x] 0.1 Repository basics: `.gitignore`, starter `README.md`, `TASKS.md`
- [x] 0.2 Python environment: `venv`, `pyproject.toml`, package folder, first passing `pytest`
- [x] 0.3 Diagram 1: system context
- [x] 0.4 Diagram 2: components
- [x] 0.5 Diagram 3: hourly forecast run (sequence)
- [x] 0.6 Diagram 4: data model
- [x] 0.7 Day 1 data check: download one week of each data source for VIC
  - [x] 0.7a Actual prices and demand (NEMOSIS)
  - [x] 0.7b AEMO pre-dispatch forecasts
  - [x] 0.7c Weather forecasts
- [x] 0.8 Record data findings in `docs/data-sources.md`

## Sprint 1: Data and baselines

- [x] 1.1 Settings with `pydantic` and `.env.example`
- [x] 1.2 Ingest actual prices and demand
  - [x] 1.2a Transform and quality checks, with tests
  - [x] 1.2b Download, save to the raw store, command to run it
- [x] 1.3 Ingest AEMO pre-dispatch forecasts
  - [x] 1.3a Transform and quality checks, with tests
  - [x] 1.3b Download, save to the raw store, command to run it
- [x] 1.4 Ingest weather forecasts
  - [x] 1.4a Response model, transform and quality checks, with tests
  - [x] 1.4b Download, save to the raw store, command to run it
- [x] 1.4c Backfill command for a range of months
- [x] 1.4d Full history backfill (January 2024 to September 2026)
- [x] 1.5 dbt staging models and data tests
  - [x] 1.5a dbt project with DuckDB and the staging model for actuals
  - [x] 1.5b Staging models for pre-dispatch and weather
  - [x] 1.5c Half-hour price table
- [x] 1.6 Score the two baselines
  - [x] 1.6a Forecast grid and AEMO baseline table
  - [x] 1.6b Naive baseline and score table
  - [x] 1.6c Baseline report with MAE by horizon

## Sprint 2: Model and evals

- [ ] 2.1 Feature table and leakage test
  - [x] 2.1a Price and demand history features
  - [ ] 2.1b AEMO forecast features
  - [ ] 2.1c Weather and calendar features
  - [ ] 2.1d One feature table, and a leakage test that changes future data
- [ ] 2.2 LightGBM median model with MLflow tracking
- [ ] 2.3 Quantile models and spike classifier
- [ ] 2.4 Walk-forward backtest and generated report

## Sprint 3: Production system

- [ ] 3.1 Battery simulator
- [ ] 3.2 FastAPI service
- [ ] 3.3 Dockerfile and Docker Compose
- [ ] 3.4 CI with tests and eval gate
- [ ] 3.5 Dagster jobs, hourly forecast and weekly retrain
- [ ] 3.6 Prometheus and Grafana monitoring

## Sprint 4: Live demo and story

- [ ] 4.1 Streamlit demo with live scoreboard
- [ ] 4.2 Final holdout scored once
- [ ] 4.3 README with results, diagrams and limits
- [ ] 4.4 Demo video
