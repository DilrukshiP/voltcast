"""Walk-forward backtest of the median model.

The backtest repeats one experiment for every month of the backtest period:

1. Train a new model on all forecasts whose answers were known before the month starts.
2. Forecast that month.
3. Keep the forecasts, beside the actual price and both baselines.

So every forecast in the result was made by a model that had never seen that month.

Run from the repository root, after `dbt build`:

    python -m voltcast.evals.backtest
"""

import logging
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from voltcast.config import Settings, get_settings
from voltcast.evals.scores import score_by_horizon
from voltcast.ingestion.periods import month_bounds, months_between
from voltcast.model.columns import KEY_COLUMNS, TARGET_COLUMN
from voltcast.model.data import load_development_table, split_by_time
from voltcast.model.train import TrainingConfig, predict, train_median_model

logger = logging.getLogger(__name__)

PREDICTION_COLUMNS: list[str] = [
    "test_month",
    *KEY_COLUMNS,
    "horizon_steps",
    TARGET_COLUMN,
    "naive_forecast_price",
    "aemo_forecast_price",
    "model_forecast_price",
]


class Fold(NamedTuple):
    """One test month. The model for it is trained on everything known before `start`."""

    start: pd.Timestamp
    end: pd.Timestamp

    @property
    def label(self) -> str:
        return f"{self.start:%Y-%m}"


def monthly_folds(first_month: date, period_end: date) -> list[Fold]:
    """Return one fold for every full month from `first_month` up to `period_end`."""
    last_day = pd.Timestamp(period_end) - pd.Timedelta(days=1)
    months = months_between((first_month.year, first_month.month), (last_day.year, last_day.month))
    folds = [Fold(*map(pd.Timestamp, month_bounds(year, month))) for year, month in months]
    return [fold for fold in folds if fold.end <= pd.Timestamp(period_end)]


def run_backtest(table: pd.DataFrame, folds: list[Fold], config: TrainingConfig) -> pd.DataFrame:
    """Train and forecast once per fold, and return all forecasts in one table."""
    parts: list[pd.DataFrame] = []
    for fold in folds:
        training, test = split_by_time(table, fold.start.to_pydatetime(), fold.end.to_pydatetime())
        model = train_median_model(training, config)
        part = test[[*KEY_COLUMNS, "horizon_steps", TARGET_COLUMN, "aemo_forecast_price"]].copy()
        part["test_month"] = fold.label
        part["naive_forecast_price"] = test["price_1d_ago"]
        part["model_forecast_price"] = predict(model.booster, test)
        parts.append(part[PREDICTION_COLUMNS])
        logger.info(
            "%s: trained on %d rows in %d rounds, forecast %d rows",
            fold.label,
            len(training),
            model.rounds,
            len(test),
        )
    return pd.concat(parts, ignore_index=True)


def predictions_path(settings: Settings) -> Path:
    """Where the backtest forecasts are saved."""
    return settings.data_dir / "backtest" / "median_predictions.parquet"


def score_predictions(predictions: pd.DataFrame) -> pd.DataFrame:
    """Compare the three forecasts by horizon, on the rows that all three cover."""
    forecasts = {
        "naive": predictions["naive_forecast_price"],
        "aemo": predictions["aemo_forecast_price"],
        "model": predictions["model_forecast_price"],
    }
    return score_by_horizon(predictions[TARGET_COLUMN], predictions["horizon_steps"], forecasts)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    folds = monthly_folds(settings.backtest_start, settings.holdout_start)
    logger.info("Backtest over %d months: %s to %s", len(folds), folds[0].label, folds[-1].label)

    predictions = run_backtest(load_development_table(settings), folds, TrainingConfig())

    path = predictions_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(path, index=False)

    print(f"\nBacktest period: {folds[0].label} to {folds[-1].label}, {len(folds)} models")
    print("Errors in dollars per MWh, on the forecasts that AEMO covers:\n")
    print(score_predictions(predictions).round(2).to_string(index=False))
    print(f"\nForecasts saved to {path}")


if __name__ == "__main__":
    main()
