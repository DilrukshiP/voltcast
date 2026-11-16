"""Load the training table and split it by time.

Rows are never split at random. A forecast model is always used on dates after
its training data, so it must also be tested that way.
"""

from datetime import datetime

import duckdb
import pandas as pd

from voltcast.config import Settings
from voltcast.model.columns import FEATURE_COLUMNS, KEY_COLUMNS, TARGET_COLUMN

TABLE_COLUMNS: list[str] = [*KEY_COLUMNS, TARGET_COLUMN, *FEATURE_COLUMNS]


def load_development_table(settings: Settings) -> pd.DataFrame:
    """Read the training table up to the holdout. Rows of the holdout are never loaded."""
    query = f"""
        select {", ".join(TABLE_COLUMNS)}
        from features
        where target_time <= ?
        order by issue_time, target_time
    """
    with duckdb.connect(str(settings.warehouse_path), read_only=True) as connection:
        return connection.execute(query, [settings.holdout_start]).df()


def split_by_time(
    table: pd.DataFrame, validation_start: datetime, validation_end: datetime
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the table into a training part and a later validation part.

    Training rows: the answer was already known when validation starts,
    so `target_time` is at or before `validation_start`.
    Validation rows: the forecast was issued at or after `validation_start`,
    and its answer is at or before `validation_end`.

    Rows issued in the 24 hours before `validation_start` with a later target are
    in neither part. Their answers lie inside the validation period.
    """
    if validation_start >= validation_end:
        raise ValueError("validation_start must be before validation_end")
    is_training = table["target_time"] <= validation_start
    is_validation = (table["issue_time"] >= validation_start) & (
        table["target_time"] <= validation_end
    )
    return (
        table.loc[is_training].reset_index(drop=True),
        table.loc[is_validation].reset_index(drop=True),
    )
