"""Shared pytest fixtures and options for CLI smoke and golden tests."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add command-line flags used by the test suite."""
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Regenerate tests/golden snapshots from current generator output.",
    )


@pytest.fixture
def update_golden(request: pytest.FixtureRequest) -> bool:
    """Return whether golden snapshots should be refreshed."""
    return bool(request.config.getoption("--update-golden"))


@pytest.fixture
def run_cli() -> Callable[..., subprocess.CompletedProcess[str]]:
    """Run the package CLI module and capture text output."""

    def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "mcp_toolsmith.cli", *args],
            check=False,
            capture_output=True,
            text=True,
        )

    return _run_cli
