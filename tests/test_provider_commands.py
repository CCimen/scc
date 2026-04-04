"""Tests for provider CLI commands (scc provider show/set)."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from scc_cli.cli import app
from scc_cli.core.provider_resolution import KNOWN_PROVIDERS

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# scc provider show
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderShow:
    """Tests for 'scc provider show' command."""

    def test_show_default_provider(self) -> None:
        """When no provider is configured, show prints 'claude'."""
        with patch("scc_cli.commands.provider.config.get_selected_provider", return_value=None):
            result = runner.invoke(app, ["provider", "show"])
        assert result.exit_code == 0
        assert "claude" in result.output

    def test_show_configured_provider(self) -> None:
        """When a provider is configured, show prints it."""
        with patch("scc_cli.commands.provider.config.get_selected_provider", return_value="codex"):
            result = runner.invoke(app, ["provider", "show"])
        assert result.exit_code == 0
        assert "codex" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# scc provider set
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderSet:
    """Tests for 'scc provider set' command."""

    def test_set_valid_provider(self) -> None:
        """Setting a known provider persists it and prints confirmation."""
        with patch("scc_cli.commands.provider.config.set_selected_provider") as mock_set:
            result = runner.invoke(app, ["provider", "set", "codex"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with("codex")
        assert "codex" in result.output

    def test_set_claude_provider(self) -> None:
        """Setting claude is also valid."""
        with patch("scc_cli.commands.provider.config.set_selected_provider") as mock_set:
            result = runner.invoke(app, ["provider", "set", "claude"])
        assert result.exit_code == 0
        mock_set.assert_called_once_with("claude")

    def test_set_invalid_provider_errors(self) -> None:
        """Setting an unknown provider exits with error."""
        result = runner.invoke(app, ["provider", "set", "invalid"])
        assert result.exit_code != 0
        assert "Unknown provider" in result.output

    def test_set_invalid_provider_lists_known(self) -> None:
        """Error message lists known providers."""
        result = runner.invoke(app, ["provider", "set", "foobar"])
        for p in KNOWN_PROVIDERS:
            assert p in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# scc provider (no subcommand)
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderNoArgs:
    """Tests for 'scc provider' with no subcommand."""

    def test_no_args_shows_help(self) -> None:
        """Running 'scc provider' with no subcommand shows help."""
        result = runner.invoke(app, ["provider"])
        # no_args_is_help=True causes typer to show help and exit 0 or 2
        assert "show" in result.output
        assert "set" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# StartSessionRequest provider_id field
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartSessionRequestProviderField:
    """Verify StartSessionRequest has provider_id field."""

    def test_provider_id_defaults_to_none(self) -> None:
        """provider_id defaults to None when not specified."""
        from pathlib import Path

        from scc_cli.application.start_session import StartSessionRequest

        req = StartSessionRequest(
            workspace_path=Path("/tmp/test"),
            workspace_arg=None,
            entry_dir=Path("/tmp"),
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=False,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
        )
        assert req.provider_id is None

    def test_provider_id_can_be_set(self) -> None:
        """provider_id can be explicitly set."""
        from pathlib import Path

        from scc_cli.application.start_session import StartSessionRequest

        req = StartSessionRequest(
            workspace_path=Path("/tmp/test"),
            workspace_arg=None,
            entry_dir=Path("/tmp"),
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=False,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="codex",
        )
        assert req.provider_id == "codex"
