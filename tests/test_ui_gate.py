"""Tests for ui/gate.py - Interactivity policy enforcement.

Test Categories:
- Gate priority order tests (JSON > --no-interactive > CI > non-TTY > default)
- InteractivityContext creation tests
- require_selection_or_prompt behavior tests
- CI environment detection tests
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from scc_cli.errors import UsageError
from scc_cli.ui.gate import (
    InteractivityContext,
    InteractivityMode,
    _is_ci_environment,
    _is_tty_available,
    is_interactive_allowed,
    require_selection_or_prompt,
    validate_mode_flags,
)


class TestValidateModeFlagsA2:
    """Test validate_mode_flags() fast fail validation (A.2).

    This function enforces that --json cannot be combined with interactive flags,
    failing fast with a clear error rather than silently ignoring flags.
    """

    def test_no_conflict_when_not_json_mode(self) -> None:
        """No error raised when json_mode is False."""
        # Should not raise even with all interactive flags set
        validate_mode_flags(
            json_mode=False,
            interactive=True,
            select=True,
            dashboard=True,
        )

    def test_no_conflict_when_no_interactive_flags(self) -> None:
        """No error raised when json_mode is True but no interactive flags."""
        validate_mode_flags(json_mode=True)

    def test_json_with_interactive_raises_usage_error(self) -> None:
        """--json with --interactive raises UsageError."""
        with pytest.raises(UsageError) as exc_info:
            validate_mode_flags(json_mode=True, interactive=True)

        assert "--interactive" in str(exc_info.value.user_message)

    def test_json_with_select_raises_usage_error(self) -> None:
        """--json with --select raises UsageError."""
        with pytest.raises(UsageError) as exc_info:
            validate_mode_flags(json_mode=True, select=True)

        assert "--select" in str(exc_info.value.user_message)

    def test_json_with_dashboard_raises_usage_error(self) -> None:
        """--json with --dashboard raises UsageError."""
        with pytest.raises(UsageError) as exc_info:
            validate_mode_flags(json_mode=True, dashboard=True)

        assert "--dashboard" in str(exc_info.value.user_message)

    def test_json_with_multiple_flags_lists_all_in_error(self) -> None:
        """Multiple conflicting flags are all listed in error message."""
        with pytest.raises(UsageError) as exc_info:
            validate_mode_flags(
                json_mode=True,
                interactive=True,
                select=True,
            )

        msg = str(exc_info.value.user_message)
        assert "--interactive" in msg
        assert "--select" in msg

    def test_error_includes_suggested_action(self) -> None:
        """UsageError includes actionable suggestion."""
        with pytest.raises(UsageError) as exc_info:
            validate_mode_flags(json_mode=True, interactive=True)

        assert exc_info.value.suggested_action is not None
        assert "Remove" in exc_info.value.suggested_action


class TestIsInteractiveAllowed:
    """Test is_interactive_allowed() priority order."""

    def test_json_mode_forbids_interactive(self) -> None:
        """Priority 1: --json flag always blocks interactive UI."""
        # JSON mode should block even if everything else allows interactive
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                assert not is_interactive_allowed(json_mode=True)

    def test_no_interactive_flag_forbids_interactive(self) -> None:
        """Priority 2: --no-interactive flag blocks interactive UI."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                assert not is_interactive_allowed(no_interactive_flag=True)

    def test_ci_environment_forbids_interactive(self) -> None:
        """Priority 3: CI environment blocks interactive UI."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=True):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                assert not is_interactive_allowed()

    def test_non_tty_forbids_interactive(self) -> None:
        """Priority 4: Non-TTY stdin blocks interactive UI."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=False):
                assert not is_interactive_allowed()

    def test_interactive_flag_allows_when_tty_available(self) -> None:
        """Priority 5: --interactive flag allows interactive if TTY available."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                assert is_interactive_allowed(interactive_flag=True)

    def test_default_allows_in_tty(self) -> None:
        """Priority 6: Default behavior allows interactive in TTY."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                assert is_interactive_allowed()

    def test_priority_json_beats_interactive_flag(self) -> None:
        """JSON mode takes precedence over --interactive flag."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                assert not is_interactive_allowed(json_mode=True, interactive_flag=True)

    def test_priority_no_interactive_beats_interactive_flag(self) -> None:
        """--no-interactive takes precedence over --interactive flag."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                result = is_interactive_allowed(no_interactive_flag=True, interactive_flag=True)
                assert not result


