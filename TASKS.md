# VoltCast Tasks

One step at a time. A box is ticked only after the step is verified.

## Sprint 0: Setup and design

- [x] 0.1 Repository basics: `.gitignore`, starter `README.md`, `TASKS.md`
- [x] 0.2 Python environment: `venv`, `pyproject.toml`, package folder, first passing `pytest`
- [x] 0.3 Diagram 1: system context
- [x] 0.4 Diagram 2: components
- [ ] 0.5 Diagram 3: hourly forecast run (sequence)
- [ ] 0.6 Diagram 4: data model
- [ ] 0.7 Day 1 data check: download one week of each data source for VIC

## Sprint 1: Data and baselines

- [ ] 1.1 Settings with `pydantic` and `.env.example`
- [ ] 1.2 Ingest actual prices and demand
- [ ] 1.3 Ingest AEMO pre-dispatch forecasts
- [ ] 1.4 Ingest weather forecasts
- [ ] 1.5 dbt staging models and data tests
- [ ] 1.6 Score the two baselines

## Sprint 2: Model and evals

- [ ] 2.1 Feature table and leakage test
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
