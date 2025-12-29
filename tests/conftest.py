"""Shared pytest fixtures for SCC tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Path Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_git_repo(temp_dir):
    """Create a temporary git repository for testing."""
    import subprocess

    subprocess.run(["git", "init"], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_dir,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_dir,
        capture_output=True,
    )

    # Create an initial commit
    readme = temp_dir / "README.md"
    readme.write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_dir,
        capture_output=True,
    )

    yield temp_dir


# ═══════════════════════════════════════════════════════════════════════════════
# Config Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_config_dir(temp_dir, monkeypatch):
    """Create a temporary config directory and patch config paths.

    NOTE: This fixture is for the config architecture with remote org config.
    - config_dir is ~/.config/scc/ (not scc-cli)
    - cache_dir is ~/.cache/scc/
    - No local org config (org config is fetched remotely)
    """
    config_dir = temp_dir / ".config" / "scc"
    config_dir.mkdir(parents=True)

    cache_dir = temp_dir / ".cache" / "scc"
    cache_dir.mkdir(parents=True)

    monkeypatch.setattr("scc_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("scc_cli.config.CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr("scc_cli.config.SESSIONS_FILE", config_dir / "sessions.json")
    monkeypatch.setattr("scc_cli.config.CACHE_DIR", cache_dir)
    monkeypatch.setattr("scc_cli.config.LEGACY_CONFIG_DIR", temp_dir / ".config" / "scc-cli")

    yield config_dir


# ═══════════════════════════════════════════════════════════════════════════════
# Console Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_console():
    """Create a mock Rich console for testing output."""
    console = MagicMock()
    console.width = 120
    return console


# ═══════════════════════════════════════════════════════════════════════════════
# Subprocess Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_subprocess_success():
    """Mock subprocess.run to return success."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="success output",
            stderr="",
        )
        yield mock_run


@pytest.fixture
def mock_subprocess_failure():
    """Mock subprocess.run to return failure."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error output",
        )
        yield mock_run


@pytest.fixture
def mock_docker_available():
    """Mock Docker being available."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = "/usr/local/bin/docker"
        yield mock_which


@pytest.fixture
def mock_docker_unavailable():
    """Mock Docker being unavailable."""
    with patch("shutil.which") as mock_which:
        mock_which.return_value = None
        yield mock_which


# ═══════════════════════════════════════════════════════════════════════════════
# Environment Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment variables for testing."""
    # Remove any SCC-related environment variables
    for key in list(os.environ.keys()):
        if key.startswith("SCC_"):
            monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture(autouse=True)
def isolate_xdg_paths(tmp_path: Path, monkeypatch):
    """Isolate XDG paths for ALL tests to prevent cache pollution.

    This autouse fixture ensures that all tests write to temporary directories
    instead of the user's real ~/.cache/scc/ or ~/.config/scc/. This is critical
    for modules like contexts.py that read XDG_CACHE_HOME directly from env vars.

    Without this, tests that call record_context() would pollute the user's
    real session/context cache with fake test paths.
    """
    # Set XDG environment variables to temp directories
    xdg_cache = tmp_path / ".cache"
    xdg_config = tmp_path / ".config"
    xdg_cache.mkdir(parents=True, exist_ok=True)
    xdg_config.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))

    yield


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Testing Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner for testing commands."""
    from typer.testing import CliRunner

    return CliRunner()


@pytest.fixture
def app():
    """Get the CLI app for testing."""
    from scc_cli.cli import app

    return app
