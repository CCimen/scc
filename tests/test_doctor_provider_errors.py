"""Tests for provider-aware doctor types and check functions.

Covers:
- ProviderNotReadyError message/action/exit_code
- ProviderImageMissingError message/action/exit_code
- AuthReadiness field access
- CheckResult category default and explicit values
- check_provider_auth happy path, missing auth, volume missing, subprocess
  timeout, unknown provider fallback
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.core.contracts import AuthReadiness
from scc_cli.core.errors import ProviderImageMissingError, ProviderNotReadyError
from scc_cli.doctor.checks.environment import check_provider_auth
from scc_cli.doctor.types import CheckResult


# ---------------------------------------------------------------------------
# ProviderNotReadyError
# ---------------------------------------------------------------------------


class TestProviderNotReadyError:
    """ProviderNotReadyError carries provider_id and auto-populates messages."""

    def test_message_includes_provider_id(self) -> None:
        err = ProviderNotReadyError(provider_id="codex")
        assert "codex" in err.user_message
        assert "not ready" in err.user_message

    def test_suggested_action_includes_doctor_command(self) -> None:
        err = ProviderNotReadyError(provider_id="codex")
        assert "scc doctor --provider codex" in err.suggested_action

    def test_exit_code_is_3(self) -> None:
        err = ProviderNotReadyError(provider_id="claude")
        assert err.exit_code == 3

    def test_str_returns_user_message(self) -> None:
        err = ProviderNotReadyError(provider_id="claude")
        assert str(err) == err.user_message

    def test_custom_message_preserved(self) -> None:
        err = ProviderNotReadyError(
            provider_id="claude",
            user_message="Custom not ready",
            suggested_action="Do this instead",
        )
        assert err.user_message == "Custom not ready"
        assert err.suggested_action == "Do this instead"


# ---------------------------------------------------------------------------
# ProviderImageMissingError
# ---------------------------------------------------------------------------


class TestProviderImageMissingError:
    """ProviderImageMissingError carries provider_id and optional image_ref."""

    def test_message_includes_provider_and_image(self) -> None:
        err = ProviderImageMissingError(
            provider_id="codex", image_ref="scc-agent-codex:latest"
        )
        assert "codex" in err.user_message
        assert "scc-agent-codex:latest" in err.user_message

    def test_message_without_image_ref(self) -> None:
        err = ProviderImageMissingError(provider_id="codex")
        assert "codex" in err.user_message
        # No image detail appended
        assert "()" not in err.user_message

    def test_suggested_action_includes_build_command(self) -> None:
        err = ProviderImageMissingError(provider_id="codex")
        assert "images/scc-agent-codex/" in err.suggested_action

    def test_exit_code_is_3(self) -> None:
        err = ProviderImageMissingError(provider_id="claude")
        assert err.exit_code == 3

    def test_custom_messages_preserved(self) -> None:
        err = ProviderImageMissingError(
            provider_id="claude",
            user_message="Image gone",
            suggested_action="Rebuild it",
        )
        assert err.user_message == "Image gone"
        assert err.suggested_action == "Rebuild it"


# ---------------------------------------------------------------------------
# AuthReadiness
# ---------------------------------------------------------------------------


class TestAuthReadiness:
    """AuthReadiness is a frozen dataclass with status, mechanism, guidance."""

    def test_field_access(self) -> None:
        ar = AuthReadiness(
            status="present",
            mechanism="oauth_file",
            guidance="No action needed",
        )
        assert ar.status == "present"
        assert ar.mechanism == "oauth_file"
        assert ar.guidance == "No action needed"

    def test_frozen(self) -> None:
        ar = AuthReadiness(status="missing", mechanism="auth_json_file", guidance="Login")
        with pytest.raises(AttributeError):
            ar.status = "present"  # type: ignore[misc]

    def test_missing_status(self) -> None:
        ar = AuthReadiness(
            status="missing",
            mechanism="auth_json_file",
            guidance="Run codex auth to authenticate",
        )
        assert ar.status == "missing"
        assert ar.mechanism == "auth_json_file"


# ---------------------------------------------------------------------------
# CheckResult.category
# ---------------------------------------------------------------------------


class TestCheckResultCategory:
    """CheckResult has a category field defaulting to 'general'."""

    def test_default_category_is_general(self) -> None:
        cr = CheckResult(name="Test", passed=True, message="ok")
        assert cr.category == "general"

    def test_explicit_category(self) -> None:
        cr = CheckResult(name="Test", passed=True, message="ok", category="provider")
        assert cr.category == "provider"


# ---------------------------------------------------------------------------
# check_provider_auth
# ---------------------------------------------------------------------------


def _mock_subprocess_run(
    *,
    volume_rc: int = 0,
    file_rc: int = 0,
    volume_exc: Exception | None = None,
    file_exc: Exception | None = None,
) -> MagicMock:
    """Build a side-effect callable for subprocess.run that routes by subcommand."""

    def _side_effect(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        # volume inspect
        if "volume" in cmd and "inspect" in cmd:
            if volume_exc is not None:
                raise volume_exc
            return subprocess.CompletedProcess(cmd, volume_rc, b"", b"")
        # docker run ... test -f ...
        if "run" in cmd and "test" in cmd:
            if file_exc is not None:
                raise file_exc
            return subprocess.CompletedProcess(cmd, file_rc, b"", b"")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    return MagicMock(side_effect=_side_effect)


class TestCheckProviderAuth:
    """check_provider_auth probes Docker volumes for auth credentials."""

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_happy_path_auth_present(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_subprocess_run(volume_rc=0, file_rc=0).side_effect
        result = check_provider_auth(provider_id="claude")
        assert result.passed is True
        assert result.category == "provider"
        assert ".credentials.json" in result.message

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_auth_missing(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_subprocess_run(volume_rc=0, file_rc=1).side_effect
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert result.category == "provider"
        assert ".credentials.json" in result.message

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_codex_auth_file(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_subprocess_run(volume_rc=0, file_rc=0).side_effect
        result = check_provider_auth(provider_id="codex")
        assert result.passed is True
        assert "auth.json" in result.message

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_volume_missing(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_subprocess_run(volume_rc=1).side_effect
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert "does not exist" in result.message
        assert result.category == "provider"

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_subprocess_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_subprocess_run(
            volume_exc=subprocess.TimeoutExpired(cmd=["docker"], timeout=10),
        ).side_effect
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert result.category == "provider"

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_file_check_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_subprocess_run(
            volume_rc=0,
            file_exc=subprocess.TimeoutExpired(cmd=["docker"], timeout=30),
        ).side_effect
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert "Timed out" in result.message
        assert result.category == "provider"

    def test_unknown_provider_fallback(self) -> None:
        result = check_provider_auth(provider_id="nonexistent")
        assert result.passed is False
        assert "Unknown provider" in result.message
        assert result.category == "provider"

    @patch("scc_cli.doctor.checks.environment.subprocess.run")
    def test_docker_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = _mock_subprocess_run(
            volume_exc=FileNotFoundError("docker not found"),
        ).side_effect
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert result.category == "provider"
