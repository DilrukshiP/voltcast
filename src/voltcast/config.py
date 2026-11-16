"""Project settings, read from environment variables and an optional `.env` file.

Every setting has a safe default, so the project runs without a `.env` file.
To change a value, set an environment variable with the prefix `VOLTCAST_`,
for example `VOLTCAST_DATA_DIR=/tmp/voltcast-data`.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Region = Literal["NSW1", "QLD1", "SA1", "TAS1", "VIC1"]

# The first full month in which all three sources are complete (see docs/data-sources.md).
# The weather archive has empty values until 20 January 2024.
EARLIEST_HISTORY_START: date = date(2024, 2, 1)


class Settings(BaseSettings):
    """All values that can differ between machines or runs."""

    model_config = SettingsConfigDict(
        env_prefix="VOLTCAST_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    region: Region = "VIC1"
    latitude: float = Field(default=-37.81, ge=-90, le=90)
    longitude: float = Field(default=144.96, ge=-180, le=180)
    market_timezone: str = "Australia/Brisbane"
    history_start: date = EARLIEST_HISTORY_START
    # From this date to the holdout, data is used to compare models, not to train them.
    validation_start: date = date(2026, 4, 1)
    # Data from this date on is the final holdout. It is scored once, at the end of the project.
    holdout_start: date = date(2026, 7, 1)
    data_dir: Path = Path("data")
    nemweb_archive_url: str = "https://www.nemweb.com.au/Data_Archive/Wholesale_Electricity/MMSDM"
    weather_api_url: str = "https://previous-runs-api.open-meteo.com/v1/forecast"
    request_timeout_seconds: int = Field(default=60, gt=0)

    @field_validator("history_start")
    @classmethod
    def history_start_is_supported(cls, value: date) -> date:
        """Reject a start date that is earlier than the weather history."""
        if value < EARLIEST_HISTORY_START:
            raise ValueError(f"history_start must be {EARLIEST_HISTORY_START} or later")
        return value

    @model_validator(mode="after")
    def periods_are_in_order(self) -> Self:
        """Reject periods that are not in the order history, validation, holdout."""
        if self.holdout_start <= self.history_start:
            raise ValueError("holdout_start must be after history_start")
        if not self.history_start < self.validation_start < self.holdout_start:
            raise ValueError("validation_start must be between history_start and holdout_start")
        return self

    @property
    def raw_dir(self) -> Path:
        """Folder for files exactly as downloaded."""
        return self.data_dir / "raw"

    @property
    def warehouse_path(self) -> Path:
        """The DuckDB file that dbt builds."""
        return self.data_dir / "voltcast.duckdb"

    @property
    def mlflow_tracking_uri(self) -> str:
        """Address of the local database in which MLflow records training runs."""
        return f"sqlite:///{(self.data_dir / 'mlflow.db').resolve()}"

    @property
    def mlflow_artifact_dir(self) -> Path:
        """Folder in which MLflow keeps the files of each run, such as the model."""
        return (self.data_dir / "mlartifacts").resolve()


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings object for the whole program."""
    return Settings()
