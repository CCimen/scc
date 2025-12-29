"""Tests for start cancellation and offline handling.

Focus on exit codes and user-visible messages for early exits.
"""

from unittest.mock import patch

from typer.testing import CliRunner

from scc_cli.cli import app
from scc_cli.exit_codes import EXIT_CANCELLED, EXIT_CONFIG

runner = CliRunner()


def test_start_cancelled_exits_130_and_message():
    """User cancellation should exit 130 and show a Cancelled message."""
    with (
        patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
        patch("scc_cli.cli_launch.config.load_config", return_value={}),
        patch(
            "scc_cli.cli_launch._resolve_session_selection",
            return_value=(None, None, None, None, True),
        ),
    ):
        result = runner.invoke(app, ["start"])

    assert result.exit_code == EXIT_CANCELLED
    assert "Cancelled" in result.output


def test_start_offline_without_cache_exits_config():
    """--offline with no cache should exit with EXIT_CONFIG and message."""
    with (
        patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
        patch("scc_cli.cli_launch.config.load_cached_org_config", return_value=None),
    ):
        result = runner.invoke(app, ["start", "--offline"])

    assert result.exit_code == EXIT_CONFIG
    assert "--offline" in result.output
