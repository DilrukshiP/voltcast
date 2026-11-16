"""Train the median price model and compare it with the baselines on the validation period.

Run from the repository root, after `dbt build`:

    python -m voltcast.model.train
"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import NamedTuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from voltcast.config import Settings, get_settings
from voltcast.evals.scores import score_by_horizon
from voltcast.model.columns import FEATURE_COLUMNS, TARGET_COLUMN
from voltcast.model.data import load_development_table, split_by_time
from voltcast.model.tracking import log_run

logger = logging.getLogger(__name__)

EXPERIMENT_NAME: str = "median_model"


class TrainingConfig(BaseModel):
    """Every value that shapes a training run. Recorded with each run."""

    model_config = ConfigDict(frozen=True)

    learning_rate: float = Field(default=0.05, gt=0, le=1)
    num_leaves: int = Field(default=63, ge=2)
    min_data_in_leaf: int = Field(default=200, ge=1)
    feature_fraction: float = Field(default=0.8, gt=0, le=1)
    bagging_fraction: float = Field(default=0.8, gt=0, le=1)
    max_rounds: int = Field(default=3000, ge=1)
    early_stopping_rounds: int = Field(default=50, ge=1)
    # The last days of the training period are held back to decide when to stop.
    tuning_days: int = Field(default=60, ge=1)
    seed: int = 42

    def lightgbm_parameters(
        self, quantile: float | None = None
    ) -> dict[str, float | int | str | bool]:
        """Return the settings in the names that LightGBM uses.

        Without `quantile`, the model predicts the median. With `quantile`, for example 0.9,
        it predicts the price that the actual price stays below in 90% of cases.
        """
        if quantile is None:
            # "l1" means absolute error. A model trained on it predicts the median.
            goal: dict[str, float | int | str | bool] = {"objective": "l1", "metric": "l1"}
        else:
            if not 0 < quantile < 1:
                raise ValueError("quantile must be between 0 and 1")
            goal = {"objective": "quantile", "alpha": quantile, "metric": "quantile"}
        return {
            **goal,
            "learning_rate": self.learning_rate,
            "num_leaves": self.num_leaves,
            "min_data_in_leaf": self.min_data_in_leaf,
            "feature_fraction": self.feature_fraction,
            "bagging_fraction": self.bagging_fraction,
            "bagging_freq": 1,
            "seed": self.seed,
            "deterministic": True,
            "force_row_wise": True,
            "verbose": -1,
        }


class TrainedModel(NamedTuple):
    """A trained model and the facts about how it was trained."""

    booster: lgb.Booster
    rounds: int
    # The error on the tuning period: absolute error for the median, pinball loss for a quantile.
    tuning_loss: float
    training_rows: int


def to_model_inputs(table: pd.DataFrame) -> pd.DataFrame:
    """Return only the allowed input columns, in a fixed order, with true/false as 1/0."""
    inputs = table[FEATURE_COLUMNS]
    flags = [column for column in FEATURE_COLUMNS if inputs[column].dtype == bool]
    return inputs.astype(dict.fromkeys(flags, "int8"))


def as_datetime(day: date) -> datetime:
    """Midnight at the start of a day."""
    return datetime.combine(day, datetime.min.time())


def train_price_model(
    training: pd.DataFrame, config: TrainingConfig, quantile: float | None = None
) -> TrainedModel:
    """Train a model for the median price, or for a quantile of the price, in two passes.

    Pass 1 trains on the early part of the data and watches the error on the last
    `tuning_days`. It stops when that error no longer improves. This gives the number of rounds.
    Pass 2 trains on all the data for that number of rounds, so the newest days are also used.
    """
    parameters = config.lightgbm_parameters(quantile)
    period_end = pd.Timestamp(training["target_time"].max()).to_pydatetime()
    tuning_start = period_end - timedelta(days=config.tuning_days)
    early, tuning = split_by_time(training, tuning_start, period_end)
    if early.empty or tuning.empty:
        raise ValueError("not enough data to hold back a tuning period")

    early_data = lgb.Dataset(to_model_inputs(early), early[TARGET_COLUMN])
    tuning_data = lgb.Dataset(to_model_inputs(tuning), tuning[TARGET_COLUMN], reference=early_data)
    first_pass = lgb.train(
        parameters,
        early_data,
        num_boost_round=config.max_rounds,
        valid_sets=[tuning_data],
        valid_names=["tuning"],
        callbacks=[lgb.early_stopping(config.early_stopping_rounds, verbose=False)],
    )
    rounds = first_pass.best_iteration
    tuning_loss = float(first_pass.best_score["tuning"][str(parameters["metric"])])

    all_data = lgb.Dataset(to_model_inputs(training), training[TARGET_COLUMN])
    booster = lgb.train(parameters, all_data, num_boost_round=rounds)
    return TrainedModel(booster, rounds, tuning_loss, len(training))


def train_median_model(training: pd.DataFrame, config: TrainingConfig) -> TrainedModel:
    """Train the model for the median price."""
    return train_price_model(training, config)


def predict(booster: lgb.Booster, table: pd.DataFrame) -> pd.Series:
    """Forecast the price in dollars per MWh for every row of the table."""
    values = np.asarray(booster.predict(to_model_inputs(table)), dtype=float)
    return pd.Series(values, index=table.index, name="model_forecast_price")


def model_path(settings: Settings) -> Path:
    """Where the trained median model is saved."""
    return settings.data_dir / "models" / "median_model.txt"


def flatten_scores(scores: pd.DataFrame) -> dict[str, float]:
    """Turn the score table into one name per number, for example `model_mae/all_horizons`."""
    flat: dict[str, float] = {}
    error_columns = [
        str(name) for name in scores.columns if str(name).endswith(("_mae", "_median"))
    ]
    for _, line in scores.iterrows():
        horizon = str(line["horizon"]).lower().replace(" ", "_")
        for column in error_columns:
            flat[f"{column}/{horizon}"] = float(line[column])
    return flat


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    config = TrainingConfig()

    table = load_development_table(settings)
    training, validation = split_by_time(
        table, as_datetime(settings.validation_start), as_datetime(settings.holdout_start)
    )
    logger.info("Training rows: %d, validation rows: %d", len(training), len(validation))

    model = train_median_model(training, config)
    logger.info("Rounds: %d, MAE on the tuning period: %.2f", model.rounds, model.tuning_loss)

    forecasts = {
        "naive": validation["price_1d_ago"],
        "aemo": validation["aemo_forecast_price"],
        "model": predict(model.booster, validation),
    }
    scores = score_by_horizon(validation[TARGET_COLUMN], validation["horizon_steps"], forecasts)
    model_mae_all_rows = float((forecasts["model"] - validation[TARGET_COLUMN]).abs().mean())

    path = model_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    model.booster.save_model(str(path))

    run_id = log_run(
        settings,
        EXPERIMENT_NAME,
        run_name=f"validation from {settings.validation_start}",
        parameters={
            **config.model_dump(),
            "history_start": settings.history_start,
            "validation_start": settings.validation_start,
            "holdout_start": settings.holdout_start,
            "training_rows": model.training_rows,
            "validation_rows": len(validation),
            "feature_count": len(FEATURE_COLUMNS),
            "rounds": model.rounds,
        },
        metrics={
            "tuning_mae": model.tuning_loss,
            "model_mae_all_rows": model_mae_all_rows,
            **flatten_scores(scores),
        },
        files=[path],
    )

    print(f"\nValidation period: {settings.validation_start} to {settings.holdout_start}")
    print("Errors in dollars per MWh, on the forecasts that AEMO covers:\n")
    print(scores.round(2).to_string(index=False))
    print(f"\nModel MAE on all {len(validation):,} validation forecasts: {model_mae_all_rows:.2f}")
    print(f"Model saved to {path}")
    print(f"Run recorded in MLflow with id {run_id}")


if __name__ == "__main__":
    main()
