"""Backtest report: turn the saved backtest forecasts into `evals/backtest_report.md`.

Run from the repository root, after `python -m voltcast.evals.backtest`:

    python -m voltcast.evals.backtest_report

All numbers use only the forecasts that AEMO covers, so the three forecasts
are always compared on exactly the same rows.
"""

import logging
from pathlib import Path

import pandas as pd

from voltcast.config import get_settings
from voltcast.evals.backtest import predictions_path, score_predictions
from voltcast.evals.baselines import SPIKE_THRESHOLD
from voltcast.model.columns import TARGET_COLUMN
from voltcast.model.tracking import log_run
from voltcast.model.train import flatten_scores

logger = logging.getLogger(__name__)

REPORT_PATH: Path = Path("evals/backtest_report.md")
EXPERIMENT_NAME: str = "median_backtest"
FORECASTS: list[str] = ["naive", "aemo", "model"]
GROUP_TABLE_HEADER: str = (
    "Forecasts compared | Naive MAE | AEMO MAE | Model MAE | Model against AEMO |"
)


def absolute_errors(predictions: pd.DataFrame) -> pd.DataFrame:
    """Return the absolute error of each forecast, for the rows that AEMO covers."""
    covered = predictions.loc[predictions["aemo_forecast_price"].notna()]
    errors = pd.DataFrame(
        {
            "test_month": covered["test_month"],
            "is_spike": covered[TARGET_COLUMN] > SPIKE_THRESHOLD,
        }
    )
    for name in FORECASTS:
        errors[name] = (covered[f"{name}_forecast_price"] - covered[TARGET_COLUMN]).abs()
    return errors


def score_groups(errors: pd.DataFrame, group_column: str) -> pd.DataFrame:
    """Return the number of forecasts and the mean error of each forecast, per group."""
    grouped = errors.groupby(group_column)
    table = grouped[FORECASTS].mean().add_suffix("_mae")
    table.insert(0, "forecasts", grouped.size())
    table["model_vs_aemo"] = table["model_mae"] / table["aemo_mae"] - 1.0
    return table.reset_index()


def headline(errors: pd.DataFrame, by_month: pd.DataFrame) -> dict[str, float]:
    """Return the few numbers that summarise the whole backtest."""
    means = errors[FORECASTS].mean()
    medians = errors[FORECASTS].median()
    return {
        "months": float(len(by_month)),
        "forecasts": float(len(errors)),
        "naive_mae": float(means["naive"]),
        "aemo_mae": float(means["aemo"]),
        "model_mae": float(means["model"]),
        "aemo_median": float(medians["aemo"]),
        "model_median": float(medians["model"]),
        "mae_change_vs_aemo": float(means["model"] / means["aemo"] - 1.0),
        "mae_change_vs_naive": float(means["model"] / means["naive"] - 1.0),
        "median_change_vs_aemo": float(medians["model"] / medians["aemo"] - 1.0),
        "months_model_beats_aemo": float((by_month["model_mae"] < by_month["aemo_mae"]).sum()),
        "months_model_beats_naive": float((by_month["model_mae"] < by_month["naive_mae"]).sum()),
    }


