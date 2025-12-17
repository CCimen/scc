"""Tests for auth.py authentication resolution module.

TDD approach: These tests define expected behavior BEFORE implementation.
Security-critical tests for shell injection prevention and trust model.

Test coverage targets:
- env:VAR resolution
- command:CMD safe execution (no shell injection)
- Platform-aware parsing
- Binary validation with shutil.which()
- Trust model (allow_command parameter)
- Error handling and sanitized messages
- Edge cases
"""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def clean_env(monkeypatch):
    """Remove auth-related environment variables."""
    for var in ["TEST_TOKEN", "GITLAB_TOKEN", "GITHUB_TOKEN", "SCC_ALLOW_REMOTE_COMMANDS"]:
        monkeypatch.delenv(var, raising=False)
    yield


@pytest.fixture
def env_with_token(monkeypatch):
    """Set up environment with a test token."""
    monkeypatch.setenv("TEST_TOKEN", "secret-token-value")
    yield


@pytest.fixture
def env_allow_remote_commands(monkeypatch):
    """Enable remote command execution."""
    monkeypatch.setenv("SCC_ALLOW_REMOTE_COMMANDS", "1")
    yield


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for resolve_auth with env: spec
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveAuthEnv:
    """Tests for env:VAR_NAME authentication resolution."""

    def test_env_returns_token_when_set(self, env_with_token):
        """Should return token from environment variable."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("env:TEST_TOKEN")

        assert result is not None
        assert result.token == "secret-token-value"
        assert result.source == "env"
        assert result.env_name == "TEST_TOKEN"

    def test_env_returns_none_when_not_set(self, clean_env):
        """Should return None when environment variable not set."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("env:NONEXISTENT_VAR")

        assert result is None

    def test_env_strips_whitespace_from_token(self, monkeypatch):
        """Should strip whitespace from token value."""
        from scc_cli.auth import resolve_auth

        monkeypatch.setenv("WHITESPACE_TOKEN", "  token-with-spaces  ")

        result = resolve_auth("env:WHITESPACE_TOKEN")

        assert result is not None
        assert result.token == "token-with-spaces"

    def test_env_strips_whitespace_from_var_name(self, env_with_token):
        """Should strip whitespace from variable name."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("env:  TEST_TOKEN  ")

        assert result is not None
        assert result.token == "secret-token-value"

    def test_env_returns_none_for_empty_token(self, monkeypatch):
        """Should return None when token is empty string."""
        from scc_cli.auth import resolve_auth

        monkeypatch.setenv("EMPTY_TOKEN", "")

        result = resolve_auth("env:EMPTY_TOKEN")

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for resolve_auth with command: spec
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveAuthCommand:
    """Tests for command:CMD authentication resolution."""

    def test_command_executes_without_shell(self):
        """CRITICAL: Should execute command with shell=False."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="my-token\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                resolve_auth("command:echo token")

            # Verify shell=False was passed
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs.get("shell") is False

    def test_command_returns_token_on_success(self):
        """Should return token from successful command output."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="secret-command-token\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                result = resolve_auth("command:echo token")

        assert result is not None
        assert result.token == "secret-command-token"
        assert result.source == "command"

    def test_command_returns_none_on_failure(self):
        """Should return None when command returns non-zero."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="error",
            )
            with patch("shutil.which", return_value="/bin/false"):
                result = resolve_auth("command:false")

        assert result is None

    def test_command_returns_none_on_empty_output(self):
        """Should return None when command output is empty."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="   \n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                result = resolve_auth("command:echo")

        assert result is None

    def test_command_strips_whitespace_from_output(self):
        """Should strip whitespace from command output."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="  token-value  \n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                result = resolve_auth("command:echo token")

        assert result is not None
        assert result.token == "token-value"

    def test_command_uses_10_second_timeout(self):
        """Should use 10 second timeout (reduced from 30s)."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="token\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                resolve_auth("command:echo token")

            call_kwargs = mock_run.call_args.kwargs
            assert call_kwargs.get("timeout") == 10


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for shell injection prevention (CRITICAL SECURITY TESTS)
# ═══════════════════════════════════════════════════════════════════════════════


class TestShellInjectionPrevention:
    """CRITICAL: Tests to verify shell injection is prevented."""

    def test_command_does_not_interpret_shell_metacharacters(self):
        """Should NOT interpret shell metacharacters like pipes, redirects, etc."""
        from scc_cli.auth import resolve_auth

        # Malicious command attempting shell injection
        malicious_cmd = "echo harmless; rm -rf /"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="harmless; rm -rf /\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                resolve_auth(f"command:{malicious_cmd}")

            # Should be called with list args, not shell string
            call_args = mock_run.call_args
            first_arg = call_args[0][0]
            assert isinstance(first_arg, list), "Should pass command as list, not string"
            assert call_args.kwargs.get("shell") is False

    def test_command_with_pipe_does_not_execute_second_command(self):
        """Pipe characters should NOT execute a second command."""
        from scc_cli.auth import resolve_auth

        # Attempted command injection via pipe
        malicious_cmd = "echo token | cat /etc/passwd"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="token | cat /etc/passwd\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                resolve_auth(f"command:{malicious_cmd}")

            # The pipe should be treated as a literal argument, not shell operator
            # With shell=False, this is safe
            assert mock_run.call_args.kwargs.get("shell") is False

    def test_command_with_backticks_does_not_execute(self):
        """Backticks should NOT execute embedded commands."""
        from scc_cli.auth import resolve_auth

        malicious_cmd = "echo `whoami`"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="`whoami`\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                resolve_auth(f"command:{malicious_cmd}")

            assert mock_run.call_args.kwargs.get("shell") is False

    def test_command_with_dollar_subshell_does_not_execute(self):
        """$(...) should NOT execute as subshell."""
        from scc_cli.auth import resolve_auth

        malicious_cmd = "echo $(cat /etc/passwd)"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="$(cat /etc/passwd)\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                resolve_auth(f"command:{malicious_cmd}")

            assert mock_run.call_args.kwargs.get("shell") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for binary validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestBinaryValidation:
    """Tests for executable validation with shutil.which()."""

    def test_raises_error_when_executable_not_found(self):
        """Should raise RuntimeError when executable not found."""
        from scc_cli.auth import resolve_auth

        with patch("shutil.which", return_value=None):
            with pytest.raises(RuntimeError) as exc_info:
                resolve_auth("command:nonexistent-command arg1")

            assert "not found" in str(exc_info.value).lower()
            assert "nonexistent-command" in str(exc_info.value)

    def test_uses_resolved_absolute_path(self):
        """Should use absolute path from shutil.which(), not raw command."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="token\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/usr/local/bin/my-command"):
                resolve_auth("command:my-command arg1 arg2")

            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "/usr/local/bin/my-command"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for platform-aware parsing
