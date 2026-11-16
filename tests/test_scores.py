"""Tests for the forecast comparison by horizon."""

import pandas as pd

from voltcast.evals.scores import score_by_horizon


def example() -> pd.DataFrame:
    """Four rows. The last row has no value from forecast `b`."""
    return pd.DataFrame(
        {
            "horizon_steps": [1, 2, 40, 41],
            "actual": [100.0, 100.0, 100.0, 100.0],
            "a": [110.0, 130.0, 150.0, 170.0],
            "b": [96.0, 106.0, 0.0, None],
        }
    )


def scores() -> pd.DataFrame:
    data = example()
    return score_by_horizon(data["actual"], data["horizon_steps"], {"a": data["a"], "b": data["b"]})


def line(table: pd.DataFrame, horizon: str) -> pd.Series:
    matching = table.loc[table["horizon"] == horizon]
    assert len(matching) == 1
    return matching.iloc[0]


def test_columns_are_named_after_the_forecasts() -> None:
    assert list(scores().columns) == [
        "horizon",
        "forecasts",
        "compared",
        "a_mae",
        "b_mae",
        "a_median",
        "b_median",
    ]


def test_group_where_every_forecast_has_a_value() -> None:
    short = line(scores(), "0.5 to 4 hours")
    assert short["forecasts"] == 2
    assert short["compared"] == 2
    assert short["a_mae"] == 20.0
    assert short["b_mae"] == 5.0


def test_row_with_a_missing_forecast_is_left_out_for_all_forecasts() -> None:
    long = line(scores(), "16.5 to 24 hours")
    assert long["forecasts"] == 2
    assert long["compared"] == 1
    assert long["a_mae"] == 50.0
    assert long["b_mae"] == 100.0


def test_all_horizons_line() -> None:
    everything = line(scores(), "All horizons")
    assert everything["compared"] == 3
    assert everything["a_mae"] == 30.0
    assert everything["a_median"] == 30.0
    assert everything["b_median"] == 6.0
