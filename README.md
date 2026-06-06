# Personal Life Agent

A **local-first terminal MVP** for a personal life assistant. This project runs entirely on your machine — no cloud services, databases, or external APIs in this foundation step.

Use it from the command line to interact with a lightweight assistant that will grow over time into a fuller personal life management tool.

## Requirements

- Python 3.11+
- WSL Ubuntu, Windows 11 (via WSL), or Linux

## Quick start

From the project root:

```bash
# Create and activate a virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run the CLI
python -m life_agent --help
python -m life_agent version
python -m life_agent health
```

You can also run commands without installing by ensuring you are in the project root — Python adds the current directory to the module search path when using `python -m`.

## Development

```bash
# Run tests
pytest

# Run tests with verbose output
pytest -v
```

## Project structure

```
personal-life-agent/
├── life_agent/          # Application package
│   ├── cli/             # Typer CLI commands
│   ├── config.py        # Environment-based settings
│   └── main.py          # Typer app entry point
├── tests/               # Pytest tests
├── docs/                # Documentation and roadmap
├── pyproject.toml       # Project metadata and dependencies
└── README.md
```

## Configuration

Copy `.env.example` to `.env` and adjust values if needed:

```bash
cp .env.example .env
```

| Variable   | Default       | Description              |
|------------|---------------|--------------------------|
| `APP_ENV`  | `development` | Application environment  |
| `LOG_LEVEL`| `INFO`        | Logging level            |

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for planned features. The MVP foundation intentionally excludes databases, LLMs, planners, reminders, and external integrations.

## License

Private / personal project.
