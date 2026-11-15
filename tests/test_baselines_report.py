"""Tests for the baseline report calculations."""

from datetime import date

import pandas as pd
import pytest

from voltcast.evals.baselines import (
    SUMMARY_COLUMNS,
    render_report,
    summarise_errors,
    summarise_prices,
)


def scores() -> pd.DataFrame:
    """Four forecasts. Steps 1 and 2 are covered by AEMO. Steps 40 and 41 are half covered."""
    return pd.DataFrame(
        {
            "horizon_steps": [1, 2, 40, 41],
            "naive_abs_error": [10.0, 30.0, 50.0, 70.0],
            "aemo_abs_error": [4.0, 6.0, 100.0, None],
        }
    )


def line(summary: pd.DataFrame, horizon: str) -> pd.Series:
    """Return the one summary line for a horizon group."""
    matching = summary.loc[summary["horizon"] == horizon]
    assert len(matching) == 1
    return matching.iloc[0]


def test_summary_has_one_line_per_horizon_group() -> None:
    summary = summarise_errors(scores())
    assert list(summary.columns) == SUMMARY_COLUMNS
    assert summary["horizon"].tolist() == [
        "0.5 to 4 hours",
        "4.5 to 12 hours",
        "12.5 to 16 hours",
        "16.5 to 24 hours",
        "All horizons",
    ]


def test_fully_covered_group_uses_all_rows() -> None:
    short = line(summarise_errors(scores()), "0.5 to 4 hours")
    assert short["rows"] == 2
    assert short["aemo_coverage"] == 1.0
    assert short["naive_mae"] == 20.0
    assert short["aemo_mae"] == 5.0


def test_half_covered_group_compares_on_covered_rows_only() -> None:
    long = line(summarise_errors(scores()), "16.5 to 24 hours")
    assert long["rows"] == 2
    assert long["aemo_coverage"] == 0.5
    assert long["naive_mae_all_rows"] == 60.0
    assert long["naive_mae"] == 50.0
    assert long["aemo_mae"] == 100.0


def test_all_horizons_line_reports_mean_and_median() -> None:
    everything = line(summarise_errors(scores()), "All horizons")
    assert everything["rows"] == 4
    assert everything["aemo_coverage"] == 0.75
    assert everything["naive_mae_all_rows"] == 40.0
    assert everything["naive_mae"] == 30.0
    assert everything["aemo_mae"] == pytest.approx(110.0 / 3)
    assert everything["naive_median"] == 30.0
    assert everything["aemo_median"] == 6.0


def test_price_summary_counts_spikes_and_negative_prices() -> None:
    prices = pd.DataFrame({"price_dollars_per_mwh": [-20.0, 50.0, 80.0, 300.0, 900.0]})
    summary = summarise_prices(prices)
    assert summary["half_hours"] == 5
    assert summary["median"] == 80.0
    assert summary["spikes"] == 1
    assert summary["negative"] == 1
    assert summary["highest"] == 900.0


def test_report_names_the_period_and_shows_the_numbers() -> None:
    prices = summarise_prices(pd.DataFrame({"price_dollars_per_mwh": [-20.0, 50.0, 900.0]}))
    report = render_report(summarise_errors(scores()), prices, date(2024, 2, 1), date(2026, 7, 1))
    assert "Development period: 2024-02-01 to 2026-07-01" in report
    assert "is the final holdout and is not used" in report
    assert "| 0.5 to 4 hours | 2 | 100.0% | 20.00 | 20.00 | 5.00 | 20.00 | 5.00 |" in report
    assert "| Spikes (above 300) | 1 (33.33%) |" in report
