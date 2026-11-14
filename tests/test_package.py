"""Smoke test: the package can be imported and reports its version."""

import voltcast


def test_package_has_version() -> None:
    assert voltcast.__version__ == "0.1.0"
