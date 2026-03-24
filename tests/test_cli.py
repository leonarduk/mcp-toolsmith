"""CLI smoke tests for the package scaffold."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path


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


def test_generate_command_supports_new_flags(
    run_cli: Callable[..., subprocess.CompletedProcess[str]], tmp_path: Path
) -> None:
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
    assert "snippets/" in result.stdout
    assert result.stderr == ""


def test_generate_writes_report_json_with_filter_metadata(
    run_cli: Callable[..., subprocess.CompletedProcess[str]], tmp_path: Path
) -> None:
    """Successful generation should emit report.json with filter and skip metadata."""
    out_dir = tmp_path / "out"
    result = run_cli(
        "generate",
        "tests/fixtures/petstore_v3.yaml",
        "--out",
        str(out_dir),
        "--include",
        "pets",
    )

    assert result.returncode == 0
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))

    assert report["spec_title"] == "Petstore"
    assert report["generated_operations"] == 3
    assert report["cli_flags"]["include"] == ["pets"]
    assert report["cli_flags"]["exclude"] == []
    assert report["skipped_operations"] == [
        {
            "operation_id": "delete_pet",
            "reason": "excluded by --include tag filters",
        }
    ]


def test_generate_no_report_suppresses_report_file(
    run_cli: Callable[..., subprocess.CompletedProcess[str]], tmp_path: Path
) -> None:
    """The --no-report flag should suppress report.json without failing generation."""
    out_dir = tmp_path / "out"
    result = run_cli(
        "generate",
        "tests/fixtures/petstore_v3.yaml",
        "--out",
        str(out_dir),
        "--no-report",
    )

    assert result.returncode == 0
    assert not (out_dir / "report.json").exists()
    assert (out_dir / "src" / "index.ts").exists()
