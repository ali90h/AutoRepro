"""Shared test fixtures and configuration."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def isolated_environment(temp_workspace, monkeypatch):
    """Isolate tests from system environment."""
    # Change to temp directory
    monkeypatch.chdir(temp_workspace)

    # Clear relevant environment variables
    env_vars_to_clear = [
        "AUTOREPRO_CONFIG",
        "AUTOREPRO_PLUGINS",
        "AUTOREPRO_DEBUG",
    ]

    for var in env_vars_to_clear:
        monkeypatch.delenv(var, raising=False)

    return temp_workspace
