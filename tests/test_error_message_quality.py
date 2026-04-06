"""Tests for error message quality — every user-facing error is actionable and truthful.

Verifies:
- ProviderNotReadyError messages include 'scc doctor' or 'scc start' guidance
- InvalidProviderError lists valid provider names
- ProviderImageMissingError includes the build command
- Non-interactive launch failures give exact fix command
- Doctor check failures wrap Docker errors with SCC context
- ProviderNotAllowedError names the allowed providers
- SandboxLaunchError surfaces stderr
- ensure_provider_auth wraps raw exceptions with actionable guidance
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scc_cli.core.contracts import AuthReadiness
from scc_cli.core.errors import (
    ConfigError,
    DockerDaemonNotRunningError,
    DockerNotFoundError,
    ExistingSandboxConflictError,
    InvalidProviderError,
    LaunchPolicyBlockedError,
    ProviderImageBuildError,
    ProviderImageMissingError,
    ProviderNotAllowedError,
    ProviderNotReadyError,
    SandboxLaunchError,
    SCCError,
)

# ═══════════════════════════════════════════════════════════════════════════════
# ProviderNotReadyError — actionable messages
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderNotReadyErrorMessages:
    """ProviderNotReadyError must always include actionable guidance."""

    def test_default_message_includes_doctor_command(self) -> None:
        """Default suggested_action includes 'scc doctor' command."""
        err = ProviderNotReadyError(provider_id="claude")
        assert "scc doctor" in err.suggested_action
        assert "--provider claude" in err.suggested_action

    def test_default_message_identifies_provider(self) -> None:
        """Default user_message names the provider."""
        err = ProviderNotReadyError(provider_id="codex")
        assert "codex" in err.user_message

    def test_custom_message_preserved(self) -> None:
        """Custom user_message is not overwritten by __post_init__."""
        err = ProviderNotReadyError(
            provider_id="claude",
            user_message="Custom auth failure message",
            suggested_action="Do this specific thing",
        )
        assert err.user_message == "Custom auth failure message"
        assert err.suggested_action == "Do this specific thing"

    def test_exit_code_is_prerequisite(self) -> None:
        """ProviderNotReadyError has exit code 3 (prerequisite)."""
        err = ProviderNotReadyError(provider_id="claude")
        assert err.exit_code == 3

    def test_non_interactive_auth_missing_gives_fix_command(self) -> None:
        """Non-interactive ProviderNotReadyError includes the exact CLI command."""
        err = ProviderNotReadyError(
            provider_id="codex",
            user_message="Codex auth cache is missing and this start is non-interactive.",
            suggested_action=(
                "Run 'scc start --provider codex' interactively once and "
                "complete the one-time browser sign-in."
            ),
        )
        assert "scc start --provider codex" in err.suggested_action
        assert "interactively" in err.suggested_action


# ═══════════════════════════════════════════════════════════════════════════════
# InvalidProviderError — lists valid options
# ═══════════════════════════════════════════════════════════════════════════════


class TestInvalidProviderErrorMessages:
    """InvalidProviderError must list valid provider names."""

    def test_lists_known_providers(self) -> None:
        """Error message lists all known providers."""
        err = InvalidProviderError(
            provider_id="typo",
            known_providers=("claude", "codex"),
        )
        assert "claude" in err.user_message
        assert "codex" in err.user_message
        assert "typo" in err.user_message

    def test_suggested_action_lists_valid_options(self) -> None:
        """Suggested action includes 'Use one of:' with provider names."""
        err = InvalidProviderError(
            provider_id="invalid",
            known_providers=("claude", "codex"),
        )
        assert "claude" in err.suggested_action
        assert "codex" in err.suggested_action

    def test_exit_code_is_usage(self) -> None:
        """InvalidProviderError has exit code 2 (usage)."""
        err = InvalidProviderError(
            provider_id="x",
            known_providers=("claude",),
        )
        assert err.exit_code == 2

    def test_empty_known_providers_still_works(self) -> None:
        """Even with empty known_providers, the error is constructible."""
        err = InvalidProviderError(provider_id="ghost", known_providers=())
        assert "ghost" in err.user_message


# ═══════════════════════════════════════════════════════════════════════════════
# ProviderImageMissingError — build command
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderImageMissingErrorMessages:
    """ProviderImageMissingError must include the build command."""

    def test_includes_docker_build_command(self) -> None:
        """Suggested action contains 'docker build'."""
        err = ProviderImageMissingError(
            provider_id="claude",
            image_ref="scc-agent-claude:latest",
        )
        assert "docker build" in err.suggested_action
        assert "scc-agent-claude" in err.suggested_action

    def test_image_ref_in_message(self) -> None:
        """User message includes the image ref."""
        err = ProviderImageMissingError(
            provider_id="codex",
            image_ref="scc-agent-codex:latest",
        )
        assert "scc-agent-codex:latest" in err.user_message

    def test_no_provider_fallback(self) -> None:
        """Without provider_id, suggested action is still present."""
        err = ProviderImageMissingError()
        assert err.suggested_action  # Not empty


# ═══════════════════════════════════════════════════════════════════════════════
# ProviderImageBuildError — build command
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderImageBuildErrorMessages:
    """ProviderImageBuildError provides the retry command."""

    def test_includes_build_command(self) -> None:
        """When build_command is set, suggested_action includes it."""
        err = ProviderImageBuildError(
            provider_id="claude",
            build_command="docker build -t scc-agent-claude images/scc-agent-claude/",
        )
        assert "docker build" in err.suggested_action

    def test_no_build_command_fallback(self) -> None:
        """Without build_command, suggested_action is still actionable."""
        err = ProviderImageBuildError(provider_id="claude")
        assert "try again" in err.suggested_action.lower() or "retry" in err.suggested_action.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# ProviderNotAllowedError — lists allowed providers
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderNotAllowedErrorMessages:
    """ProviderNotAllowedError names the allowed providers and suggests a fix."""

    def test_lists_allowed_providers(self) -> None:
        """Error message includes allowed providers."""
        err = ProviderNotAllowedError(
            provider_id="codex",
            allowed_providers=("claude",),
        )
        assert "claude" in err.user_message
        assert "codex" in err.user_message

    def test_suggested_action_mentions_admin(self) -> None:
        """Suggested action points user to team admin."""
        err = ProviderNotAllowedError(
            provider_id="codex",
            allowed_providers=("claude",),
        )
        assert "admin" in err.suggested_action.lower() or "allowed_providers" in err.suggested_action


# ═══════════════════════════════════════════════════════════════════════════════
# SandboxLaunchError — Docker stderr surfacing
# ═══════════════════════════════════════════════════════════════════════════════


class TestSandboxLaunchErrorMessages:
    """SandboxLaunchError must surface Docker stderr so the user can diagnose."""

    def test_stderr_in_suggested_action(self) -> None:
        """Docker stderr is included in suggested_action."""
        err = SandboxLaunchError(
            stderr="no space left on device",
        )
        assert "no space left on device" in err.suggested_action

    def test_empty_stderr_clean_message(self) -> None:
        """When stderr is empty/whitespace, no Docker error line appended."""
        err = SandboxLaunchError(stderr="  ")
        assert "Docker error:" not in err.suggested_action

    def test_no_stderr_clean_message(self) -> None:
        """When stderr is None, suggested_action is still actionable."""
        err = SandboxLaunchError()
        assert "Docker Desktop" in err.suggested_action or "Docker" in err.suggested_action


# ═══════════════════════════════════════════════════════════════════════════════
# ExistingSandboxConflictError — actionable commands
# ═══════════════════════════════════════════════════════════════════════════════


class TestExistingSandboxConflictErrorMessages:
    """ExistingSandboxConflictError must give specific commands."""

    def test_includes_scc_fresh_and_stop(self) -> None:
        """Suggested action includes --fresh and scc stop."""
        err = ExistingSandboxConflictError(container_name="scc-my-project-claude")
        assert "--fresh" in err.suggested_action
        assert "scc stop" in err.suggested_action

    def test_container_name_in_stop_command(self) -> None:
        """Container name appears in the stop command."""
        err = ExistingSandboxConflictError(container_name="scc-my-project-claude")
        assert "scc-my-project-claude" in err.suggested_action

    def test_no_container_name_still_actionable(self) -> None:
        """Without container name, suggestion is still meaningful."""
        err = ExistingSandboxConflictError()
        assert "--fresh" in err.suggested_action


# ═══════════════════════════════════════════════════════════════════════════════
# LaunchPolicyBlockedError — policy context
# ═══════════════════════════════════════════════════════════════════════════════


class TestLaunchPolicyBlockedErrorMessages:
    """LaunchPolicyBlockedError explains the policy conflict."""

    def test_includes_provider_and_policy(self) -> None:
        """Message names the provider and network policy."""
        err = LaunchPolicyBlockedError(
            provider_id="claude",
            network_policy="enforced",
            required_destination_sets=("claude-api", "github"),
        )
        assert "claude" in err.user_message
        assert "enforced" in err.user_message
        assert "claude-api" in err.user_message

    def test_suggested_action_is_actionable(self) -> None:
        """Suggested action tells user what to do."""
        err = LaunchPolicyBlockedError(
            provider_id="codex",
            network_policy="enforced",
        )
        assert "policy" in err.suggested_action.lower() or "provider" in err.suggested_action.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# DockerNotFoundError / DockerDaemonNotRunningError — SCC context
# ═══════════════════════════════════════════════════════════════════════════════


class TestDockerPrerequisiteErrors:
    """Docker errors include SCC-level context, not raw Docker output."""

    def test_docker_not_found_has_install_link(self) -> None:
        """DockerNotFoundError suggested_action includes install URL."""
        err = DockerNotFoundError()
        assert "docker.com" in err.suggested_action or "docker" in err.suggested_action.lower()

    def test_docker_daemon_not_running_gives_next_step(self) -> None:
        """DockerDaemonNotRunningError tells user to start Docker."""
        err = DockerDaemonNotRunningError()
        assert "Start" in err.suggested_action or "start" in err.suggested_action

    def test_docker_not_found_exit_code(self) -> None:
        """DockerNotFoundError has exit code 3 (prerequisite)."""
        err = DockerNotFoundError()
        assert err.exit_code == 3


# ═══════════════════════════════════════════════════════════════════════════════
# ensure_provider_auth — wrapping raw exceptions
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnsureProviderAuthErrorWrapping:
    """ensure_provider_auth wraps raw exceptions with SCC context."""

    def test_os_error_wrapped_with_guidance(self) -> None:
        """OSError from bootstrap_auth is wrapped in ProviderNotReadyError."""
        from scc_cli.commands.launch.auth_bootstrap import ensure_provider_auth

        plan = MagicMock()
        plan.resume = False
        mock_provider = MagicMock()
        mock_provider.auth_check.return_value = MagicMock(status="missing")
        mock_provider.capability_profile.return_value = MagicMock(provider_id="claude")
        mock_provider.bootstrap_auth.side_effect = OSError("Permission denied")

        deps = MagicMock()
        deps.agent_provider = mock_provider
        show = MagicMock()

        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_provider_auth(
                plan,
                dependencies=deps,
                non_interactive=False,
                show_notice=show,
            )
        err = exc_info.value
        assert "Permission denied" in err.user_message
        assert "scc start --provider claude" in err.suggested_action
        assert "scc doctor" in err.suggested_action

    def test_provider_not_ready_passes_through(self) -> None:
        """ProviderNotReadyError from bootstrap_auth passes through unchanged."""
        from scc_cli.commands.launch.auth_bootstrap import ensure_provider_auth

        plan = MagicMock()
        plan.resume = False
        original = ProviderNotReadyError(
            provider_id="codex",
            user_message="Original message",
            suggested_action="Original action",
        )
        mock_provider = MagicMock()
        mock_provider.auth_check.return_value = MagicMock(status="missing")
        mock_provider.capability_profile.return_value = MagicMock(provider_id="codex")
        mock_provider.bootstrap_auth.side_effect = original

        deps = MagicMock()
        deps.agent_provider = mock_provider
        show = MagicMock()

        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_provider_auth(
                plan,
                dependencies=deps,
                non_interactive=False,
                show_notice=show,
            )
        # Should be the exact same object, not double-wrapped
        assert exc_info.value is original
        assert exc_info.value.user_message == "Original message"

    def test_non_interactive_missing_auth_gives_fix(self) -> None:
        """Non-interactive mode with missing auth raises with fix command."""
        from scc_cli.commands.launch.auth_bootstrap import ensure_provider_auth

        plan = MagicMock()
        plan.resume = False
        mock_provider = MagicMock()
        mock_provider.auth_check.return_value = MagicMock(status="missing")
        mock_provider.capability_profile.return_value = MagicMock(provider_id="codex")

        deps = MagicMock()
        deps.agent_provider = mock_provider
        show = MagicMock()

        with pytest.raises(ProviderNotReadyError) as exc_info:
            ensure_provider_auth(
                plan,
                dependencies=deps,
                non_interactive=True,
                show_notice=show,
            )
        err = exc_info.value
        assert "non-interactive" in err.user_message
        assert "scc start --provider codex" in err.suggested_action

    def test_resume_skips_auth_check(self) -> None:
        """Resume mode skips auth bootstrap entirely."""
        from scc_cli.commands.launch.auth_bootstrap import ensure_provider_auth

        plan = MagicMock()
        plan.resume = True
        mock_provider = MagicMock()

        deps = MagicMock()
        deps.agent_provider = mock_provider

        # Should not raise, no bootstrap called
        ensure_provider_auth(
            plan,
            dependencies=deps,
            non_interactive=False,
            show_notice=MagicMock(),
        )
        mock_provider.bootstrap_auth.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# choose_start_provider — non-interactive error messages
# ═══════════════════════════════════════════════════════════════════════════════


class TestChooseStartProviderErrorMessages:
    """choose_start_provider raises actionable errors in non-interactive mode."""

    def test_multiple_providers_no_selection_gives_fix(self) -> None:
        """When multiple providers available but none selected, error is actionable."""
        from scc_cli.commands.launch.provider_choice import choose_start_provider

        with pytest.raises(ProviderNotReadyError) as exc_info:
            choose_start_provider(
                cli_flag=None,
                resume_provider=None,
                workspace_last_used=None,
                config_provider=None,
                connected_provider_ids=("claude", "codex"),
                allowed_providers=(),
                non_interactive=True,
                prompt_choice=None,
            )
        err = exc_info.value
        assert "--provider" in err.suggested_action
        assert "scc provider set" in err.suggested_action

    def test_no_prompt_choice_gives_terminal_guidance(self) -> None:
        """When prompt_choice is None, error tells user to use interactive terminal."""
        from scc_cli.commands.launch.provider_choice import choose_start_provider

        with pytest.raises(ProviderNotReadyError) as exc_info:
            choose_start_provider(
                cli_flag=None,
                resume_provider=None,
                workspace_last_used=None,
                config_provider=None,
                connected_provider_ids=("claude", "codex"),
                allowed_providers=(),
                non_interactive=False,
                prompt_choice=None,
            )
        err = exc_info.value
        assert "interactive" in err.suggested_action.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Doctor check errors — Docker errors wrapped with SCC context
# ═══════════════════════════════════════════════════════════════════════════════


class TestDoctorCheckErrorWrapping:
    """Doctor checks wrap Docker errors with SCC context."""

    def test_docker_check_failure_has_fix_hint(self) -> None:
        """check_docker returns fix_hint with install instructions."""
        from unittest.mock import patch as mock_patch

        from scc_cli.doctor.checks.environment import check_docker

        # docker_module is imported inside the function as `from ... import docker`
        # which resolves to scc_cli.docker — patch that module's function
        with mock_patch("scc_cli.docker.get_docker_version", return_value=None):
            result = check_docker()

        assert not result.passed
        assert result.fix_hint is not None
        assert "docker" in result.fix_hint.lower() or "Docker" in result.fix_hint

    def test_docker_daemon_check_failure_has_fix_hint(self) -> None:
        """check_docker_running returns fix_hint when daemon unreachable."""
        from unittest.mock import patch as mock_patch

        from scc_cli.doctor.checks.environment import check_docker_running

        with mock_patch(
            "scc_cli.doctor.checks.environment.subprocess.run",
            side_effect=FileNotFoundError("docker not found"),
        ):
            result = check_docker_running()

        assert not result.passed
        assert result.fix_hint is not None

    def test_provider_auth_check_failure_has_fix_hint(self) -> None:
        """check_provider_auth returns fix_hint when auth check fails."""
        from unittest.mock import patch as mock_patch

        from scc_cli.doctor.checks.environment import check_provider_auth

        mock_adapters = MagicMock()
        mock_provider = MagicMock()
        mock_provider.auth_check.return_value = AuthReadiness(
            status="missing",
            mechanism="oauth_file",
            guidance="Run 'scc start --provider claude' to sign in",
        )
        mock_adapters.agent_provider = mock_provider

        with mock_patch(
            "scc_cli.bootstrap.get_default_adapters",
            return_value=mock_adapters,
        ):
            result = check_provider_auth(provider_id="claude")

        assert not result.passed
        assert result.fix_hint is not None
        assert "scc start" in result.fix_hint

    def test_provider_image_check_failure_has_build_command(self) -> None:
        """check_provider_image returns fix_commands with docker build."""
        from unittest.mock import patch as mock_patch

        from scc_cli.doctor.checks.environment import check_provider_image

        mock_spec = MagicMock()
        mock_spec.image_ref = "scc-agent-claude:latest"

        with (
            mock_patch(
                "scc_cli.core.provider_registry.get_runtime_spec",
                return_value=mock_spec,
            ),
            mock_patch(
                "scc_cli.doctor.checks.environment.subprocess.run",
            ) as mock_run,
        ):
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_run.return_value = mock_result
            result = check_provider_image(provider_id="claude")

        assert not result.passed
        assert result.fix_commands is not None
        assert any("docker build" in cmd for cmd in result.fix_commands)


# ═══════════════════════════════════════════════════════════════════════════════
# Error hierarchy sanity
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorHierarchySanity:
    """Error hierarchy is consistent — all SCC errors have user_message and suggested_action."""

    @pytest.mark.parametrize(
        "error_cls,kwargs",
        [
            (ProviderNotReadyError, {"provider_id": "claude"}),
            (InvalidProviderError, {"provider_id": "bad", "known_providers": ("claude", "codex")}),
            (ProviderImageMissingError, {"provider_id": "claude", "image_ref": "img:latest"}),
            (ProviderNotAllowedError, {"provider_id": "codex", "allowed_providers": ("claude",)}),
            (SandboxLaunchError, {"stderr": "test error"}),
            (DockerNotFoundError, {}),
            (DockerDaemonNotRunningError, {}),
            (ExistingSandboxConflictError, {"container_name": "scc-test"}),
            (LaunchPolicyBlockedError, {"provider_id": "claude", "network_policy": "enforced"}),
        ],
    )
    def test_every_error_has_user_message_and_action(
        self, error_cls: type[SCCError], kwargs: dict
    ) -> None:
        """Every error class produces a non-empty user_message and suggested_action."""
        err = error_cls(**kwargs)
        assert err.user_message, f"{error_cls.__name__} has empty user_message"
        assert err.suggested_action, f"{error_cls.__name__} has empty suggested_action"

    @pytest.mark.parametrize(
        "error_cls,kwargs,expected_exit_code",
        [
            (ProviderNotReadyError, {"provider_id": "claude"}, 3),
            (InvalidProviderError, {"provider_id": "x", "known_providers": ()}, 2),
            (SandboxLaunchError, {}, 5),
            (DockerNotFoundError, {}, 3),
            (ConfigError, {}, 2),
        ],
    )
    def test_exit_codes_match_documented_scheme(
        self,
        error_cls: type[SCCError],
        kwargs: dict,
        expected_exit_code: int,
    ) -> None:
        """Exit codes match the documented scheme (2=usage, 3=prereq, 4=tool, 5=internal)."""
        err = error_cls(**kwargs)
        assert err.exit_code == expected_exit_code



