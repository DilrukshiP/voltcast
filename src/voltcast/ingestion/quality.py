"""Shared error type for data quality checks."""


class DataQualityError(ValueError):
    """Raised when downloaded data fails a quality check."""
