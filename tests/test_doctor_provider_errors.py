"""Tests for provider-aware doctor types and check functions.

Covers:
- ProviderNotReadyError message/action/exit_code
- ProviderImageMissingError message/action/exit_code
- AuthReadiness field access
- CheckResult category default and explicit values
- check_provider_auth via adapter-owned auth_check() (D037)
"""

from __future__ import annotations

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
        err = ProviderImageMissingError(provider_id="codex", image_ref="scc-agent-codex:latest")
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


def _make_fake_adapters(
    *,
    claude_readiness: AuthReadiness | None = None,
    codex_readiness: AuthReadiness | None = None,
    claude_exc: Exception | None = None,
    codex_exc: Exception | None = None,
) -> MagicMock:
    """Build a fake DefaultAdapters with configurable auth_check() results."""
    claude_provider = MagicMock()
    codex_provider = MagicMock()

    if claude_exc is not None:
        claude_provider.auth_check.side_effect = claude_exc
    elif claude_readiness is not None:
        claude_provider.auth_check.return_value = claude_readiness
    else:
        claude_provider.auth_check.return_value = AuthReadiness(
            status="present", mechanism="oauth_file", guidance="No action needed"
        )

    if codex_exc is not None:
        codex_provider.auth_check.side_effect = codex_exc
    elif codex_readiness is not None:
        codex_provider.auth_check.return_value = codex_readiness
    else:
        codex_provider.auth_check.return_value = AuthReadiness(
            status="present", mechanism="auth_json_file", guidance="No action needed"
        )

    adapters = MagicMock()
    adapters.agent_provider = claude_provider
    adapters.codex_agent_provider = codex_provider
    return adapters


class TestCheckProviderAuth:
    """check_provider_auth delegates to adapter-owned auth_check() (D037)."""

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_happy_path_claude_auth_present(self, mock_adapters: MagicMock) -> None:
        mock_adapters.return_value = _make_fake_adapters()
        result = check_provider_auth(provider_id="claude")
        assert result.passed is True
        assert result.category == "provider"
        assert "auth cache present" in result.message
        assert "oauth_file" in result.message

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_claude_auth_missing(self, mock_adapters: MagicMock) -> None:
        mock_adapters.return_value = _make_fake_adapters(
            claude_readiness=AuthReadiness(
                status="missing",
                mechanism="oauth_file",
                guidance="Run 'scc start --provider claude' to authenticate.",
            )
        )
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert result.category == "provider"
        assert "auth cache missing" in result.message

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_codex_auth_present(self, mock_adapters: MagicMock) -> None:
        mock_adapters.return_value = _make_fake_adapters()
        result = check_provider_auth(provider_id="codex")
        assert result.passed is True
        assert "auth cache present" in result.message
        assert "auth_json_file" in result.message

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_codex_auth_missing(self, mock_adapters: MagicMock) -> None:
        mock_adapters.return_value = _make_fake_adapters(
            codex_readiness=AuthReadiness(
                status="missing",
                mechanism="auth_json_file",
                guidance="Run 'scc start --provider codex' to authenticate.",
            )
        )
        result = check_provider_auth(provider_id="codex")
        assert result.passed is False
        assert result.category == "provider"

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_unknown_provider_fallback(self, mock_adapters: MagicMock) -> None:
        mock_adapters.return_value = _make_fake_adapters()
        result = check_provider_auth(provider_id="nonexistent")
        assert result.passed is False
        assert "Unknown provider" in result.message
        assert result.category == "provider"

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_adapter_exception_handled(self, mock_adapters: MagicMock) -> None:
        mock_adapters.return_value = _make_fake_adapters(
            claude_exc=RuntimeError("Docker not reachable")
        )
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert result.category == "provider"
        assert "Auth check failed" in result.message

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_bootstrap_failure_handled(self, mock_adapters: MagicMock) -> None:
        mock_adapters.side_effect = RuntimeError("Cannot initialise")
        result = check_provider_auth(provider_id="claude")
        assert result.passed is False
        assert "Could not initialise" in result.message
        assert result.category == "provider"

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_truthful_wording_present(self, mock_adapters: MagicMock) -> None:
        """D037: wording says 'auth cache present', not 'logged in'."""
        mock_adapters.return_value = _make_fake_adapters()
        result = check_provider_auth(provider_id="claude")
        assert "auth cache present" in result.message
        assert "logged in" not in result.message.lower()

    @patch("scc_cli.bootstrap.get_default_adapters")
    def test_truthful_wording_missing(self, mock_adapters: MagicMock) -> None:
        """D037: wording says 'auth cache missing', not 'not logged in'."""
        mock_adapters.return_value = _make_fake_adapters(
            claude_readiness=AuthReadiness(
                status="missing", mechanism="oauth_file", guidance="Authenticate first"
            )
        )
        result = check_provider_auth(provider_id="claude")
        assert "auth cache missing" in result.message
        assert "logged in" not in result.message.lower()