# ═══════════════════════════════════════════════════════════════════════════════


class TestPlatformAwareParsing:
    """Tests for platform-aware shlex.split() behavior."""

    def test_parses_quoted_arguments_correctly(self):
        """Should handle quoted arguments."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="token\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/cmd"):
                resolve_auth('command:cmd "arg with spaces" arg2')

            call_args = mock_run.call_args[0][0]
            # Should be split correctly with quoted arg preserved
            assert len(call_args) >= 2

    def test_handles_empty_command_string(self):
        """Should return None for empty command."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("command:   ")

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for trust model (allow_command parameter)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrustModel:
    """Tests for trust model distinguishing user config from remote org config."""

    def test_command_allowed_by_default(self):
        """command: should be allowed by default (for user config)."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="token\n",
                stderr="",
            )
            with patch("shutil.which", return_value="/bin/echo"):
                result = resolve_auth("command:echo token")

        assert result is not None

    def test_command_blocked_when_allow_command_false(self):
        """command: should be blocked when allow_command=False."""
        from scc_cli.auth import resolve_auth

        with pytest.raises(ValueError) as exc_info:
            resolve_auth("command:echo token", allow_command=False)

        assert "not allowed" in str(exc_info.value).lower()
        assert "SCC_ALLOW_REMOTE_COMMANDS" in str(exc_info.value)

    def test_env_allowed_even_when_allow_command_false(self):
        """env: should always be allowed regardless of allow_command."""
        from scc_cli.auth import resolve_auth

        with patch.dict(os.environ, {"MY_TOKEN": "secret"}):
            result = resolve_auth("env:MY_TOKEN", allow_command=False)

        assert result is not None
        assert result.token == "secret"


class TestRemoteCommandAllowed:
    """Tests for is_remote_command_allowed() function."""

    def test_returns_false_by_default(self, clean_env):
        """Should return False when env var not set."""
        from scc_cli.auth import is_remote_command_allowed

        assert is_remote_command_allowed() is False

    def test_returns_true_when_set_to_1(self, monkeypatch):
        """Should return True when SCC_ALLOW_REMOTE_COMMANDS=1."""
        from scc_cli.auth import is_remote_command_allowed

        monkeypatch.setenv("SCC_ALLOW_REMOTE_COMMANDS", "1")

        assert is_remote_command_allowed() is True

    def test_returns_true_when_set_to_true(self, monkeypatch):
        """Should return True when SCC_ALLOW_REMOTE_COMMANDS=true."""
        from scc_cli.auth import is_remote_command_allowed

        monkeypatch.setenv("SCC_ALLOW_REMOTE_COMMANDS", "true")

        assert is_remote_command_allowed() is True

    def test_returns_true_when_set_to_yes(self, monkeypatch):
        """Should return True when SCC_ALLOW_REMOTE_COMMANDS=yes."""
        from scc_cli.auth import is_remote_command_allowed

        monkeypatch.setenv("SCC_ALLOW_REMOTE_COMMANDS", "yes")

        assert is_remote_command_allowed() is True

    def test_returns_false_for_other_values(self, monkeypatch):
        """Should return False for values other than 1/true/yes."""
        from scc_cli.auth import is_remote_command_allowed

        monkeypatch.setenv("SCC_ALLOW_REMOTE_COMMANDS", "maybe")

        assert is_remote_command_allowed() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for error handling and sanitized messages
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    """Tests for error handling and message sanitization."""

    def test_invalid_auth_spec_raises_valueerror(self):
        """Should raise ValueError for invalid auth spec format."""
        from scc_cli.auth import resolve_auth

        with pytest.raises(ValueError) as exc_info:
            resolve_auth("invalid:spec")

        assert "Invalid auth spec" in str(exc_info.value)

    def test_timeout_raises_runtime_error(self):
        """Should raise RuntimeError on command timeout."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=10)
            with patch("shutil.which", return_value="/bin/slow"):
                with pytest.raises(RuntimeError) as exc_info:
                    resolve_auth("command:slow-command")

        assert "timed out" in str(exc_info.value).lower()

    def test_error_message_does_not_include_command(self):
        """CRITICAL: Error messages should NOT include command (may contain secrets)."""
        from scc_cli.auth import resolve_auth

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = OSError("Permission denied")
            with patch("shutil.which", return_value="/bin/cmd"):
                with pytest.raises(RuntimeError) as exc_info:
                    resolve_auth("command:cmd --secret=mysecrettoken")

        error_msg = str(exc_info.value)
        assert "mysecrettoken" not in error_msg
        assert "--secret" not in error_msg

    def test_invalid_command_syntax_raises_runtime_error(self):
        """Should raise RuntimeError for malformed command syntax."""
        from scc_cli.auth import resolve_auth

        # Unclosed quote in command
        with pytest.raises(RuntimeError) as exc_info:
            resolve_auth('command:echo "unclosed')

        assert "syntax" in str(exc_info.value).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_none_auth_spec_returns_none(self):
        """Should return None for None auth_spec."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth(None)

        assert result is None

    def test_empty_string_auth_spec_returns_none(self):
        """Should return None for empty string auth_spec."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("")

        assert result is None

    def test_whitespace_only_auth_spec_returns_none(self):
        """Should return None for whitespace-only auth_spec."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("   ")

        assert result is None

    def test_env_with_only_prefix_returns_none(self):
        """Should return None for 'env:' with no variable name."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("env:")

        assert result is None

    def test_command_with_only_prefix_returns_none(self):
        """Should return None for 'command:' with no command."""
        from scc_cli.auth import resolve_auth

        result = resolve_auth("command:")

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for AuthResult dataclass
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthResult:
    """Tests for AuthResult dataclass."""

    def test_authresult_is_frozen(self):
        """AuthResult should be immutable (frozen dataclass)."""
        from scc_cli.auth import AuthResult

        result = AuthResult(token="secret", source="env", env_name="MY_VAR")

        with pytest.raises(Exception):  # FrozenInstanceError
            result.token = "changed"

    def test_authresult_has_correct_fields(self):
        """AuthResult should have token, source, and env_name fields."""
        from scc_cli.auth import AuthResult

        result = AuthResult(token="test", source="command", env_name=None)

        assert result.token == "test"
        assert result.source == "command"
        assert result.env_name is None

    def test_authresult_env_name_optional(self):
        """env_name should be optional (defaults to None for command:)."""
        from scc_cli.auth import AuthResult

        result = AuthResult(token="test", source="command")

        assert result.env_name is None
