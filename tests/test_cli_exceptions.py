"""Tests for CLI exceptions commands.

TDD tests for Phase 2.1 - CLI Commands for exception management.

Commands to implement:
- scc exceptions list [--active|--expired|--all] [--json]
- scc exceptions create [--policy] [--id] --ttl --reason --allow-* [--shared]
- scc exceptions delete <id> [--yes]
- scc exceptions cleanup
- scc exceptions reset (--user|--repo) --yes
- scc unblock <target> --ttl --reason [--shared]
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scc_cli import cli
from scc_cli.models.exceptions import AllowTargets, ExceptionFile
from scc_cli.models.exceptions import Exception as SccException

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


def make_exception(
    id: str = "local-20251221-a1b2",
    hours_until_expiry: int = 8,
    plugins: list[str] | None = None,
    mcp_servers: list[str] | None = None,
    reason: str = "Testing",
) -> SccException:
    """Create a test exception with configurable expiry."""
    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=hours_until_expiry)
    return SccException(
        id=id,
        created_at=now.isoformat(),
        expires_at=expires.isoformat(),
        reason=reason,
        scope="local",
        allow=AllowTargets(
            plugins=plugins or [],
            mcp_servers=mcp_servers or [],
            base_images=[],
        ),
    )


def make_expired_exception(id: str = "local-20251220-dead") -> SccException:
    """Create an expired exception."""
    now = datetime.now(timezone.utc)
    created = now - timedelta(hours=24)
    expired = now - timedelta(hours=1)
    return SccException(
        id=id,
        created_at=created.isoformat(),
        expires_at=expired.isoformat(),
        reason="Expired test",
        scope="local",
        allow=AllowTargets(plugins=["old-plugin"], mcp_servers=[], base_images=[]),
    )


@pytest.fixture
def mock_user_store():
    """Create a mock user store with some exceptions."""
    store = MagicMock()
    store.read.return_value = ExceptionFile(
        schema_version=1,
        exceptions=[
            make_exception("local-20251221-a1b2", 8, mcp_servers=["jira-api"]),
            make_exception("local-20251221-c3d4", 4, plugins=["vendor-tools"]),
        ],
    )
    store.prune_expired.return_value = 0
    store.reset.return_value = None
    return store


@pytest.fixture
def mock_repo_store():
    """Create a mock repo store."""
    store = MagicMock()
    store.read.return_value = ExceptionFile(schema_version=1, exceptions=[])
    store.prune_expired.return_value = 0
    store.reset.return_value = None
    return store


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc exceptions list command
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionsListCommand:
    """Tests for `scc exceptions list` command."""

    def test_list_shows_active_exceptions(self, mock_user_store, mock_repo_store):
        """Should display active exceptions by default."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "list"])

        assert result.exit_code == 0
        assert "local-20251221-a1b2" in result.output
        assert "jira-api" in result.output

    def test_list_active_flag(self, mock_user_store, mock_repo_store):
        """Should show only active exceptions with --active flag."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "list", "--active"])

        assert result.exit_code == 0
        # Should not show expired exceptions
        assert "expired" not in result.output.lower() or "0 expired" in result.output.lower()

    def test_list_expired_flag(self, mock_user_store, mock_repo_store):
        """Should show only expired exceptions with --expired flag."""
        mock_user_store.read.return_value = ExceptionFile(
            schema_version=1,
            exceptions=[
                make_expired_exception("local-20251220-dead"),
                make_exception("local-20251221-live", 8, plugins=["active-plugin"]),
            ],
        )
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "list", "--expired"])

        assert result.exit_code == 0
        assert "local-20251220-dead" in result.output

    def test_list_all_flag(self, mock_user_store, mock_repo_store):
        """Should show all exceptions (active + expired) with --all flag."""
        mock_user_store.read.return_value = ExceptionFile(
            schema_version=1,
            exceptions=[
                make_expired_exception("local-20251220-dead"),
                make_exception("local-20251221-live", 8, plugins=["active-plugin"]),
            ],
        )
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "list", "--all"])

        assert result.exit_code == 0
        assert "local-20251220-dead" in result.output
        assert "local-20251221-live" in result.output

    def test_list_json_output(self, mock_user_store, mock_repo_store):
        """Should output valid JSON with --json flag."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) >= 1
        assert "id" in data[0]

    def test_list_empty_shows_message(self, mock_repo_store):
        """Should show message when no exceptions exist."""
        empty_store = MagicMock()
        empty_store.read.return_value = ExceptionFile(schema_version=1, exceptions=[])
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=empty_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "list"])

        assert result.exit_code == 0
        assert "no" in result.output.lower() or "empty" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc exceptions create command
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionsCreateCommand:
    """Tests for `scc exceptions create` command."""

    def test_create_with_mcp_server(self, mock_user_store, mock_repo_store):
        """Should create exception for MCP server."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-mcp",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Testing integration",
                ],
            )

        assert result.exit_code == 0
        mock_user_store.write.assert_called_once()
        assert "created" in result.output.lower() or "✓" in result.output

    def test_create_with_plugin(self, mock_user_store, mock_repo_store):
        """Should create exception for plugin."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-plugin",
                    "vendor-tools",
                    "--ttl",
                    "4h",
                    "--reason",
                    "Vendor demo",
                ],
            )

        assert result.exit_code == 0
        mock_user_store.write.assert_called_once()

    def test_create_with_base_image(self, mock_user_store, mock_repo_store):
        """Should create exception for base image."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-image",
                    "custom:latest",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Custom image test",
                ],
            )

        assert result.exit_code == 0
        mock_user_store.write.assert_called_once()

    def test_create_multiple_targets(self, mock_user_store, mock_repo_store):
        """Should allow multiple targets in single exception."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-mcp",
                    "jira-api",
                    "--allow-mcp",
                    "github-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Multi-target test",
                ],
            )

        assert result.exit_code == 0

    def test_create_shared_uses_repo_store(self, mock_user_store, mock_repo_store):
        """Should use repo store when --shared is specified."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-mcp",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Shared test",
                    "--shared",
                ],
            )

        assert result.exit_code == 0
        mock_repo_store.write.assert_called_once()

    def test_create_policy_generates_yaml(self, mock_user_store, mock_repo_store):
        """Should generate YAML snippet for --policy flag."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--policy",
                    "--id",
                    "INC-2025-001",
                    "--allow-mcp",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Policy exception",
                ],
            )

        assert result.exit_code == 0
        # Should output YAML-like content for PR
        assert "INC-2025-001" in result.output
        assert "jira-api" in result.output

    def test_create_policy_requires_id(self, mock_user_store, mock_repo_store):
        """Should require --id when --policy is specified."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--policy",
                    "--allow-mcp",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Policy exception",
                ],
            )

        assert result.exit_code != 0
        assert "id" in result.output.lower()

    def test_create_requires_reason(self, mock_user_store, mock_repo_store):
        """Should require --reason."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-mcp",
                    "jira-api",
                    "--ttl",
                    "8h",
                ],
            )

        assert result.exit_code != 0

    def test_create_requires_target(self, mock_user_store, mock_repo_store):
        """Should require at least one allow target."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--ttl",
                    "8h",
                    "--reason",
                    "No targets",
                ],
            )

        assert result.exit_code != 0

    def test_create_with_until(self, mock_user_store, mock_repo_store):
        """Should accept --until time format."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-mcp",
                    "jira-api",
                    "--until",
                    "17:00",
                    "--reason",
                    "Until EOD",
                ],
            )

        assert result.exit_code == 0

    def test_create_with_expires_at(self, mock_user_store, mock_repo_store):
        """Should accept --expires-at RFC3339 format."""
        future = datetime.now(timezone.utc) + timedelta(hours=8)
        expires_at = future.strftime("%Y-%m-%dT%H:%M:%SZ")
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-mcp",
                    "jira-api",
                    "--expires-at",
                    expires_at,
                    "--reason",
                    "Explicit expiry",
                ],
            )

        assert result.exit_code == 0

    def test_create_shows_expiration_info(self, mock_user_store, mock_repo_store):
        """Should show expiration time and relative duration."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "exceptions",
                    "create",
                    "--allow-mcp",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Test",
                ],
            )

        assert result.exit_code == 0
        # Should show relative time like "8h" or expiration time
        assert "8h" in result.output or "expires" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc exceptions delete command
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionsDeleteCommand:
    """Tests for `scc exceptions delete` command."""

    def test_delete_by_id(self, mock_user_store, mock_repo_store):
        """Should delete exception by exact ID."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                ["exceptions", "delete", "local-20251221-a1b2"],
            )

        assert result.exit_code == 0
        mock_user_store.write.assert_called_once()

    def test_delete_by_prefix(self, mock_user_store, mock_repo_store):
        """Should delete by prefix if unambiguous."""
        # Only one exception starting with 'local-20251221-a'
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                ["exceptions", "delete", "local-20251221-a"],
            )

        assert result.exit_code == 0

    def test_delete_ambiguous_prefix_error(self, mock_user_store, mock_repo_store):
        """Should error on ambiguous prefix."""
        # Both exceptions start with 'local-20251221-'
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                ["exceptions", "delete", "local-20251221-"],
            )

        # Should fail or prompt
        assert result.exit_code != 0 or "ambiguous" in result.output.lower()

    def test_delete_not_found_error(self, mock_user_store, mock_repo_store):
        """Should error when exception not found."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                ["exceptions", "delete", "nonexistent-id"],
            )

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "no" in result.output.lower()

    def test_delete_with_yes_flag(self, mock_user_store, mock_repo_store):
        """Should not prompt with --yes flag."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(
                cli.app,
                ["exceptions", "delete", "local-20251221-a1b2", "--yes"],
            )

        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc exceptions cleanup command
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionsCleanupCommand:
    """Tests for `scc exceptions cleanup` command."""

    def test_cleanup_removes_expired(self, mock_repo_store):
        """Should remove expired exceptions."""
        mock_store = MagicMock()
        mock_store.prune_expired.return_value = 3
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "cleanup"])

        assert result.exit_code == 0
        mock_store.prune_expired.assert_called()
        assert "3" in result.output or "removed" in result.output.lower()

    def test_cleanup_no_expired(self, mock_repo_store):
        """Should show message when nothing to cleanup."""
        mock_store = MagicMock()
        mock_store.prune_expired.return_value = 0
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "cleanup"])

        assert result.exit_code == 0
        assert "0" in result.output or "no" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc exceptions reset command
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionsResetCommand:
    """Tests for `scc exceptions reset` command."""

    def test_reset_user_requires_yes(self, mock_user_store, mock_repo_store):
        """Should require --yes for destructive reset."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "reset", "--user"])

        # Should fail without --yes
        assert result.exit_code != 0

    def test_reset_user_with_yes(self, mock_user_store, mock_repo_store):
        """Should reset user store with --yes."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "reset", "--user", "--yes"])

        assert result.exit_code == 0
        mock_user_store.reset.assert_called_once()

    def test_reset_repo_with_yes(self, mock_user_store, mock_repo_store):
        """Should reset repo store with --yes."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "reset", "--repo", "--yes"])

        assert result.exit_code == 0
        mock_repo_store.reset.assert_called_once()

    def test_reset_requires_store_selection(self, mock_user_store, mock_repo_store):
        """Should require --user or --repo."""
        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
        ):
            result = runner.invoke(cli.app, ["exceptions", "reset", "--yes"])

        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc unblock command
# ═══════════════════════════════════════════════════════════════════════════════


class TestUnblockCommand:
    """Tests for `scc unblock` command."""

    def test_unblock_creates_exception(self, mock_user_store, mock_repo_store):
        """Should create local exception for blocked target."""
        # Mock the evaluation to show item as denied
        mock_eval = MagicMock()
        mock_eval.denied_additions = [MagicMock(target="jira-api", target_type="mcp_server")]
        mock_eval.blocked_items = []

        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
            patch("scc_cli.cli_exceptions.get_current_denials", return_value=mock_eval),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "unblock",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Need for sprint",
                ],
            )

        assert result.exit_code == 0
        mock_user_store.write.assert_called_once()
        assert "created" in result.output.lower() or "✓" in result.output

    def test_unblock_shared_uses_repo_store(self, mock_user_store, mock_repo_store):
        """Should use repo store with --shared."""
        mock_eval = MagicMock()
        mock_eval.denied_additions = [MagicMock(target="jira-api", target_type="mcp_server")]
        mock_eval.blocked_items = []

        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
            patch("scc_cli.cli_exceptions.get_current_denials", return_value=mock_eval),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "unblock",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Team needs",
                    "--shared",
                ],
            )

        assert result.exit_code == 0
        mock_repo_store.write.assert_called_once()

    def test_unblock_security_block_fails(self, mock_user_store, mock_repo_store):
        """Should fail when trying to unblock security-blocked item."""
        mock_eval = MagicMock()
        mock_eval.denied_additions = []
        mock_eval.blocked_items = [MagicMock(target="vendor-tools", target_type="plugin")]

        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
            patch("scc_cli.cli_exceptions.get_current_denials", return_value=mock_eval),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "unblock",
                    "vendor-tools",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Trying to bypass",
                ],
            )

        assert result.exit_code != 0
        assert "security" in result.output.lower() or "policy" in result.output.lower()

    def test_unblock_not_denied_fails(self, mock_user_store, mock_repo_store):
        """Should fail when target is not currently denied."""
        mock_eval = MagicMock()
        mock_eval.denied_additions = []
        mock_eval.blocked_items = []

        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
            patch("scc_cli.cli_exceptions.get_current_denials", return_value=mock_eval),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "unblock",
                    "unknown-target",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Preemptive",
                ],
            )

        assert result.exit_code != 0
        assert "not" in result.output.lower() or "denied" in result.output.lower()

    def test_unblock_requires_reason(self, mock_user_store, mock_repo_store):
        """Should require --reason."""
        mock_eval = MagicMock()
        mock_eval.denied_additions = [MagicMock(target="jira-api", target_type="mcp_server")]
        mock_eval.blocked_items = []

        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
            patch("scc_cli.cli_exceptions.get_current_denials", return_value=mock_eval),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "unblock",
                    "jira-api",
                    "--ttl",
                    "8h",
                ],
            )

        assert result.exit_code != 0

    def test_unblock_shows_store_path(self, mock_user_store, mock_repo_store):
        """Should show where exception was saved."""
        mock_eval = MagicMock()
        mock_eval.denied_additions = [MagicMock(target="jira-api", target_type="mcp_server")]
        mock_eval.blocked_items = []

        with (
            patch("scc_cli.cli_exceptions._get_user_store", return_value=mock_user_store),
            patch("scc_cli.cli_exceptions._get_repo_store", return_value=mock_repo_store),
            patch("scc_cli.cli_exceptions.get_current_denials", return_value=mock_eval),
        ):
            result = runner.invoke(
                cli.app,
                [
                    "unblock",
                    "jira-api",
                    "--ttl",
                    "8h",
                    "--reason",
                    "Testing",
                ],
            )

        assert result.exit_code == 0
        # Should show path to store file
        assert "saved" in result.output.lower() or ".json" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for help and error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionsHelpAndErrors:
    """Tests for help messages and error handling."""

    def test_exceptions_help(self):
        """Should show help for exceptions command."""
        result = runner.invoke(cli.app, ["exceptions", "--help"])

        assert result.exit_code == 0
        assert "exceptions" in result.output.lower()

    def test_exceptions_list_help(self):
        """Should show help for exceptions list command."""
        result = runner.invoke(cli.app, ["exceptions", "list", "--help"])

        assert result.exit_code == 0

    def test_exceptions_create_help(self):
        """Should show help for exceptions create command."""
        result = runner.invoke(cli.app, ["exceptions", "create", "--help"])

        assert result.exit_code == 0

    def test_unblock_help(self):
        """Should show help for unblock command."""
        result = runner.invoke(cli.app, ["unblock", "--help"])

        assert result.exit_code == 0
        assert "unblock" in result.output.lower()
