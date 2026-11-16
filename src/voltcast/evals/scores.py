"""Compare several forecasts with the actual price, by horizon."""

from collections.abc import Mapping

import pandas as pd

from voltcast.evals.baselines import HORIZON_GROUPS


def score_by_horizon(
    actual: pd.Series, horizon_steps: pd.Series, forecasts: Mapping[str, pd.Series]
) -> pd.DataFrame:
    """Return the mean and median absolute error of each forecast, for each horizon group.

    Only rows where every forecast has a value are scored, so all forecasts
    are compared on exactly the same rows. `compared` is the number of such rows.
    """
    errors = pd.DataFrame({name: (values - actual).abs() for name, values in forecasts.items()})
    comparable = errors.notna().all(axis=1)

    lines: list[dict[str, object]] = []
    for group in HORIZON_GROUPS:
        in_group = horizon_steps.between(group.first_step, group.last_step)
        scored = errors.loc[in_group & comparable]
        line: dict[str, object] = {
            "horizon": group.label,
            "forecasts": int(in_group.sum()),
            "compared": len(scored),
        }
        for name in forecasts:
            line[f"{name}_mae"] = scored[name].mean()
        for name in forecasts:
            line[f"{name}_median"] = scored[name].median()
        lines.append(line)
    return pd.DataFrame(lines)
