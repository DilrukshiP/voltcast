"""Baseline report: how large are the errors of the two baselines?

Run from the repository root, after `dbt build`:

    python -m voltcast.evals.baselines

The report covers the development period only. The final holdout is never read here.
"""

import logging
from datetime import date
from pathlib import Path
from typing import NamedTuple

import duckdb
import pandas as pd

from voltcast.config import Settings, get_settings

logger = logging.getLogger(__name__)

REPORT_PATH: Path = Path("evals/baseline_report.md")
SPIKE_THRESHOLD: float = 300.0


class HorizonGroup(NamedTuple):
    """A range of half-hour steps that is reported as one line."""

    label: str
    first_step: int
    last_step: int


HORIZON_GROUPS: list[HorizonGroup] = [
    HorizonGroup("0.5 to 4 hours", 1, 8),
    HorizonGroup("4.5 to 12 hours", 9, 24),
    HorizonGroup("12.5 to 16 hours", 25, 32),
    HorizonGroup("16.5 to 24 hours", 33, 48),
    HorizonGroup("All horizons", 1, 48),
]

SUMMARY_COLUMNS: list[str] = [
    "horizon",
    "rows",
    "aemo_coverage",
    "naive_mae_all_rows",
    "naive_mae",
    "aemo_mae",
    "naive_median",
    "aemo_median",
]


def load_scores(settings: Settings) -> pd.DataFrame:
    """Read the score table for the development period."""
    query = """
        select horizon_steps, naive_abs_error, aemo_abs_error
        from baseline_scores
        where target_time <= ?
    """
    with duckdb.connect(str(settings.warehouse_path), read_only=True) as connection:
        return connection.execute(query, [settings.holdout_start]).df()


def load_prices(settings: Settings) -> pd.DataFrame:
    """Read the half-hour prices for the development period."""
    query = """
        select target_time, price_dollars_per_mwh
        from prices_half_hourly
        where target_time > ? and target_time <= ?
    """
    with duckdb.connect(str(settings.warehouse_path), read_only=True) as connection:
        return connection.execute(query, [settings.history_start, settings.holdout_start]).df()


def summarise_errors(scores: pd.DataFrame) -> pd.DataFrame:
    """Return one line per horizon group with the errors of both baselines.

    `naive_mae_all_rows` uses every row. The other four error columns use only
    the rows where AEMO has a forecast, so both baselines are compared on the same rows.
    """
    lines: list[dict[str, object]] = []
    for group in HORIZON_GROUPS:
        in_group = scores["horizon_steps"].between(group.first_step, group.last_step)
        rows = scores.loc[in_group]
        covered = rows.loc[rows["aemo_abs_error"].notna()]
        lines.append(
            {
                "horizon": group.label,
                "rows": len(rows),
                "aemo_coverage": len(covered) / len(rows) if len(rows) else float("nan"),
                "naive_mae_all_rows": rows["naive_abs_error"].mean(),
                "naive_mae": covered["naive_abs_error"].mean(),
                "aemo_mae": covered["aemo_abs_error"].mean(),
                "naive_median": covered["naive_abs_error"].median(),
                "aemo_median": covered["aemo_abs_error"].median(),
            }
        )
    return pd.DataFrame(lines, columns=SUMMARY_COLUMNS)


def summarise_prices(prices: pd.DataFrame) -> dict[str, float]:
    """Return simple facts about the actual half-hour prices."""
    price = prices["price_dollars_per_mwh"]
    return {
        "half_hours": float(len(price)),
        "mean": float(price.mean()),
        "median": float(price.median()),
        "lowest": float(price.min()),
        "highest": float(price.max()),
        "spikes": float((price > SPIKE_THRESHOLD).sum()),
        "negative": float((price < 0).sum()),
    }


def render_report(
    errors: pd.DataFrame, prices: dict[str, float], history_start: date, holdout_start: date
) -> str:
    """Build the report text in Markdown."""
    half_hours = prices["half_hours"]
    lines: list[str] = [
        "# Baseline report",
        "",
        "This file is written by `python -m voltcast.evals.baselines`. Do not edit it by hand.",
        "",
        f"Development period: {history_start} to {holdout_start}, Victoria (VIC1).",
        f"Data from {holdout_start} on is the final holdout and is not used in this report.",
        "",
        "## Actual half-hour prices",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Half hours | {half_hours:,.0f} |",
        f"| Mean price | {prices['mean']:,.2f} |",
        f"| Median price | {prices['median']:,.2f} |",
        f"| Lowest price | {prices['lowest']:,.2f} |",
        f"| Highest price | {prices['highest']:,.2f} |",
        f"| Spikes (above {SPIKE_THRESHOLD:,.0f}) | {prices['spikes']:,.0f} "
        f"({prices['spikes'] / half_hours:.2%}) |",
        f"| Negative prices | {prices['negative']:,.0f} ({prices['negative'] / half_hours:.2%}) |",
        "",
        "Prices are in dollars per MWh.",
        "",
        "## Baseline errors by horizon",
        "",
        "| Horizon | Forecasts | AEMO coverage | Naive MAE, all rows | Naive MAE | AEMO MAE "
        "| Naive median | AEMO median |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for line in errors.itertuples(index=False):
        lines.append(
            f"| {line.horizon} | {line.rows:,} | {line.aemo_coverage:.1%} "
            f"| {line.naive_mae_all_rows:,.2f} | {line.naive_mae:,.2f} | {line.aemo_mae:,.2f} "
            f"| {line.naive_median:,.2f} | {line.aemo_median:,.2f} |"
        )
    lines += [
        "",
        "How to read this table:",
        "",
        "- An error is the absolute difference between a forecast and the actual price, "
        "in dollars per MWh.",
        "- MAE is the mean of the errors. The median is the middle error.",
        "- Naive: the actual price at the same time one day earlier.",
        "- AEMO: the pre-dispatch forecast from the newest run published before the issue time.",
        "- AEMO coverage: the share of forecasts for which AEMO gives a price.",
        "- The last four columns use only the forecasts that AEMO covers, "
        "so both baselines are compared on the same rows.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    errors = summarise_errors(load_scores(settings))
    prices = summarise_prices(load_prices(settings))
    report = render_report(errors, prices, settings.history_start, settings.holdout_start)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    logger.info("Wrote %s", REPORT_PATH)


if __name__ == "__main__":
    main()
