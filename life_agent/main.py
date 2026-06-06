"""Main Typer application entry point."""

import typer

from life_agent.cli.commands import register_commands

app = typer.Typer(
    name="life-agent",
    help="Local-first terminal assistant for personal life management.",
    no_args_is_help=True,
)

register_commands(app)


def main() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    main()
