"""CLI command implementations."""

import typer
from rich.console import Console

from life_agent import __version__
from life_agent.config import get_settings

console = Console()


def register_commands(app: typer.Typer) -> None:
    """Register all CLI commands on the given Typer app."""

    @app.command("version")
    def version() -> None:
        """Show the application version."""
        console.print(f"personal-life-agent {__version__}")

    @app.command("health")
    def health() -> None:
        """Check that the application is running correctly."""
        settings = get_settings()
        console.print("[green]OK[/green] personal-life-agent is healthy")
        console.print(f"  environment: {settings.app_env}")
        console.print(f"  log level:   {settings.log_level}")
