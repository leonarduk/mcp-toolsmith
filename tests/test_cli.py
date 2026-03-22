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


def test_generate_command_supports_new_flags(run_cli: Callable[..., subprocess.CompletedProcess[str]], tmp_path) -> None:
    """The generate command should expose output-planning flags."""
    fixture = "tests/fixtures/valid_openapi.yaml"
    result = run_cli(
        "generate",
        fixture,
        "--out",
        str(tmp_path / "out"),
        "--dry-run",
        "--include",
        "pets",
        "--exclude",
        "admin",
        "--no-report",
    )

    assert result.returncode == 0
    assert "planned_files=" in result.stdout
    assert "src/index.ts" in result.stdout
    assert "Generation Summary" in result.stdout
    assert result.stderr == ""
