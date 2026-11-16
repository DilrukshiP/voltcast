"""Tests for the backtest report calculations."""

import pandas as pd
import pytest

from voltcast.evals.backtest import score_predictions
from voltcast.evals.backtest_report import (
    absolute_errors,
    headline,
    render_report,
    score_band,
    score_groups,
)


def predictions() -> pd.DataFrame:
    """Five forecasts in two months. One has a spike, and one is not covered by AEMO."""
    return pd.DataFrame(
        {
            "test_month": ["2025-01", "2025-01", "2025-02", "2025-02", "2025-02"],
            "horizon_steps": [1, 2, 1, 2, 40],
            "actual_price": [100.0, 100.0, 1000.0, 100.0, 100.0],
            "naive_forecast_price": [140.0, 60.0, 100.0, 180.0, 100.0],
            "aemo_forecast_price": [110.0, 90.0, 600.0, 120.0, None],
            "model_forecast_price": [105.0, 95.0, 800.0, 90.0, 100.0],
        }
    )


def test_errors_leave_out_rows_that_aemo_does_not_cover() -> None:
    errors = absolute_errors(predictions())
    assert len(errors) == 4
    assert errors["model"].tolist() == [5.0, 5.0, 200.0, 10.0]
    assert errors["is_spike"].tolist() == [False, False, True, False]


def test_scores_by_month() -> None:
    by_month = score_groups(absolute_errors(predictions()), "test_month").set_index("test_month")
    assert by_month.loc["2025-01", "forecasts"] == 2
    assert by_month.loc["2025-01", "aemo_mae"] == 10.0
    assert by_month.loc["2025-01", "model_mae"] == 5.0
    assert by_month.loc["2025-01", "model_vs_aemo"] == pytest.approx(-0.5)
    assert by_month.loc["2025-02", "naive_mae"] == 490.0


def test_scores_by_market_state() -> None:
    by_state = score_groups(absolute_errors(predictions()), "is_spike").set_index("is_spike")
    assert by_state.loc[True, "forecasts"] == 1
    assert by_state.loc[True, "aemo_mae"] == 400.0
    assert by_state.loc[True, "model_mae"] == 200.0
    assert by_state.loc[False, "forecasts"] == 3


def test_headline_numbers() -> None:
    errors = absolute_errors(predictions())
    summary = headline(errors, score_groups(errors, "test_month"))
    assert summary["months"] == 2
    assert summary["forecasts"] == 4
    assert summary["aemo_mae"] == 110.0
    assert summary["model_mae"] == 55.0
    assert summary["mae_change_vs_aemo"] == pytest.approx(-0.5)
    assert summary["months_model_beats_aemo"] == 2


def test_report_shows_the_summary_and_all_three_views() -> None:
    data = predictions()
    errors = absolute_errors(data)
    by_month = score_groups(errors, "test_month")
    report = render_report(
        headline(errors, by_month),
        score_predictions(data),
        by_month,
        score_groups(errors, "is_spike"),
    )
    assert "2025-01 to 2025-02" in report
    assert "-50.0% against AEMO" in report
    assert "lower mean error than AEMO: 2 of 2" in report
    assert "| 2025-01 | 2 | 40.00 | 10.00 | 5.00 | -50.0% |" in report
    assert "| Spike | 1 | 900.00 | 400.00 | 200.00 | -50.0% |" in report


def predictions_with_band() -> pd.DataFrame:
    """The same five forecasts with a band. Row 3 is a spike far above its band."""
    data = predictions()
    data["model_low_price"] = [90.0, 101.0, 700.0, 80.0, 50.0]
    data["model_high_price"] = [120.0, 130.0, 900.0, 95.0, 150.0]
    return data


def test_band_scores_by_horizon_and_market_state() -> None:
    band = score_band(predictions_with_band()).set_index("group")
    # Actual prices: 100 inside 90-120, 100 below 101-130, 1000 above 700-900,
    # 100 above 80-95, 100 inside 50-150.
    everything = band.loc["All horizons"]
    assert everything["forecasts"] == 5
    assert everything["inside"] == pytest.approx(0.4)
    assert everything["below_low"] == pytest.approx(0.2)
    assert everything["above_high"] == pytest.approx(0.4)
    assert everything["mean_width"] == pytest.approx((30 + 29 + 200 + 15 + 100) / 5)
    assert band.loc["Spike", "forecasts"] == 1
    assert band.loc["Spike", "above_high"] == 1.0
    assert band.loc["No spike", "forecasts"] == 4


def test_report_has_the_band_section_only_when_a_band_is_given() -> None:
    data = predictions_with_band()
    errors = absolute_errors(data)
    by_month = score_groups(errors, "test_month")
    parts = (
        headline(errors, by_month),
        score_predictions(data),
        by_month,
        score_groups(errors, "is_spike"),
    )
    without_band = render_report(*parts)
    with_band = render_report(*parts, score_band(data))
    assert "## Uncertainty band" not in without_band
    assert "## Uncertainty band" in with_band
    assert "10% of actual prices below it, 80% inside it and 10% above it" in with_band
    assert "| Spike | 1 | 0.0% | 0.0% | 100.0% | 200.00 | 200.00 |" in with_band
