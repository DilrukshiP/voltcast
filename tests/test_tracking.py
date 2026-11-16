"""Tests for recording runs with MLflow. Each test uses its own temporary database."""

from pathlib import Path

import mlflow
import pandas as pd

from voltcast.config import Settings
from voltcast.model.tracking import log_run
from voltcast.model.train import flatten_scores


def make_settings(data_dir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=data_dir)


def record(settings: Settings, model_file: Path, mae: float) -> str:
    return log_run(
        settings,
        "test_experiment",
        run_name="a run",
        parameters={"learning_rate": 0.05, "validation_start": "2026-04-01"},
        metrics={"model_mae/all_horizons": mae},
        files=[model_file],
    )


def test_run_is_recorded_with_settings_results_and_file(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data")
    model_file = tmp_path / "median_model.txt"
    model_file.write_text("a model")

    run_id = record(settings, model_file, mae=15.97)

    run = mlflow.MlflowClient(settings.mlflow_tracking_uri).get_run(run_id)
    assert run.data.params == {"learning_rate": "0.05", "validation_start": "2026-04-01"}
    assert run.data.metrics == {"model_mae/all_horizons": 15.97}
    saved = list(settings.mlflow_artifact_dir.rglob("median_model.txt"))
    assert len(saved) == 1
    assert saved[0].read_text() == "a model"


def test_everything_is_stored_inside_the_data_folder(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data")
    model_file = tmp_path / "median_model.txt"
    model_file.write_text("a model")

    record(settings, model_file, mae=15.97)

    assert (settings.data_dir / "mlflow.db").exists()
    assert settings.mlflow_artifact_dir.is_relative_to(settings.data_dir.resolve())


def test_second_run_goes_into_the_same_experiment(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "data")
    model_file = tmp_path / "median_model.txt"
    model_file.write_text("a model")

    first = record(settings, model_file, mae=15.97)
    second = record(settings, model_file, mae=15.50)

    client = mlflow.MlflowClient(settings.mlflow_tracking_uri)
    experiment = client.get_experiment_by_name("test_experiment")
    assert experiment is not None
    runs = client.search_runs([experiment.experiment_id])
    assert {run.info.run_id for run in runs} == {first, second}


def test_flatten_scores_gives_one_name_per_number() -> None:
    scores = pd.DataFrame(
        [
            {
                "horizon": "0.5 to 4 hours",
                "forecasts": 10,
                "model_mae": 13.19,
                "model_median": 8.22,
            },
            {"horizon": "All horizons", "forecasts": 40, "model_mae": 15.97, "model_median": 10.25},
        ]
    )
    assert flatten_scores(scores) == {
        "model_mae/0.5_to_4_hours": 13.19,
        "model_median/0.5_to_4_hours": 8.22,
        "model_mae/all_horizons": 15.97,
        "model_median/all_horizons": 10.25,
    }
