"""Tests for scc setup CLI command with new flags.

TDD: Tests for --org shorthand resolution and --profile alias.
Tests cover: shorthand resolution, profile/team alias, error handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Typer CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_org_config() -> dict:
    """Sample valid organization config."""
    return {
        "schema_version": "1.0.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "profiles": {"dev": {"description": "Dev team"}, "platform": {"description": "Platform"}},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --org flag with shorthand resolution
# ═══════════════════════════════════════════════════════════════════════════════


class TestSetupOrgFlag:
    """Test the --org flag that accepts shorthands."""

    def test_org_flag_resolves_github_shorthand(
        self, cli_runner: CliRunner, sample_org_config: dict
    ) -> None:
        """--org github:org/repo should resolve to raw URL."""
        from scc_cli.cli import app
        from scc_cli.source_resolver import ResolvedSource

        mock_resolved = MagicMock(spec=ResolvedSource)
        mock_resolved.resolved_url = (
            "https://raw.githubusercontent.com/org/repo/main/org-config.json"
        )

        with (
            patch("scc_cli.cli_config.resolve_source", return_value=mock_resolved),
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                return_value=sample_org_config,
            ),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = cli_runner.invoke(
                app, ["setup", "--org", "github:acme/config", "--profile", "dev"]
            )

        assert result.exit_code == 0

    def test_org_flag_accepts_direct_url(
        self, cli_runner: CliRunner, sample_org_config: dict
    ) -> None:
        """--org should also accept direct HTTPS URLs."""
        from scc_cli.cli import app
        from scc_cli.source_resolver import ResolvedSource

        mock_resolved = MagicMock(spec=ResolvedSource)
        mock_resolved.resolved_url = "https://example.com/org-config.json"

        with (
            patch("scc_cli.cli_config.resolve_source", return_value=mock_resolved),
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                return_value=sample_org_config,
            ),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = cli_runner.invoke(
                app, ["setup", "--org", "https://example.com/org-config.json"]
            )

        assert result.exit_code == 0

    def test_org_flag_shows_error_on_invalid_shorthand(self, cli_runner: CliRunner) -> None:
        """--org with invalid shorthand should show helpful error."""
        from scc_cli.cli import app
        from scc_cli.source_resolver import ResolveError

        mock_error = ResolveError(
            message="Invalid source format",
            source="invalid-source",
            suggestion="Use: github:owner/repo or https://...",
        )

        with patch("scc_cli.cli_config.resolve_source", return_value=mock_error):
            result = cli_runner.invoke(app, ["setup", "--org", "invalid-source"])

        assert result.exit_code == 1
        assert "Invalid Source" in result.stdout or "invalid" in result.stdout.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --profile flag (alias for --team)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSetupProfileFlag:
    """Test the --profile flag as alias for --team."""

    def test_profile_flag_selects_profile(
        self, cli_runner: CliRunner, sample_org_config: dict
    ) -> None:
        """--profile should select the specified profile."""
        from scc_cli.cli import app
        from scc_cli.source_resolver import ResolvedSource

        mock_resolved = MagicMock(spec=ResolvedSource)
        mock_resolved.resolved_url = "https://example.com/org-config.json"

        with (
            patch("scc_cli.cli_config.resolve_source", return_value=mock_resolved),
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                return_value=sample_org_config,
            ),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = cli_runner.invoke(
                app, ["setup", "--org", "https://example.com/config.json", "--profile", "platform"]
            )

        assert result.exit_code == 0
        # Verify profile was passed to run_non_interactive_setup

    def test_team_flag_still_works(self, cli_runner: CliRunner, sample_org_config: dict) -> None:
        """--team should still work for backward compatibility."""
        from scc_cli.cli import app
        from scc_cli.source_resolver import ResolvedSource

        mock_resolved = MagicMock(spec=ResolvedSource)
        mock_resolved.resolved_url = "https://example.com/org-config.json"

        with (
            patch("scc_cli.cli_config.resolve_source", return_value=mock_resolved),
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                return_value=sample_org_config,
            ),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = cli_runner.invoke(
                app, ["setup", "--org", "https://example.com/config.json", "--team", "dev"]
            )

        assert result.exit_code == 0

    def test_profile_takes_precedence_over_team(
        self, cli_runner: CliRunner, sample_org_config: dict
    ) -> None:
        """When both --profile and --team specified, --profile wins."""
        from scc_cli.cli import app
        from scc_cli.source_resolver import ResolvedSource

        mock_resolved = MagicMock(spec=ResolvedSource)
        mock_resolved.resolved_url = "https://example.com/org-config.json"

        with (
            patch("scc_cli.cli_config.resolve_source", return_value=mock_resolved),
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                return_value=sample_org_config,
            ),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
            patch("scc_cli.setup.run_non_interactive_setup") as mock_run,
        ):
            mock_run.return_value = True
            result = cli_runner.invoke(
                app,
                [
                    "setup",
                    "--org",
                    "https://example.com/config.json",
                    "--profile",
                    "platform",
                    "--team",
                    "dev",
                ],
            )

        assert result.exit_code == 0
        # --profile=platform should win over --team=dev
        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        # Check that team argument is "platform" (from --profile)
        assert call_kwargs[1]["team"] == "platform" or call_kwargs.kwargs.get("team") == "platform"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --org-url backward compatibility
# ═══════════════════════════════════════════════════════════════════════════════


class TestSetupOrgUrlBackwardCompat:
    """Test that --org-url still works for backward compatibility."""

    def test_org_url_flag_still_works(self, cli_runner: CliRunner, sample_org_config: dict) -> None:
        """--org-url should still work (deprecated but supported)."""
        from scc_cli.cli import app

        with (
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                return_value=sample_org_config,
            ),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = cli_runner.invoke(
                app,
                [
                    "setup",
                    "--org-url",
                    "https://example.com/org-config.json",
                    "--team",
                    "dev",
                ],
            )

        assert result.exit_code == 0

    def test_org_takes_precedence_over_org_url(
        self, cli_runner: CliRunner, sample_org_config: dict
    ) -> None:
        """When both --org and --org-url specified, --org wins."""
        from scc_cli.cli import app
        from scc_cli.source_resolver import ResolvedSource

        mock_resolved = MagicMock(spec=ResolvedSource)
        mock_resolved.resolved_url = "https://raw.githubusercontent.com/org/repo/main/config.json"

        with (
            patch("scc_cli.cli_config.resolve_source", return_value=mock_resolved) as mock_resolve,
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                return_value=sample_org_config,
            ),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = cli_runner.invoke(
                app,
                [
                    "setup",
                    "--org",
                    "github:acme/config",
                    "--org-url",
                    "https://ignored.com/config.json",
                ],
            )

        assert result.exit_code == 0
        # Verify resolve_source was called with github shorthand, not the URL
        mock_resolve.assert_called_once_with("github:acme/config")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for standalone mode
# ═══════════════════════════════════════════════════════════════════════════════


class TestSetupStandaloneMode:
    """Test standalone mode still works with new flags."""

    def test_standalone_ignores_org_flag(self, cli_runner: CliRunner) -> None:
        """--standalone should work regardless of --org being set."""
        from scc_cli.cli import app

        with (
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = cli_runner.invoke(app, ["setup", "--standalone"])

        assert result.exit_code == 0
