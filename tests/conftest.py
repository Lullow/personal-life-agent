"""Shared pytest fixtures.

Tests never read the developer's local ``.env``.  Settings must come from the
declared defaults or from ``monkeypatch.setenv``, so a machine with real LLM
credentials configured behaves exactly like one without.
"""

import pytest

from life_agent import config


@pytest.fixture(autouse=True)
def ignore_local_env_file(monkeypatch):
    """Neutralise the local ``.env`` file for every test."""
    monkeypatch.setattr(config, "load_env_file", lambda *args, **kwargs: {})
