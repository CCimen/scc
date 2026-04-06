"""Tests for resume-after-drift edge cases and auth bootstrap failure handling.

Verifies:
- Codex session resume when auth volume deleted → auth bootstrap triggers
- Codex session resume when image removed → image auto-build triggers
- Explicit --provider overrides resume provider
- Session provider no longer in allowed_providers → ProviderNotAllowedError
- Legacy session with provider_id=None → falls back to claude (D032)
- Explicit --provider codex with missing auth in non-interactive → typed error
- Auth bootstrap callback failure → clean ProviderNotReadyError wrapping
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.commands.launch.auth_bootstrap import ensure_provider_auth
from scc_cli.commands.launch.preflight import (
    AuthStatus,
    ImageStatus,
    LaunchReadiness,
    ProviderResolutionSource,
    _ensure_auth,
    collect_launch_readiness,
    ensure_launch_ready,
    resolve_launch_provider,
)
from scc_cli.core.contracts import AuthReadiness, ProviderCapabilityProfile
from scc_cli.core.errors import ProviderNotAllowedError, ProviderNotReadyError

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _mock_adapters(
    *,
    connected_providers: tuple[str, ...] = ("claude", "codex"),
) -> MagicMock:
    """Build mock adapters that work with get_agent_provider dispatch.

    get_agent_provider looks up field names from _PROVIDER_DISPATCH:
      claude → adapters.agent_provider
      codex  → adapters.codex_agent_provider
    """
    adapters = MagicMock()

    def _make_provider(pid: str) -> MagicMock:
        provider = MagicMock()
        status = "present" if pid in connected_providers else "missing"
        provider.auth_check.return_value = AuthReadiness(
            status=status,
            mechanism="test",
            guidance=f"{pid} auth cache {status}",
        )
        provider.capability_profile.return_value = ProviderCapabilityProfile(
            provider_id=pid,
            display_name=pid.title(),
            required_destination_set=f"{pid}-core",
            supports_resume=False,
            supports_skills=True,
            supports_native_integrations=True,
        )
        return provider

    adapters.agent_provider = _make_provider("claude")
    adapters.codex_agent_provider = _make_provider("codex")
    return adapters


def _make_codex_provider_mock(
    *,
    auth_status: str = "present",
    bootstrap_raises: Exception | None = None,
) -> MagicMock:
    """Build a mock Codex provider adapter."""
    provider = MagicMock()
    provider.capability_profile.return_value = ProviderCapabilityProfile(
        provider_id="codex",
        display_name="Codex",
        required_destination_set="openai-core",
        supports_resume=False,
        supports_skills=True,
        supports_native_integrations=True,
    )
    provider.auth_check.return_value = AuthReadiness(
        status=auth_status,
        mechanism="auth_json_file",
        guidance="test",
    )
    if bootstrap_raises:
        provider.bootstrap_auth.side_effect = bootstrap_raises
    return provider


def _mock_org_with_allowed(allowed: tuple[str, ...]) -> MagicMock:
    """Build a mock NormalizedOrgConfig with a team that allows specific providers."""
    org = MagicMock()
    profile = MagicMock()
    profile.allowed_providers = allowed
    org.get_profile.return_value = profile
    return org


# ──────────────────────────────────────────────────────────────────────────────
# 1. Resume with deleted auth volume → provider stays codex, auth bootstrap needed
# ──────────────────────────────────────────────────────────────────────────────


class TestResumeWithDeletedAuthVolume:
    """When a Codex session is resumed but auth was deleted, SCC should
    trigger auth bootstrap for Codex — not silently switch to Claude."""

    def test_resolve_provider_stays_codex(self) -> None:
        """Resume provider='codex' resolves to codex regardless of auth state."""
        adapters = _mock_adapters(connected_providers=("claude",))  # codex not connected
        provider_id, source = resolve_launch_provider(
            cli_flag=None,
            resume_provider="codex",
            workspace_path=None,
            config_provider=None,
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=False,
        )
        assert provider_id == "codex"
        assert source == ProviderResolutionSource.RESUME

    @patch("scc_cli.commands.launch.preflight._check_image_available")
    def test_readiness_shows_auth_missing(self, mock_image: MagicMock) -> None:
        """collect_launch_readiness detects missing auth for resume provider."""
        mock_image.return_value = ImageStatus.AVAILABLE
        adapters = _mock_adapters(connected_providers=("claude",))  # codex auth missing

        readiness = collect_launch_readiness(
            "codex", ProviderResolutionSource.RESUME, adapters
        )
        assert readiness.provider_id == "codex"
        assert readiness.auth_status == AuthStatus.MISSING
        assert readiness.requires_auth_bootstrap is True
        assert readiness.launch_ready is False

    def test_ensure_ready_non_interactive_raises_with_auth_guidance(self) -> None:
        """Non-interactive resume with missing auth raises ProviderNotReadyError."""
        readiness = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.RESUME,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_launch_ready(
                readiness,
                adapters=MagicMock(),
                console=MagicMock(),
                non_interactive=True,
                show_notice=MagicMock(),
            )
        assert "codex" in exc_info.value.suggested_action.lower()
        assert "interactively" in exc_info.value.suggested_action.lower()


# ──────────────────────────────────────────────────────────────────────────────
# 2. Resume with image removed → auto-build (interactive) / fail (non-interactive)
# ──────────────────────────────────────────────────────────────────────────────


class TestResumeWithImageRemoved:
    """When a Codex session is resumed but the image was removed."""

    @patch("scc_cli.commands.launch.preflight._check_image_available")
    def test_readiness_shows_image_missing(self, mock_image: MagicMock) -> None:
        """collect_launch_readiness detects missing image."""
        mock_image.return_value = ImageStatus.MISSING
        adapters = _mock_adapters(connected_providers=("claude", "codex"))

        readiness = collect_launch_readiness(
            "codex", ProviderResolutionSource.RESUME, adapters
        )
        assert readiness.image_status == ImageStatus.MISSING
        assert readiness.requires_image_bootstrap is True
        assert readiness.launch_ready is False

    @patch("scc_cli.commands.launch.provider_image.ensure_provider_image")
    def test_ensure_ready_triggers_image_build_interactive(
        self, mock_build: MagicMock
    ) -> None:
        """Interactive mode triggers auto-build when image is missing."""
        readiness = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.RESUME,
            image_status=ImageStatus.MISSING,
            auth_status=AuthStatus.PRESENT,
            requires_image_bootstrap=True,
            requires_auth_bootstrap=False,
            launch_ready=False,
        )
        console_mock = MagicMock()
        notice_mock = MagicMock()
        ensure_launch_ready(
            readiness,
            adapters=MagicMock(),
            console=console_mock,
            non_interactive=False,
            show_notice=notice_mock,
        )
        mock_build.assert_called_once_with(
            "codex",
            console=console_mock,
            non_interactive=False,
            show_notice=notice_mock,
        )

    @patch("scc_cli.commands.launch.provider_image._provider_image_exists", return_value=False)
    @patch("scc_cli.commands.launch.provider_image.get_provider_build_command")
    def test_ensure_ready_fails_non_interactive_with_build_command(
        self, mock_cmd: MagicMock, _mock_exists: MagicMock
    ) -> None:
        """Non-interactive mode raises with build command in the error."""
        mock_cmd.return_value = ["docker", "build", "-t", "scc-agent-codex:latest", "."]

        readiness = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.RESUME,
            image_status=ImageStatus.MISSING,
            auth_status=AuthStatus.PRESENT,
            requires_image_bootstrap=True,
            requires_auth_bootstrap=False,
            launch_ready=False,
        )
        with pytest.raises(Exception) as exc_info:
            ensure_launch_ready(
                readiness,
                adapters=MagicMock(),
                console=MagicMock(),
                non_interactive=True,
                show_notice=MagicMock(),
            )
        # Should contain build instructions
        err = exc_info.value
        assert "docker build" in err.suggested_action.lower()


# ──────────────────────────────────────────────────────────────────────────────
# 3. Explicit --provider overrides resume provider
# ──────────────────────────────────────────────────────────────────────────────


class TestExplicitProviderOverridesResume:
    """CLI flag --provider claude overrides a codex resume session."""

    def test_cli_flag_overrides_resume_provider(self) -> None:
        """Explicit --provider claude wins over session resume_provider=codex."""
        adapters = _mock_adapters()
        provider_id, source = resolve_launch_provider(
            cli_flag="claude",
            resume_provider="codex",
            workspace_path=None,
            config_provider=None,
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=False,
        )
        assert provider_id == "claude"
        assert source == ProviderResolutionSource.EXPLICIT

    def test_cli_flag_overrides_with_different_providers(self) -> None:
        """Also works when --provider codex overrides a claude session."""
        adapters = _mock_adapters()
        provider_id, source = resolve_launch_provider(
            cli_flag="codex",
            resume_provider="claude",
            workspace_path=None,
            config_provider=None,
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=False,
        )
        assert provider_id == "codex"
        assert source == ProviderResolutionSource.EXPLICIT


# ──────────────────────────────────────────────────────────────────────────────
# 4. Session provider no longer allowed → ProviderNotAllowedError
# ──────────────────────────────────────────────────────────────────────────────


class TestResumeProviderNoLongerAllowed:
    """When a session has provider_id='codex' but team policy now only allows claude."""

    def test_resume_provider_not_in_allowed_raises(self) -> None:
        """Resume provider blocked by team policy raises ProviderNotAllowedError."""
        adapters = _mock_adapters()
        org = _mock_org_with_allowed(("claude",))

        with pytest.raises(ProviderNotAllowedError) as exc_info:
            resolve_launch_provider(
                cli_flag=None,
                resume_provider="codex",
                workspace_path=None,
                config_provider=None,
                normalized_org=org,
                team="team-a",
                adapters=adapters,
                non_interactive=False,
            )
        assert exc_info.value.provider_id == "codex"
        assert "claude" in exc_info.value.allowed_providers

    def test_explicit_cli_provider_not_allowed_also_raises(self) -> None:
        """Even explicit --provider codex fails if team policy blocks it."""
        adapters = _mock_adapters()
        org = _mock_org_with_allowed(("claude",))

        with pytest.raises(ProviderNotAllowedError) as exc_info:
            resolve_launch_provider(
                cli_flag="codex",
                resume_provider=None,
                workspace_path=None,
                config_provider=None,
                normalized_org=org,
                team="team-a",
                adapters=adapters,
                non_interactive=False,
            )
        assert exc_info.value.provider_id == "codex"


# ──────────────────────────────────────────────────────────────────────────────
# 5. Legacy session with provider_id=None → falls back to claude (D032)
# ──────────────────────────────────────────────────────────────────────────────


class TestLegacySessionFallback:
    """Legacy sessions with no provider_id fall back to claude per D032."""

    def test_none_resume_provider_falls_through(self) -> None:
        """resume_provider=None means the resume tier is skipped in precedence."""
        adapters = _mock_adapters(connected_providers=("claude",))
        provider_id, source = resolve_launch_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_path=None,
            config_provider=None,
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=True,
        )
        # With only claude connected and no other preferences, auto-single
        # picks claude
        assert provider_id == "claude"
        assert source == ProviderResolutionSource.AUTO_SINGLE

    def test_none_resume_with_global_claude_preference(self) -> None:
        """Legacy session + global preference='claude' → resolves to claude."""
        adapters = _mock_adapters(connected_providers=("claude", "codex"))
        provider_id, source = resolve_launch_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_path=None,
            config_provider="claude",
            normalized_org=None,
            team=None,
            adapters=adapters,
            non_interactive=True,
        )
        assert provider_id == "claude"
        assert source == ProviderResolutionSource.GLOBAL_PREFERRED

    def test_legacy_session_multiple_connected_non_interactive_raises(self) -> None:
        """Legacy session (None provider) with multiple connected providers in
        non-interactive mode raises ProviderNotReadyError — never silently picks."""
        adapters = _mock_adapters(connected_providers=("claude", "codex"))
        with pytest.raises(ProviderNotReadyError):
            resolve_launch_provider(
                cli_flag=None,
                resume_provider=None,
                workspace_path=None,
                config_provider=None,
                normalized_org=None,
                team=None,
                adapters=adapters,
                non_interactive=True,
            )


# ──────────────────────────────────────────────────────────────────────────────
# 6. Explicit --provider codex + missing auth in non-interactive → typed error
# ──────────────────────────────────────────────────────────────────────────────


class TestExplicitProviderMissingAuthNonInteractive:
    """--provider codex in non-interactive mode with missing auth → ProviderNotReadyError."""

    def test_non_interactive_missing_auth_raises_with_guidance(self) -> None:
        """Non-interactive launch with missing auth gives actionable message."""
        readiness = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_launch_ready(
                readiness,
                adapters=MagicMock(),
                console=MagicMock(),
                non_interactive=True,
                show_notice=MagicMock(),
            )
        err = exc_info.value
        assert "non-interactive" in err.user_message.lower()
        assert "scc start --provider codex" in err.suggested_action
        assert "interactively" in err.suggested_action.lower()

    def test_non_interactive_missing_auth_does_not_prompt(self) -> None:
        """Non-interactive mode never calls show_notice."""
        readiness = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        show_notice = MagicMock()
        with pytest.raises(ProviderNotReadyError):
            ensure_launch_ready(
                readiness,
                adapters=MagicMock(),
                console=MagicMock(),
                non_interactive=True,
                show_notice=show_notice,
            )
        show_notice.assert_not_called()

    def test_interactive_missing_auth_calls_show_notice(self) -> None:
        """Interactive mode shows notice before auth bootstrap."""
        readiness = LaunchReadiness(
            provider_id="codex",
            resolution_source=ProviderResolutionSource.EXPLICIT,
            image_status=ImageStatus.AVAILABLE,
            auth_status=AuthStatus.MISSING,
            requires_image_bootstrap=False,
            requires_auth_bootstrap=True,
            launch_ready=False,
        )
        show_notice = MagicMock()
        _ensure_auth(
            readiness,
            adapters=MagicMock(),
            non_interactive=False,
            show_notice=show_notice,
        )
        show_notice.assert_called_once()
        call_args = show_notice.call_args[0]
        assert "authenticating" in call_args[0].lower()


# ──────────────────────────────────────────────────────────────────────────────
# 7. Auth bootstrap callback failure → clean ProviderNotReadyError wrapping
# ──────────────────────────────────────────────────────────────────────────────


class TestAuthBootstrapCallbackFailure:
    """When bootstrap_auth() raises an unexpected error, ensure_provider_auth
    wraps it in a clean ProviderNotReadyError with guidance."""

    def test_port_unavailable_raises_provider_not_ready(self) -> None:
        """Codex port-unavailable produces ProviderNotReadyError with guidance."""
        with patch(
            "scc_cli.adapters.codex_auth._is_local_callback_port_available",
            return_value=False,
        ):
            from scc_cli.adapters.codex_auth import run_codex_browser_auth

            with pytest.raises(ProviderNotReadyError) as exc_info:
                run_codex_browser_auth()
            assert "1455" in exc_info.value.user_message
            assert "port" in exc_info.value.suggested_action.lower()

    def test_bootstrap_auth_oserror_wrapped_in_provider_not_ready(self) -> None:
        """OSError from bootstrap_auth() is wrapped in ProviderNotReadyError."""
        plan = MagicMock()
        plan.resume = False

        provider = _make_codex_provider_mock(
            auth_status="missing",
            bootstrap_raises=OSError("socket binding failed"),
        )
        deps = MagicMock()
        deps.agent_provider = provider

        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_provider_auth(
                plan,
                dependencies=deps,
                non_interactive=False,
                show_notice=MagicMock(),
            )
        err = exc_info.value
        assert "codex" in err.provider_id
        assert "interactively" in err.suggested_action.lower()

    def test_bootstrap_auth_file_not_found_wrapped(self) -> None:
        """FileNotFoundError (Docker not installed) is wrapped cleanly."""
        plan = MagicMock()
        plan.resume = False

        provider = _make_codex_provider_mock(
            auth_status="missing",
            bootstrap_raises=FileNotFoundError("docker: command not found"),
        )
        deps = MagicMock()
        deps.agent_provider = provider

        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_provider_auth(
                plan,
                dependencies=deps,
                non_interactive=False,
                show_notice=MagicMock(),
            )
        err = exc_info.value
        assert "codex" in err.provider_id
        assert "sign-in" in err.suggested_action.lower()

    def test_bootstrap_auth_subprocess_timeout_wrapped(self) -> None:
        """subprocess.TimeoutExpired is wrapped in ProviderNotReadyError."""
        plan = MagicMock()
        plan.resume = False

        provider = _make_codex_provider_mock(
            auth_status="missing",
            bootstrap_raises=subprocess.TimeoutExpired(cmd="docker", timeout=30),
        )
        deps = MagicMock()
        deps.agent_provider = provider

        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_provider_auth(
                plan,
                dependencies=deps,
                non_interactive=False,
                show_notice=MagicMock(),
            )
        err = exc_info.value
        assert "codex" in err.provider_id

    def test_provider_not_ready_from_bootstrap_passes_through(self) -> None:
        """ProviderNotReadyError from bootstrap_auth passes through unchanged."""
        plan = MagicMock()
        plan.resume = False

        original_error = ProviderNotReadyError(
            provider_id="codex",
            user_message="Codex browser sign-in did not complete successfully.",
            suggested_action="Retry the sign-in flow.",
        )
        provider = _make_codex_provider_mock(
            auth_status="missing",
            bootstrap_raises=original_error,
        )
        deps = MagicMock()
        deps.agent_provider = provider

        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_provider_auth(
                plan,
                dependencies=deps,
                non_interactive=False,
                show_notice=MagicMock(),
            )
        # Should be the exact same error, not a re-wrap
        assert exc_info.value is original_error

    def test_resume_skips_auth_bootstrap(self) -> None:
        """When plan.resume=True, ensure_provider_auth returns early."""
        plan = MagicMock()
        plan.resume = True

        provider = _make_codex_provider_mock(auth_status="missing")
        deps = MagicMock()
        deps.agent_provider = provider

        # Should not raise — resume skips auth bootstrap entirely
        ensure_provider_auth(
            plan,
            dependencies=deps,
            non_interactive=False,
            show_notice=MagicMock(),
        )
        provider.auth_check.assert_not_called()
        provider.bootstrap_auth.assert_not_called()
