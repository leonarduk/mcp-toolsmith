"""CLI entrypoint for MCP Toolsmith."""

from __future__ import annotations

import typer

from mcp_toolsmith import __version__

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
def generate() -> None:
    """Generate an MCP server from an OpenAPI specification."""
    typer.echo("not yet implemented")
    raise typer.Exit(code=0)


def main() -> None:
    """Run the Typer application."""
    app()


if __name__ == "__main__":
    main()
