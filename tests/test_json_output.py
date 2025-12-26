"""
Tests for JSON output infrastructure.

TDD approach: Tests written before implementation.
These tests define the contract for the JSON output system.
"""

from datetime import datetime
from unittest.mock import patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def reset_output_mode_state():
    """Reset output mode state before and after each test.

    This prevents state leakage from other tests that set pretty_mode
    via set_pretty_mode() without resetting it.
    """
    from scc_cli.output_mode import _json_mode, _pretty_mode

    # Reset before test
    _pretty_mode.set(False)
    _json_mode.set(False)
    yield
    # Reset after test (cleanup)
    _pretty_mode.set(False)
    _json_mode.set(False)


# ═══════════════════════════════════════════════════════════════════════════════
# Exit Codes Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExitCodes:
    """Test exit code constants and helper functions."""

    def test_exit_success_is_zero(self):
        """EXIT_SUCCESS must be 0."""
        from scc_cli.exit_codes import EXIT_SUCCESS

        assert EXIT_SUCCESS == 0

    def test_exit_error_is_one(self):
        """EXIT_ERROR must be 1 (general error)."""
        from scc_cli.exit_codes import EXIT_ERROR

        assert EXIT_ERROR == 1

    def test_exit_usage_is_two(self):
        """EXIT_USAGE must be 2 (Click/Typer convention)."""
        from scc_cli.exit_codes import EXIT_USAGE

        assert EXIT_USAGE == 2

    def test_exit_config_is_three(self):
        """EXIT_CONFIG must be 3."""
        from scc_cli.exit_codes import EXIT_CONFIG

        assert EXIT_CONFIG == 3

    def test_exit_validation_is_four(self):
        """EXIT_VALIDATION must be 4."""
        from scc_cli.exit_codes import EXIT_VALIDATION

        assert EXIT_VALIDATION == 4

    def test_exit_prereq_is_five(self):
        """EXIT_PREREQ must be 5."""
        from scc_cli.exit_codes import EXIT_PREREQ

        assert EXIT_PREREQ == 5

    def test_exit_governance_is_six(self):
        """EXIT_GOVERNANCE must be 6."""
        from scc_cli.exit_codes import EXIT_GOVERNANCE

        assert EXIT_GOVERNANCE == 6

    def test_get_exit_code_for_config_error(self):
        """ConfigError should map to EXIT_CONFIG."""
        from scc_cli.errors import ConfigError
        from scc_cli.exit_codes import EXIT_CONFIG, get_exit_code_for_exception

        exc = ConfigError(user_message="test")
        assert get_exit_code_for_exception(exc) == EXIT_CONFIG

    def test_get_exit_code_for_unknown_error(self):
        """Unknown exceptions should map to EXIT_ERROR."""
        from scc_cli.exit_codes import EXIT_ERROR, get_exit_code_for_exception

        exc = RuntimeError("test")
        assert get_exit_code_for_exception(exc) == EXIT_ERROR


# ═══════════════════════════════════════════════════════════════════════════════
# Kind Constants Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestKinds:
    """Test JSON kind constants."""

    def test_kind_is_str_enum(self):
        """Kind should be a string enum for JSON serialization."""
        from scc_cli.kinds import Kind

        # String enums can be used directly in JSON
        assert isinstance(Kind.TEAM_LIST.value, str)
        assert Kind.TEAM_LIST == "TeamList"

    def test_all_required_kinds_exist(self):
        """All required kind constants must exist."""
        from scc_cli.kinds import Kind

        required_kinds = [
            "TEAM_LIST",
            "TEAM_INFO",
            "TEAM_CURRENT",
            "TEAM_SWITCH",
            "STATUS",
            "DOCTOR_REPORT",
            "WORKTREE_LIST",
            "WORKTREE_CREATE",
            "WORKTREE_REMOVE",
            "SESSION_LIST",
            "CONTAINER_LIST",
            "ORG_VALIDATION",
            "ORG_SCHEMA",
            "SUPPORT_BUNDLE",
            "CONFIG_EXPLAIN",
            "START_DRY_RUN",
        ]

        for kind_name in required_kinds:
            assert hasattr(Kind, kind_name), f"Kind.{kind_name} is missing"

    def test_kind_values_are_pascal_case(self):
        """Kind values should be PascalCase for JSON readability."""
        from scc_cli.kinds import Kind

        for kind in Kind:
            # Check first char is uppercase
            assert kind.value[0].isupper(), f"{kind.value} should start with uppercase"
            # Check no underscores (PascalCase, not snake_case)
            assert "_" not in kind.value, f"{kind.value} should not contain underscores"


