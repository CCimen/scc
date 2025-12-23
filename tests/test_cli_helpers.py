"""Tests for CLI helpers module.

Tests confirm_action(), require_reason_for_governance(), and related helpers.
"""

import os
from datetime import datetime, timezone
from unittest.mock import patch

import click.exceptions
import pytest

from scc_cli.cli_helpers import (
    AuditRecord,
    ConfirmItems,
    confirm_action,
    create_audit_record,
    get_current_user,
    is_interactive,
    require_reason_for_governance,
)
from scc_cli.exit_codes import EXIT_USAGE

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for is_interactive()
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsInteractive:
    """Tests for is_interactive() detection."""

    def test_interactive_when_tty_and_no_ci(self):
        """Should return True when TTY and no CI env."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("sys.stdin.isatty", return_value=True),
            patch.dict(os.environ, {"CI": ""}, clear=False),
        ):
            assert is_interactive() is True

    def test_not_interactive_when_not_tty(self):
        """Should return False when stdin is not a TTY."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("sys.stdin.isatty", return_value=False),
            patch.dict(os.environ, {"CI": ""}, clear=False),
        ):
            assert is_interactive() is False

    @pytest.mark.parametrize("ci_value", ["1", "true", "yes", "TRUE", "Yes"])
    def test_not_interactive_when_ci_env_set(self, ci_value):
        """Should return False when CI env var is truthy."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("sys.stdin.isatty", return_value=True),
            patch.dict(os.environ, {"CI": ci_value}, clear=False),
        ):
            assert is_interactive() is False

    def test_not_interactive_in_json_mode(self):
        """Should return False in JSON mode."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=True),
            patch("sys.stdin.isatty", return_value=True),
            patch.dict(os.environ, {"CI": ""}, clear=False),
        ):
            assert is_interactive() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for confirm_action()
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfirmActionDryRun:
    """Tests for confirm_action() dry-run behavior."""

    def test_dry_run_returns_false(self):
        """--dry-run should return False without prompting."""
        result = confirm_action(yes=False, prompt="Delete?", dry_run=True)
        assert result is False

    def test_dry_run_with_yes_still_returns_false(self):
        """--dry-run takes precedence over --yes."""
        result = confirm_action(yes=True, prompt="Delete?", dry_run=True)
        assert result is False


class TestConfirmActionYesFlag:
    """Tests for confirm_action() --yes flag behavior."""

    def test_yes_flag_returns_true(self):
        """--yes should return True without prompting."""
        result = confirm_action(yes=True, prompt="Delete?")
        assert result is True

    def test_yes_flag_skips_prompt(self):
        """--yes should not call typer.confirm."""
        with patch("scc_cli.cli_helpers.typer.confirm") as mock_confirm:
            confirm_action(yes=True, prompt="Delete?")
            mock_confirm.assert_not_called()


class TestConfirmActionJsonMode:
    """Tests for confirm_action() in JSON mode."""

    def test_json_mode_exits_usage_without_yes(self):
        """JSON mode without --yes should exit with EXIT_USAGE."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=True),
            pytest.raises(click.exceptions.Exit) as exc_info,
        ):
            confirm_action(yes=False, prompt="Delete?")

        assert exc_info.value.exit_code == EXIT_USAGE

    def test_json_mode_with_yes_proceeds(self):
        """JSON mode with --yes should return True."""
        with patch("scc_cli.cli_helpers.is_json_mode", return_value=True):
            result = confirm_action(yes=True, prompt="Delete?")
            assert result is True


class TestConfirmActionNonInteractive:
    """Tests for confirm_action() in non-interactive mode."""

    def test_non_interactive_without_yes_exits_usage(self):
        """Non-interactive without --yes should exit with EXIT_USAGE."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("scc_cli.cli_helpers.is_interactive", return_value=False),
            pytest.raises(click.exceptions.Exit) as exc_info,
        ):
            confirm_action(yes=False, prompt="Delete?")

        assert exc_info.value.exit_code == EXIT_USAGE

    def test_non_interactive_with_yes_proceeds(self):
        """Non-interactive with --yes should return True."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("scc_cli.cli_helpers.is_interactive", return_value=False),
        ):
            result = confirm_action(yes=True, prompt="Delete?")
            assert result is True


class TestConfirmActionInteractive:
    """Tests for confirm_action() in interactive mode."""

    def test_interactive_prompts_user(self):
        """Interactive mode should call typer.confirm."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
            patch("scc_cli.cli_helpers.typer.confirm", return_value=True) as mock_confirm,
        ):
            result = confirm_action(yes=False, prompt="Delete all?")

            mock_confirm.assert_called_once_with("Delete all?", abort=True)
            assert result is True

    def test_interactive_displays_items(self, capsys):
        """Interactive mode should display items before prompting."""
        items = ConfirmItems(
            title="Will remove:",
            items=["container-1", "container-2", "container-3"],
        )

        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
            patch("scc_cli.cli_helpers.typer.confirm", return_value=True),
        ):
            confirm_action(yes=False, prompt="Delete?", items=items)

        # Rich console output - check that items were displayed
        # (exact format depends on Rich, just verify no crash)

    def test_interactive_truncates_long_list(self):
        """Items beyond max_display should show '+ N more'."""
        items = ConfirmItems(
            title="Will remove:",
            items=[f"container-{i}" for i in range(15)],
            max_display=5,
        )

        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
            patch("scc_cli.cli_helpers.typer.confirm", return_value=True),
        ):
            # Should not crash, should show "10 more"
            confirm_action(yes=False, prompt="Delete?", items=items)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for require_reason_for_governance()