class TestInteractivityContext:
    """Test InteractivityContext creation and methods."""

    def test_create_from_json_mode(self) -> None:
        """Context with json_mode=True has NON_INTERACTIVE mode."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create(json_mode=True)
                assert ctx.mode == InteractivityMode.NON_INTERACTIVE
                assert ctx.is_json_output is True

    def test_create_from_force_interactive(self) -> None:
        """Context with force_interactive=True has INTERACTIVE mode (if TTY)."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create(force_interactive=True)
                assert ctx.mode == InteractivityMode.INTERACTIVE

    def test_create_default_interactive_in_tty(self) -> None:
        """Default context is INTERACTIVE when in TTY."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create()
                assert ctx.mode == InteractivityMode.INTERACTIVE

    def test_create_non_interactive_when_no_tty(self) -> None:
        """Context is NON_INTERACTIVE when no TTY available."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=False):
                ctx = InteractivityContext.create()
                assert ctx.mode == InteractivityMode.NON_INTERACTIVE

    def test_allows_prompt_false_when_json(self) -> None:
        """allows_prompt() returns False when json output enabled."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create(json_mode=True)
                assert ctx.allows_prompt() is False

    def test_allows_prompt_true_when_interactive(self) -> None:
        """allows_prompt() returns True in interactive mode."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create()
                assert ctx.allows_prompt() is True

    def test_requires_confirmation_respects_force_yes(self) -> None:
        """requires_confirmation() returns False when force_yes=True."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create(force_yes=True)
                assert ctx.requires_confirmation() is False

    def test_requires_confirmation_true_by_default(self) -> None:
        """requires_confirmation() returns True by default in interactive mode."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create()
                assert ctx.requires_confirmation() is True

    def test_requires_confirmation_false_when_non_interactive(self) -> None:
        """requires_confirmation() returns False when non-interactive."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=False):
                ctx = InteractivityContext.create()
                assert ctx.requires_confirmation() is False

    def test_context_is_frozen(self) -> None:
        """InteractivityContext is immutable (frozen)."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create()
                with pytest.raises(AttributeError):
                    ctx.mode = InteractivityMode.NON_INTERACTIVE  # type: ignore[misc]


class TestRequireSelectionOrPrompt:
    """Test require_selection_or_prompt() gate logic."""

    def test_explicit_selection_returned_without_picker(self) -> None:
        """Explicit value returned immediately without calling picker."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create()
                picker_called = False

                def picker() -> str:
                    nonlocal picker_called
                    picker_called = True
                    return "picked"

                result = require_selection_or_prompt(
                    selection="explicit", picker_fn=picker, arg_name="test", ctx=ctx
                )

                assert result == "explicit"
                assert not picker_called

    def test_picker_called_when_no_selection_and_interactive(self) -> None:
        """Picker function called when no selection and interactive allowed."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create()

                def picker() -> str:
                    return "picked_value"

                result = require_selection_or_prompt(
                    selection=None, picker_fn=picker, arg_name="test", ctx=ctx
                )

                assert result == "picked_value"

    def test_missing_selection_in_non_interactive_raises_usage_error(self) -> None:
        """Missing selection in non-interactive mode raises SystemExit(EXIT_USAGE)."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=False):
                ctx = InteractivityContext.create()

                def picker() -> str:
                    return "should not be called"

                with pytest.raises(SystemExit) as exc_info:
                    require_selection_or_prompt(
                        selection=None, picker_fn=picker, arg_name="team-name", ctx=ctx
                    )

                assert exc_info.value.code == 2  # EXIT_USAGE

    def test_user_cancel_returns_none_and_exits_success(self) -> None:
        """User cancelling picker (returning None) exits with EXIT_SUCCESS."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=True):
                ctx = InteractivityContext.create()

                def picker() -> None:
                    return None  # User cancelled

                with pytest.raises(SystemExit) as exc_info:
                    require_selection_or_prompt(
                        selection=None, picker_fn=picker, arg_name="test", ctx=ctx
                    )

                assert exc_info.value.code == 0  # EXIT_SUCCESS

    def test_picker_not_called_when_explicit_selection_provided(self) -> None:
        """Picker is not called even in non-interactive mode if selection provided."""
        with patch("scc_cli.ui.gate._is_ci_environment", return_value=False):
            with patch("scc_cli.ui.gate._is_tty_available", return_value=False):
                ctx = InteractivityContext.create()
                picker_called = False

                def picker() -> str:
                    nonlocal picker_called
                    picker_called = True
                    return "should_not_be_used"

                result = require_selection_or_prompt(
                    selection="explicit_value",
                    picker_fn=picker,
                    arg_name="test",
                    ctx=ctx,
                )

                assert result == "explicit_value"
                assert not picker_called


