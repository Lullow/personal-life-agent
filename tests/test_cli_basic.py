"""Basic CLI tests for personal-life-agent."""

from typer.testing import CliRunner

from life_agent.main import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Local-first terminal assistant" in result.stdout
    assert "version" in result.stdout
    assert "health" in result.stdout


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "personal-life-agent 0.1.0" in result.stdout


def test_health():
    result = runner.invoke(app, ["health"])
    assert result.exit_code == 0
    assert "OK" in result.stdout
    assert "environment:" in result.stdout
    assert "development" in result.stdout