# ═══════════════════════════════════════════════════════════════════════════════
# Output Mode Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestOutputMode:
    """Test JSON output mode context management."""

    def test_is_json_mode_default_false(self):
        """JSON mode should be off by default."""
        from scc_cli.output_mode import is_json_mode

        assert is_json_mode() is False

    def test_json_output_mode_context_manager(self):
        """Context manager should enable JSON mode within block."""
        from scc_cli.output_mode import is_json_mode, json_output_mode

        assert is_json_mode() is False

        with json_output_mode():
            assert is_json_mode() is True

        # Must reset after context exits
        assert is_json_mode() is False

    def test_json_mode_resets_on_exception(self):
        """JSON mode must reset even if exception occurs in block."""
        from scc_cli.output_mode import is_json_mode, json_output_mode

        assert is_json_mode() is False

        try:
            with json_output_mode():
                assert is_json_mode() is True
                raise ValueError("test exception")
        except ValueError:
            pass

        # Must still reset
        assert is_json_mode() is False

    def test_is_pretty_mode_default_false(self):
        """Pretty mode should be off by default."""
        from scc_cli.output_mode import is_pretty_mode

        assert is_pretty_mode() is False

    def test_print_human_suppressed_in_json_mode(self):
        """print_human should be no-op in JSON mode."""
        from scc_cli.output_mode import json_output_mode, print_human

        with patch("scc_cli.output_mode.console") as mock_console:
            # Normal mode: should print
            print_human("test message")
            mock_console.print.assert_called_once()

            mock_console.reset_mock()

            # JSON mode: should NOT print
            with json_output_mode():
                print_human("test message")
                mock_console.print.assert_not_called()

    def test_print_json_compact_by_default(self, capsys):
        """print_json should output compact JSON by default."""
        from scc_cli.output_mode import print_json

        data = {"key": "value", "nested": {"a": 1}}
        print_json(data)

        captured = capsys.readouterr()
        # Compact JSON has no newlines within the object
        assert "\n" not in captured.out.strip()
        # Compact JSON uses minimal separators
        assert '{"key":"value",' in captured.out or '"key":"value"' in captured.out

    def test_print_json_pretty_mode(self, capsys, monkeypatch):
        """print_json should indent when pretty mode is on."""
        from scc_cli.output_mode import _pretty_mode, print_json

        # Enable pretty mode
        token = _pretty_mode.set(True)
        try:
            data = {"key": "value"}
            print_json(data)

            captured = capsys.readouterr()
            # Pretty JSON has newlines and indentation
            assert "\n" in captured.out
            assert "  " in captured.out  # indentation
        finally:
            _pretty_mode.reset(token)


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Envelope Builder Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonOutput:
    """Test JSON envelope building."""

    def test_build_envelope_structure(self):
        """Envelope must have all required fields."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        envelope = build_envelope(Kind.TEAM_LIST, data={"teams": []})

        assert "apiVersion" in envelope
        assert "kind" in envelope
        assert "metadata" in envelope
        assert "status" in envelope
        assert "data" in envelope

    def test_build_envelope_api_version(self):
        """apiVersion should be scc.cli/v1."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        envelope = build_envelope(Kind.TEAM_LIST, data={})
        assert envelope["apiVersion"] == "scc.cli/v1"

    def test_build_envelope_kind_from_enum(self):
        """kind should use enum value."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        envelope = build_envelope(Kind.TEAM_LIST, data={})
        assert envelope["kind"] == "TeamList"

    def test_build_envelope_metadata_has_timestamp(self):
        """metadata.generatedAt should be ISO 8601 timestamp."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        envelope = build_envelope(Kind.TEAM_LIST, data={})

        # Should be parseable as ISO datetime
        generated_at = envelope["metadata"]["generatedAt"]
        datetime.fromisoformat(generated_at.replace("Z", "+00:00"))

    def test_build_envelope_metadata_has_cli_version(self):
        """metadata.cliVersion should be present."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        envelope = build_envelope(Kind.TEAM_LIST, data={})
        assert "cliVersion" in envelope["metadata"]

    def test_build_envelope_status_ok_default_true(self):
        """status.ok should default to True."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        envelope = build_envelope(Kind.TEAM_LIST, data={})
        assert envelope["status"]["ok"] is True
        assert envelope["status"]["errors"] == []
        assert envelope["status"]["warnings"] == []

    def test_build_envelope_status_ok_false_with_errors(self):
        """status.ok should be False when errors provided."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        envelope = build_envelope(
            Kind.TEAM_LIST,
            data={},
            ok=False,
            errors=["Something went wrong"],
        )
        assert envelope["status"]["ok"] is False
        assert "Something went wrong" in envelope["status"]["errors"]

    def test_build_envelope_data_passthrough(self):
        """data should pass through as-is."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        test_data = {"teams": [{"name": "platform"}, {"name": "frontend"}]}
        envelope = build_envelope(Kind.TEAM_LIST, data=test_data)
        assert envelope["data"] == test_data


# ═══════════════════════════════════════════════════════════════════════════════
# Deprecation Infrastructure Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeprecation:
    """Test deprecation warning infrastructure."""

    def test_warn_deprecated_prints_to_stderr(self, capsys):
        """Deprecation warnings should go to stderr."""
        from scc_cli.deprecation import warn_deprecated

        # The implementation uses a dedicated _stderr_console that writes to stderr
        with patch("scc_cli.deprecation._stderr_console") as mock_console:
            warn_deprecated("old-cmd", "new-cmd")
            mock_console.print.assert_called_once()
            # The console itself is configured for stderr, no err= param needed

    def test_warn_deprecated_suppressed_in_json_mode(self):
        """Deprecation warnings should be suppressed in JSON mode."""
        from scc_cli.deprecation import warn_deprecated
        from scc_cli.output_mode import json_output_mode

        with patch("scc_cli.deprecation._stderr_console") as mock_console:
            with json_output_mode():
                warn_deprecated("old-cmd", "new-cmd")
                mock_console.print.assert_not_called()

    def test_warn_deprecated_suppressed_by_env_var(self, monkeypatch):
        """SCC_NO_DEPRECATION_WARN=1 should suppress warnings."""
        from scc_cli.deprecation import warn_deprecated

        monkeypatch.setenv("SCC_NO_DEPRECATION_WARN", "1")

        with patch("scc_cli.deprecation._stderr_console") as mock_console:
            warn_deprecated("old-cmd", "new-cmd")
            mock_console.print.assert_not_called()

    def test_warn_deprecated_includes_removal_version(self):
        """Warning should mention removal version."""
        from scc_cli.deprecation import warn_deprecated

        with patch("scc_cli.deprecation._stderr_console") as mock_console:
            warn_deprecated("old-cmd", "new-cmd", remove_version="2.0")
            call_args = mock_console.print.call_args[0][0]
            assert "2.0" in call_args
