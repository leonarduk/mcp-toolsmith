"""Shared pytest fixtures for CLI smoke tests."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable

import pytest


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
