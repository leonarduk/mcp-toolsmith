"""CLI smoke tests for the package scaffold."""

from __future__ import annotations

import subprocess
from collections.abc import Callable


def test_help_flag_runs_cleanly(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """The CLI help output should render successfully."""
    result = run_cli("--help")

    assert result.returncode == 0
    assert "Convert OpenAPI specifications into MCP server templates." in result.stdout
    assert "generate" in result.stdout
    assert result.stderr == ""


def test_version_flag_reports_package_version(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """The CLI version flag should print the packaged version."""
    result = run_cli("--version")

    assert result.returncode == 0
    assert result.stdout.strip() == "mcp-toolsmith 0.1.0"
    assert result.stderr == ""


def test_generate_stub_runs_cleanly(
    run_cli: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    """The generate stub should exit successfully with its placeholder output."""
    result = run_cli("generate")

    assert result.returncode == 0
    assert result.stdout.strip() == "not yet implemented"
    assert result.stderr == ""
