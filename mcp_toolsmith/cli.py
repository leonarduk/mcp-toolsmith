"""CLI entrypoint for MCP Toolsmith."""

from __future__ import annotations

from pathlib import Path

import typer

from mcp_toolsmith import __version__
from mcp_toolsmith.extractor import extract_operations
from mcp_toolsmith.generator import generate as generate_project
from mcp_toolsmith.loader import load_spec
from mcp_toolsmith.scorer import score_operations

app = typer.Typer(
    help="Convert OpenAPI specifications into MCP server templates.",
    no_args_is_help=True,
)


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

    try:
        scoring = score_operations(operations, allow_unsafe=unsafe)
        spec_title = str(spec.get("info", {}).get("title", "Generated MCP Server"))
        result = generate_project(
            operations,
            scoring,
            out,
            dry_run=dry_run,
            unsafe=unsafe,
            spec_title=spec_title,
        )
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error generating project: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"planned_files={len(result.files)} skipped_operations={len(result.skipped_operations)}")
    for path in result.files:
        typer.echo(str(path))
    if dry_run:
        typer.echo("dry_run=true snippets=skipped")
    else:
        typer.echo(f"snippets_dir={out / 'snippets'}")


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