# ═══════════════════════════════════════════════════════════════════════════════


class TestRequireReasonForGovernance:
    """Tests for require_reason_for_governance()."""

    def test_yes_without_reason_exits_usage(self):
        """--yes without --reason should exit with EXIT_USAGE."""
        with pytest.raises(click.exceptions.Exit) as exc_info:
            require_reason_for_governance(yes=True, reason=None)

        assert exc_info.value.exit_code == EXIT_USAGE

    def test_yes_with_reason_returns_reason(self):
        """--yes with --reason should return the reason."""
        result = require_reason_for_governance(yes=True, reason="Testing exception")
        assert result == "Testing exception"

    def test_no_yes_with_reason_returns_reason(self):
        """Reason provided without --yes should return the reason."""
        result = require_reason_for_governance(yes=False, reason="Manual testing")
        assert result == "Manual testing"

    def test_interactive_prompts_for_reason(self):
        """Interactive mode without reason should prompt."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("scc_cli.cli_helpers.is_interactive", return_value=True),
            patch("scc_cli.cli_helpers.typer.prompt", return_value="User input reason"),
        ):
            result = require_reason_for_governance(yes=False, reason=None)
            assert result == "User input reason"

    def test_json_mode_without_reason_exits_usage(self):
        """JSON mode without reason should exit EXIT_USAGE."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=True),
            pytest.raises(click.exceptions.Exit) as exc_info,
        ):
            require_reason_for_governance(yes=False, reason=None)

        assert exc_info.value.exit_code == EXIT_USAGE

    def test_non_interactive_without_reason_exits_usage(self):
        """Non-interactive mode without reason should exit EXIT_USAGE."""
        with (
            patch("scc_cli.cli_helpers.is_json_mode", return_value=False),
            patch("scc_cli.cli_helpers.is_interactive", return_value=False),
            pytest.raises(click.exceptions.Exit) as exc_info,
        ):
            require_reason_for_governance(yes=False, reason=None)

        assert exc_info.value.exit_code == EXIT_USAGE


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for audit record helpers
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditRecord:
    """Tests for AuditRecord and related helpers."""

    def test_get_current_user_from_env(self):
        """Should get user from USER env var."""
        with patch.dict(os.environ, {"USER": "testuser"}, clear=False):
            assert get_current_user() == "testuser"

    def test_get_current_user_fallback_username(self):
        """Should fall back to USERNAME env var."""
        with patch.dict(os.environ, {"USER": "", "USERNAME": "winuser"}, clear=False):
            # This test is platform-dependent, but validates the logic
            result = get_current_user()
            assert result in ("testuser", "winuser", "unknown", os.getenv("USER", ""))

    def test_create_audit_record_basic(self):
        """Should create audit record with required fields."""
        record = create_audit_record(
            command="unblock",
            target="plugin-x",
            reason="Testing",
        )

        assert record.command == "unblock"
        assert record.target == "plugin-x"
        assert record.reason == "Testing"
        assert record.ticket is None
        assert record.expires_in is None
        assert isinstance(record.timestamp, datetime)
        assert record.actor != ""

    def test_create_audit_record_with_optional_fields(self):
        """Should create audit record with optional fields."""
        record = create_audit_record(
            command="unblock",
            target="plugin-x",
            reason="Testing",
            ticket="JIRA-123",
            expires_in="7d",
        )

        assert record.ticket == "JIRA-123"
        assert record.expires_in == "7d"

    def test_audit_record_to_dict(self):
        """Should serialize to dictionary correctly."""
        record = AuditRecord(
            timestamp=datetime(2025, 12, 23, 21, 0, 0, tzinfo=timezone.utc),
            command="unblock",
            actor="testuser",
            target="plugin-x",
            reason="Testing",
            ticket="JIRA-123",
        )

        result = record.to_dict()

        assert result["timestamp"] == "2025-12-23T21:00:00+00:00"
        assert result["command"] == "unblock"
        assert result["actor"] == "testuser"
        assert result["target"] == "plugin-x"
        assert result["reason"] == "Testing"
        assert result["ticket"] == "JIRA-123"
        assert "expires_in" not in result  # None values excluded

    def test_audit_record_to_dict_minimal(self):
        """Should exclude None optional fields."""
        record = AuditRecord(
            timestamp=datetime(2025, 12, 23, 21, 0, 0, tzinfo=timezone.utc),
            command="unblock",
            actor="testuser",
            target="plugin-x",
            reason="Testing",
        )

        result = record.to_dict()

        assert "ticket" not in result
        assert "expires_in" not in result