class TestCIEnvironmentDetection:
    """Test CI environment detection patterns."""

    @pytest.mark.parametrize(
        "env_var,env_value,expected",
        [
            ("CI", "true", True),
            ("CI", "TRUE", True),
            ("CI", "1", True),
            ("CI", "yes", True),
            ("CONTINUOUS_INTEGRATION", "true", True),
            ("BUILD_NUMBER", "123", False),  # BUILD_NUMBER needs true/1/yes value
            ("BUILD_NUMBER", "true", True),
            ("GITHUB_ACTIONS", "true", True),
            ("GITLAB_CI", "true", True),
        ],
    )
    def test_ci_env_detection(
        self, monkeypatch: pytest.MonkeyPatch, env_var: str, env_value: str, expected: bool
    ) -> None:
        """Various CI environment variables are detected correctly."""
        # Clear all CI-related env vars first
        for var in [
            "CI",
            "CONTINUOUS_INTEGRATION",
            "BUILD_NUMBER",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
        ]:
            monkeypatch.delenv(var, raising=False)

        # Set the test env var
        monkeypatch.setenv(env_var, env_value)

        assert _is_ci_environment() == expected

    @pytest.mark.parametrize(
        "env_value,expected",
        [
            ("true", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("", False),  # Empty = not CI
            ("false", False),  # Explicit false = not CI
            ("0", False),
            ("no", False),
        ],
    )
    def test_ci_env_values(
        self, monkeypatch: pytest.MonkeyPatch, env_value: str, expected: bool
    ) -> None:
        """Various CI environment variable values are handled correctly."""
        # Clear all CI-related env vars first
        for var in [
            "CI",
            "CONTINUOUS_INTEGRATION",
            "BUILD_NUMBER",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
        ]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv("CI", env_value)
        assert _is_ci_environment() == expected

    def test_no_ci_env_returns_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """No CI environment variables returns False."""
        for var in [
            "CI",
            "CONTINUOUS_INTEGRATION",
            "BUILD_NUMBER",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
        ]:
            monkeypatch.delenv(var, raising=False)

        assert _is_ci_environment() is False


class TestTTYDetection:
    """Test TTY detection."""

    def test_is_tty_available_returns_bool(self) -> None:
        """_is_tty_available returns a boolean."""
        result = _is_tty_available()
        assert isinstance(result, bool)


class TestInteractivityModeEnum:
    """Test InteractivityMode enum values."""

    def test_interactive_mode_exists(self) -> None:
        """INTERACTIVE mode exists."""
        assert InteractivityMode.INTERACTIVE is not None

    def test_non_interactive_mode_exists(self) -> None:
        """NON_INTERACTIVE mode exists."""
        assert InteractivityMode.NON_INTERACTIVE is not None

    def test_modes_are_distinct(self) -> None:
        """INTERACTIVE and NON_INTERACTIVE are different values."""
        assert InteractivityMode.INTERACTIVE != InteractivityMode.NON_INTERACTIVE
