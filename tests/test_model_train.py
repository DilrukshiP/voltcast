"""Tests for the training code. They use a small made-up table, so they run in seconds."""

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from voltcast.model.columns import FEATURE_COLUMNS, TARGET_COLUMN
from voltcast.model.train import (
    TrainingConfig,
    predict,
    to_model_inputs,
    train_median_model,
)

FLAG_COLUMNS = ["aemo_has_forecast", "is_weekend", "is_public_holiday"]
SMALL_CONFIG = TrainingConfig(
    num_leaves=7, min_data_in_leaf=10, max_rounds=60, early_stopping_rounds=10, tuning_days=5
)


def made_up_table(days: int = 30) -> pd.DataFrame:
    """Hourly issue times with 4 targets each. The price depends on two of the inputs."""
    random = np.random.default_rng(7)
    rows = [
        {"issue_time": issue_time, "target_time": issue_time + step * pd.Timedelta(minutes=30)}
        for issue_time in pd.date_range("2025-01-01", periods=days * 24, freq="h")
        for step in range(1, 5)
    ]
    table = pd.DataFrame(rows)
    for column in FEATURE_COLUMNS:
        table[column] = random.normal(0.0, 1.0, len(table))
    for column in FLAG_COLUMNS:
        table[column] = random.random(len(table)) > 0.5
    table[TARGET_COLUMN] = (
        60.0
        + 20.0 * table["price_last"]
        + 10.0 * table["temperature_c"]
        + random.normal(0.0, 1.0, len(table))
    )
    return table


def test_model_inputs_are_the_listed_columns_in_order_with_numbers_only() -> None:
    inputs = to_model_inputs(made_up_table(days=1))
    assert list(inputs.columns) == FEATURE_COLUMNS
    assert TARGET_COLUMN not in inputs.columns
    assert not any(inputs[column].dtype == bool for column in inputs.columns)
    assert set(inputs["is_weekend"].unique()) <= {0, 1}


def test_training_learns_the_pattern_in_the_data() -> None:
    table = made_up_table()
    model = train_median_model(table, SMALL_CONFIG)

    forecast = predict(model.booster, table)
    model_error = (forecast - table[TARGET_COLUMN]).abs().mean()
    constant_error = (table[TARGET_COLUMN].median() - table[TARGET_COLUMN]).abs().mean()

    assert 1 <= model.rounds <= SMALL_CONFIG.max_rounds
    assert model.training_rows == len(table)
    assert model.tuning_mae > 0
    assert model_error < 0.5 * constant_error


def test_training_twice_gives_the_same_forecasts() -> None:
    table = made_up_table(days=20)
    first = predict(train_median_model(table, SMALL_CONFIG).booster, table)
    second = predict(train_median_model(table, SMALL_CONFIG).booster, table)
    pd.testing.assert_series_equal(first, second)


def test_too_little_data_for_a_tuning_period_is_rejected() -> None:
    with pytest.raises(ValueError, match="not enough data"):
        train_median_model(made_up_table(days=2), SMALL_CONFIG)


def test_config_rejects_impossible_values() -> None:
    with pytest.raises(ValidationError):
        TrainingConfig(learning_rate=0.0)
    with pytest.raises(ValidationError):
        TrainingConfig(feature_fraction=1.5)
