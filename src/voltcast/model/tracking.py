"""Record training runs with MLflow, in a local database inside the data folder.

To look at the recorded runs in a browser, run from the repository root:

    mlflow ui --backend-store-uri sqlite:///data/mlflow.db --port 5001

and open http://127.0.0.1:5001
"""

from collections.abc import Mapping
from pathlib import Path

import mlflow

from voltcast.config import Settings


def ensure_experiment(settings: Settings, name: str) -> str:
    """Point MLflow at the local database and return the id of the named experiment.

    The experiment is created on first use, with its files inside the data folder.
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    experiment = mlflow.get_experiment_by_name(name)
    if experiment is not None:
        return str(experiment.experiment_id)
    return mlflow.create_experiment(name, artifact_location=settings.mlflow_artifact_dir.as_uri())


def log_run(
    settings: Settings,
    experiment_name: str,
    run_name: str,
    parameters: Mapping[str, object],
    metrics: Mapping[str, float],
    files: list[Path],
) -> str:
    """Record one run: its settings, its results and its files. Return the run id."""
    experiment_id = ensure_experiment(settings, experiment_name)
    with mlflow.start_run(experiment_id=experiment_id, run_name=run_name) as run:
        mlflow.log_params(dict(parameters))
        mlflow.log_metrics(dict(metrics))
        for file in files:
            mlflow.log_artifact(str(file))
    return str(run.info.run_id)
