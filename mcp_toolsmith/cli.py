"""CLI entrypoint for MCP Toolsmith."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from mcp_toolsmith import __version__
from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.generator import generate as generate_project
from mcp_toolsmith.loader import load_spec
from mcp_toolsmith.models import OperationModel
from mcp_toolsmith.report import GenerationReport, SkippedOperation, build_report
from mcp_toolsmith.scorer import score_operations

app = typer.Typer(
    help="Convert OpenAPI specifications into MCP server templates.",
    no_args_is_help=True,
)
console = Console()


def version_callback(value: bool) -> None:
    """Print the package version and exit."""
    if value:
        typer.echo(f"mcp-toolsmith {__version__}")
        raise typer.Exit()


@app.callback()
def cli(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the application version and exit.",
    ),
) -> None:
    """MCP Toolsmith command line interface."""


@app.command()
def generate(
    source: str = typer.Argument(..., help="Local path or HTTPS URL to an OpenAPI 3.x spec."),
    out: Path = typer.Option(Path("generated-mcp-server"), "--out", help="Output directory."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan files without writing them."),
    unsafe: bool = typer.Option(False, "--unsafe", help="Include DELETE/PUT/PATCH operations."),
    no_report: bool = typer.Option(False, "--no-report", help="Skip writing report.json."),
    include: list[str] = typer.Option([], "--include", help="Only include operations with these tags."),
    exclude: list[str] = typer.Option([], "--exclude", help="Exclude operations with these tags."),
) -> None:
    """Generate an MCP server from an OpenAPI specification."""
    try:
        spec = load_spec(source)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error loading spec: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    try:
        operations = extract_operations(spec)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error extracting operations: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    filtered_operations, pre_generation_skips = _filter_operations(
        operations,
        include=include,
        exclude=exclude,
    )

    try:
        scoring = score_operations(filtered_operations, allow_unsafe=unsafe)
        result = generate_project(filtered_operations, scoring, out, dry_run=dry_run, unsafe=unsafe)
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error generating project: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    skipped_operations = pre_generation_skips + [
        SkippedOperation(operation_id=operation_id, reason="unsafe HTTP method requires --unsafe")
        for operation_id in result.skipped_operations
    ]
    report = build_report(
        spec_title=spec.get("info", {}).get("title", "Unknown Spec"),
        spec_version=spec.get("info", {}).get("version", "unknown"),
        total_operations=len(operations),
        generated_operations=len(filtered_operations) - len(result.skipped_operations),
        skipped_operations=skipped_operations,
        score=scoring,
        generated_files=[path.relative_to(out) for path in result.files],
        cli_flags={
            "source": source,
            "out": str(out),
            "dry_run": dry_run,
            "unsafe": unsafe,
            "no_report": no_report,
            "include": include,
            "exclude": exclude,
        },
    )

    if not no_report and not dry_run:
        (out / "report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    _render_summary(report)
    typer.echo(f"planned_files={len(result.files)} skipped_operations={len(report.skipped_operations)}")
    for path in result.files:
        typer.echo(str(path))


def _filter_operations(
    operations: list[OperationModel],
    *,
    include: list[str],
    exclude: list[str],
) -> tuple[list[OperationModel], list[SkippedOperation]]:
    include_set = set(include)
    exclude_set = set(exclude)
    kept = []
    skipped: list[SkippedOperation] = []

    for operation in operations:
        operation_tags = set(operation.tags)
        if include_set and not operation_tags.intersection(include_set):
            skipped.append(
                SkippedOperation(
                    operation_id=operation.operation_id,
                    reason="excluded by --include tag filters",
                )
            )
            continue
        if exclude_set and operation_tags.intersection(exclude_set):
            skipped.append(
                SkippedOperation(
                    operation_id=operation.operation_id,
                    reason="excluded by --exclude tag filters",
                )
            )
            continue
        kept.append(operation)

    return kept, skipped


def _render_summary(report: GenerationReport) -> None:
    table = Table(title="Generation Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Spec", f"{report.spec_title} ({report.spec_version})")
    table.add_row("Total operations", str(report.total_operations))
    table.add_row("Generated", str(report.generated_operations))
    table.add_row("Skipped", str(len(report.skipped_operations)))
    table.add_row("Score", str(report.score.total))
    for dimension, score in sorted(report.score.dimensions.items()):
        table.add_row(f"Score: {dimension}", str(score))

    warnings = [finding for finding in report.score.findings if finding.level != "info"]
    if warnings:
        table.add_row("Warnings", str(len(warnings)))
    if report.skipped_operations:
        reasons = ", ".join(
            f"{item.operation_id}: {item.reason}" for item in report.skipped_operations[:3]
        )
        if len(report.skipped_operations) > 3:
            reasons += ", ..."
        table.add_row("Skip reasons", reasons)
    console.print(table)


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