def render_report(
    summary: dict[str, float],
    by_horizon: pd.DataFrame,
    by_month: pd.DataFrame,
    by_state: pd.DataFrame,
) -> str:
    """Build the report text in Markdown."""
    months = int(summary["months"])
    first_month, last_month = by_month["test_month"].min(), by_month["test_month"].max()
    lines: list[str] = [
        "# Backtest report: median price model",
        "",
        "This file is written by `python -m voltcast.evals.backtest_report`. "
        "Do not edit it by hand.",
        "",
        f"Walk-forward backtest for Victoria (VIC1), {first_month} to {last_month}. "
        f"A new model was trained for each of the {months} months, "
        "on data from before that month only.",
        "",
        "## Summary",
        "",
        f"- Forecasts compared: {summary['forecasts']:,.0f}",
        f"- Mean absolute error: model {summary['model_mae']:.2f}, "
        f"AEMO pre-dispatch {summary['aemo_mae']:.2f}, same time yesterday "
        f"{summary['naive_mae']:.2f}",
        f"- Change in mean absolute error: {summary['mae_change_vs_aemo']:+.1%} against AEMO, "
        f"{summary['mae_change_vs_naive']:+.1%} against same time yesterday",
        f"- Median absolute error: model {summary['model_median']:.2f}, "
        f"AEMO {summary['aemo_median']:.2f} ({summary['median_change_vs_aemo']:+.1%})",
        f"- Months in which the model has a lower mean error than AEMO: "
        f"{summary['months_model_beats_aemo']:.0f} of {months}",
        "",
        "Errors are in dollars per MWh. A negative change means the model's error is lower.",
        "",
        "## By horizon",
        "",
        "| Horizon | Forecasts compared | Naive MAE | AEMO MAE | Model MAE "
        "| Naive median | AEMO median | Model median |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for line in by_horizon.itertuples(index=False):
        lines.append(
            f"| {line.horizon} | {line.compared:,} | {line.naive_mae:,.2f} | {line.aemo_mae:,.2f} "
            f"| {line.model_mae:,.2f} | {line.naive_median:,.2f} | {line.aemo_median:,.2f} "
            f"| {line.model_median:,.2f} |"
        )
    lines += [
        "",
        "## By month",
        "",
        "| Test month | " + GROUP_TABLE_HEADER,
        "|---|---|---|---|---|---|",
    ]
    for line in by_month.itertuples(index=False):
        lines.append(
            f"| {line.test_month} | {line.forecasts:,} | {line.naive_mae:,.2f} "
            f"| {line.aemo_mae:,.2f} | {line.model_mae:,.2f} | {line.model_vs_aemo:+.1%} |"
        )
    lines += [
        "",
        "## By market state",
        "",
        "A spike is a half hour with an actual price above "
        f"{SPIKE_THRESHOLD:,.0f} dollars per MWh.",
        "",
        "| Market state | " + GROUP_TABLE_HEADER,
        "|---|---|---|---|---|---|",
    ]
    for line in by_state.itertuples(index=False):
        state = "Spike" if line.is_spike else "No spike"
        lines.append(
            f"| {state} | {line.forecasts:,} | {line.naive_mae:,.2f} | {line.aemo_mae:,.2f} "
            f"| {line.model_mae:,.2f} | {line.model_vs_aemo:+.1%} |"
        )
    lines += [
        "",
        "## How to read this report",
        "",
        "- Naive: the actual price at the same time one day earlier.",
        "- AEMO: the pre-dispatch forecast from the newest run published before the issue time.",
        "- Model: the VoltCast median model.",
        "- Only forecasts that AEMO covers are compared, so all three use the same rows.",
        "- The final holdout period is not part of this report.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    predictions = pd.read_parquet(predictions_path(settings))

    errors = absolute_errors(predictions)
    by_horizon = score_predictions(predictions)
    by_month = score_groups(errors, "test_month")
    by_state = score_groups(errors, "is_spike")
    summary = headline(errors, by_month)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(summary, by_horizon, by_month, by_state), encoding="utf-8")
    logger.info("Wrote %s", REPORT_PATH)

    run_id = log_run(
        settings,
        EXPERIMENT_NAME,
        run_name=f"{by_month['test_month'].min()} to {by_month['test_month'].max()}",
        parameters={
            "first_test_month": by_month["test_month"].min(),
            "last_test_month": by_month["test_month"].max(),
            "holdout_start": settings.holdout_start,
        },
        metrics={**summary, **flatten_scores(by_horizon)},
        files=[REPORT_PATH],
    )
    logger.info("Recorded in MLflow with id %s", run_id)


if __name__ == "__main__":
    main()
