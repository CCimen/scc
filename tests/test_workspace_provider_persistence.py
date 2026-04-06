"""Tests for workspace provider preference persistence edge cases.

Verifies:
- set_workspace_last_used_provider is called ONLY after finalize_launch succeeds
- KEEP_EXISTING conflict path writes workspace preference
- Cancelled / failed launches do NOT write workspace preference
- _resolve_prompt_default returns correct preselection for ask+last-used
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.application.start_session import StartSessionPlan
from scc_cli.commands.launch.conflict_resolution import (
    LaunchConflictDecision,
    LaunchConflictResolution,
)
from scc_cli.commands.launch.preflight import (
    AuthStatus,
    ImageStatus,
    LaunchReadiness,
    ProviderResolutionSource,
)
from scc_cli.commands.launch.provider_choice import _resolve_prompt_default
from scc_cli.core.contracts import AuthReadiness, ProviderCapabilityProfile
from scc_cli.core.errors import SandboxLaunchError
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.models import MountSpec, SandboxSpec

# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────


def _build_plan(tmp_path: Path, *, provider_id: str = "codex") -> StartSessionPlan:
    resolver = ResolverResult(
        workspace_root=tmp_path,
        entry_dir=tmp_path,
        mount_root=tmp_path,
        container_workdir=str(tmp_path),
        is_auto_detected=False,
        is_suspicious=False,
        reason="explicit",
    )
    sandbox_spec = SandboxSpec(
        image=f"scc-agent-{provider_id}:latest",
        workspace_mount=MountSpec(source=tmp_path, target=tmp_path),
        workdir=tmp_path,
        provider_id=provider_id,
    )
    return StartSessionPlan(
        resolver_result=resolver,
        workspace_path=tmp_path,
        team=None,
        session_name="demo",
        resume=False,
        fresh=False,
        current_branch="main",
        effective_config=None,
        sync_result=None,
        sync_error_message=None,
        agent_settings=None,
        sandbox_spec=sandbox_spec,
        agent_launch_spec=None,
    )


def _build_dependencies(*, provider_id: str = "codex") -> MagicMock:
    provider = MagicMock()
    provider.capability_profile.return_value = ProviderCapabilityProfile(
        provider_id=provider_id,
        display_name=provider_id.capitalize(),
        required_destination_set=None,
        supports_resume=False,
        supports_skills=True,
        supports_native_integrations=True,
    )
    provider.auth_check.return_value = AuthReadiness(
        status="present", mechanism="auth_json_file", guidance=None
    )
    deps = MagicMock()
    deps.agent_provider = provider
    return deps


def _build_adapters() -> MagicMock:
    adapters = MagicMock()
    adapters.sandbox_runtime.ensure_available.return_value = None
    adapters.filesystem = MagicMock()
    adapters.personal_profile_service.workspace_has_overrides.return_value = False
    return adapters


def _invoke_start(tmp_path: Path, *, provider: str = "codex") -> None:
    from scc_cli.commands.launch.flow import start

    start(
        workspace=str(tmp_path),
        team=None,
        session_name="demo",
        resume=False,
        select=False,
        worktree_name=None,
        fresh=False,
        install_deps=False,
        offline=False,
        standalone=True,
        dry_run=False,
        json_output=False,
        pretty=False,
        non_interactive=False,
        debug=False,
        allow_suspicious_workspace=False,
        provider=provider,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Shared decorator stacks
# ──────────────────────────────────────────────────────────────────────────────

_FLOW_BASE_PATCHES = [
    "scc_cli.commands.launch.flow.setup.is_setup_needed",
    "scc_cli.commands.launch.flow.config.load_user_config",
    "scc_cli.commands.launch.flow.get_default_adapters",
    "scc_cli.commands.launch.flow.sessions.get_session_service",
    "scc_cli.commands.launch.flow.validate_and_resolve_workspace",
    "scc_cli.commands.launch.flow.prepare_workspace",
    "scc_cli.commands.launch.flow.resolve_workspace_team",
    "scc_cli.commands.launch.flow.resolve_launch_provider",
    "scc_cli.commands.launch.flow.prepare_live_start_plan",
    "scc_cli.commands.launch.flow.build_sync_output_view_model",
    "scc_cli.commands.launch.flow.render_launch_output",
    "scc_cli.commands.launch.flow._apply_personal_profile",
    "scc_cli.commands.launch.flow.warn_if_non_worktree",
    "scc_cli.commands.launch.flow.resolve_launch_conflict",
    "scc_cli.commands.launch.flow._record_session_and_context",
    "scc_cli.commands.launch.flow.set_workspace_last_used_provider",
    "scc_cli.commands.launch.flow.collect_launch_readiness",
    "scc_cli.commands.launch.flow.ensure_launch_ready",
    "scc_cli.commands.launch.flow.show_auth_bootstrap_panel",
    "scc_cli.commands.launch.flow.show_launch_panel",
    "scc_cli.commands.launch.flow.finalize_launch",
]


def _apply_flow_patches(
    tmp_path: Path,
    *,
    provider_id: str = "codex",
    conflict_decision: LaunchConflictDecision = LaunchConflictDecision.PROCEED,
    finalize_side_effect: Exception | None = None,
) -> dict[str, MagicMock]:
    """Create a dict of mock names → MagicMock with sensible defaults."""
    plan = _build_plan(tmp_path, provider_id=provider_id)
    deps = _build_dependencies(provider_id=provider_id)

    mocks: dict[str, MagicMock] = {}
    for patch_path in _FLOW_BASE_PATCHES:
        short_name = patch_path.rsplit(".", 1)[-1]
        mocks[short_name] = MagicMock()

    # Wire up return values
    mocks["is_setup_needed"].return_value = False
    mocks["load_user_config"].return_value = {}
    mocks["get_default_adapters"].return_value = _build_adapters()
    mocks["validate_and_resolve_workspace"].return_value = tmp_path
    mocks["prepare_workspace"].return_value = tmp_path
    mocks["resolve_workspace_team"].return_value = None
    mocks["resolve_launch_provider"].return_value = (provider_id, "explicit")
    mocks["collect_launch_readiness"].return_value = LaunchReadiness(
        provider_id=provider_id,
        resolution_source=ProviderResolutionSource.EXPLICIT,
        image_status=ImageStatus.AVAILABLE,
        auth_status=AuthStatus.PRESENT,
        requires_image_bootstrap=False,
        requires_auth_bootstrap=False,
        launch_ready=True,
    )
    mocks["prepare_live_start_plan"].return_value = (deps, plan)
    mocks["_apply_personal_profile"].return_value = (None, False)
    mocks["resolve_launch_conflict"].return_value = LaunchConflictResolution(
        decision=conflict_decision,
        plan=plan,
    )

    if finalize_side_effect is not None:
        mocks["finalize_launch"].side_effect = finalize_side_effect

    return mocks


# ──────────────────────────────────────────────────────────────────────────────
# Tests: workspace preference after successful launch
# ──────────────────────────────────────────────────────────────────────────────


class TestSuccessfulLaunchWritesPreference:
    """set_workspace_last_used_provider is called after finalize_launch succeeds."""

    def test_successful_launch_writes_workspace_preference(self, tmp_path: Path) -> None:
        mocks = _apply_flow_patches(tmp_path, provider_id="codex")

        with _patch_all(mocks):
            _invoke_start(tmp_path, provider="codex")

        mocks["set_workspace_last_used_provider"].assert_called_once_with(tmp_path, "codex")

    def test_successful_launch_calls_preference_after_finalize(self, tmp_path: Path) -> None:
        """Verify ordering: finalize_launch is called before set_workspace_last_used_provider."""
        call_order: list[str] = []
        mocks = _apply_flow_patches(tmp_path, provider_id="codex")
        mocks["finalize_launch"].side_effect = lambda *a, **kw: call_order.append("finalize")
        mocks["set_workspace_last_used_provider"].side_effect = lambda *a, **kw: call_order.append(
            "set_pref"
        )

        with _patch_all(mocks):
            _invoke_start(tmp_path, provider="codex")

        assert call_order == ["finalize", "set_pref"]


# ──────────────────────────────────────────────────────────────────────────────
# Tests: failed launch does NOT write preference
# ──────────────────────────────────────────────────────────────────────────────


class TestFailedLaunchDoesNotWritePreference:
    """If finalize_launch raises, workspace preference must NOT be persisted."""

    def test_finalize_launch_raises_skips_preference_write(self, tmp_path: Path) -> None:
        mocks = _apply_flow_patches(
            tmp_path,
            provider_id="codex",
            finalize_side_effect=SandboxLaunchError(
                user_message="Docker start failed",
                suggested_action="Check docker daemon",
            ),
        )

        with _patch_all(mocks), pytest.raises(SandboxLaunchError):
            _invoke_start(tmp_path, provider="codex")

        mocks["set_workspace_last_used_provider"].assert_not_called()

    def test_finalize_launch_raises_runtime_error_skips_preference(self, tmp_path: Path) -> None:
        mocks = _apply_flow_patches(
            tmp_path,
            provider_id="codex",
            finalize_side_effect=RuntimeError("unexpected container failure"),
        )

        with _patch_all(mocks), pytest.raises(RuntimeError):
            _invoke_start(tmp_path, provider="codex")

        mocks["set_workspace_last_used_provider"].assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# Tests: cancelled launch does NOT write preference
# ──────────────────────────────────────────────────────────────────────────────


class TestCancelledLaunchDoesNotWritePreference:
    """If the user cancels, workspace preference must NOT be persisted."""

    def test_cancelled_conflict_does_not_write_preference(self, tmp_path: Path) -> None:
        mocks = _apply_flow_patches(
            tmp_path,
            provider_id="codex",
            conflict_decision=LaunchConflictDecision.CANCELLED,
        )

        import typer

        with _patch_all(mocks), pytest.raises(typer.Exit):
            _invoke_start(tmp_path, provider="codex")

        mocks["set_workspace_last_used_provider"].assert_not_called()
        mocks["finalize_launch"].assert_not_called()


# ──────────────────────────────────────────────────────────────────────────────
# Tests: KEEP_EXISTING writes preference
# ──────────────────────────────────────────────────────────────────────────────


class TestKeepExistingWritesPreference:
    """KEEP_EXISTING conflict resolution writes workspace preference (without launching)."""

    def test_keep_existing_writes_preference_via_flow_start(self, tmp_path: Path) -> None:
        mocks = _apply_flow_patches(
            tmp_path,
            provider_id="codex",
            conflict_decision=LaunchConflictDecision.KEEP_EXISTING,
        )

        import typer

        with _patch_all(mocks), pytest.raises(typer.Exit) as exc_info:
            _invoke_start(tmp_path, provider="codex")

        assert exc_info.value.exit_code == 0
        mocks["set_workspace_last_used_provider"].assert_called_once_with(tmp_path, "codex")
        # finalize_launch should NOT be called for KEEP_EXISTING
        mocks["finalize_launch"].assert_not_called()

    def test_keep_existing_does_not_call_finalize_launch(self, tmp_path: Path) -> None:
        mocks = _apply_flow_patches(
            tmp_path,
            provider_id="claude",
            conflict_decision=LaunchConflictDecision.KEEP_EXISTING,
        )

        import typer

        with _patch_all(mocks), pytest.raises(typer.Exit):
            _invoke_start(tmp_path, provider="claude")

        mocks["finalize_launch"].assert_not_called()
        mocks["set_workspace_last_used_provider"].assert_called_once_with(tmp_path, "claude")


# ──────────────────────────────────────────────────────────────────────────────
# Tests: _resolve_prompt_default preselection logic
# ──────────────────────────────────────────────────────────────────────────────


class TestResolvePromptDefault:
    """_resolve_prompt_default returns correct preselection for ask+last-used scenarios."""

    def test_workspace_last_used_preselected_when_connected(self) -> None:
        """ask + workspace_last_used='codex' + codex connected → codex preselected."""
        result = _resolve_prompt_default(
            candidates=("claude", "codex"),
            connected_allowed=("claude", "codex"),
            workspace_last_used="codex",
            config_provider="ask",
        )
        assert result == "codex"

    def test_workspace_last_used_not_preselected_when_disconnected(self) -> None:
        """ask + workspace_last_used='codex' + codex NOT connected → no preselection."""
        result = _resolve_prompt_default(
            candidates=("claude", "codex"),
            connected_allowed=("claude",),
            workspace_last_used="codex",
            config_provider="ask",
        )
        assert result is None

    def test_no_workspace_last_used_no_preselection(self) -> None:
        """ask + no workspace_last_used → no preselection."""
        result = _resolve_prompt_default(
            candidates=("claude", "codex"),
            connected_allowed=("claude", "codex"),
            workspace_last_used=None,
            config_provider="ask",
        )
        assert result is None

    def test_config_provider_preselected_when_no_workspace_last_used(self) -> None:
        """No workspace_last_used but config_provider set and connected → config preselected."""
        result = _resolve_prompt_default(
            candidates=("claude", "codex"),
            connected_allowed=("claude", "codex"),
            workspace_last_used=None,
            config_provider="claude",
        )
        assert result == "claude"

    def test_workspace_last_used_beats_config_provider(self) -> None:
        """workspace_last_used takes precedence over config_provider."""
        result = _resolve_prompt_default(
            candidates=("claude", "codex"),
            connected_allowed=("claude", "codex"),
            workspace_last_used="codex",
            config_provider="claude",
        )
        assert result == "codex"

    def test_workspace_last_used_not_in_candidates_returns_none(self) -> None:
        """workspace_last_used not in candidates → falls through."""
        result = _resolve_prompt_default(
            candidates=("claude",),
            connected_allowed=("claude",),
            workspace_last_used="codex",
            config_provider=None,
        )
        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# Tests: ask preference triggers prompt with correct preselection
# ──────────────────────────────────────────────────────────────────────────────


class TestAskPreferencePromptPreselection:
    """When global preference is 'ask', the chooser prompt receives the right default."""

    def test_ask_with_workspace_last_used_passes_preselection_to_prompt(self) -> None:
        """ask + workspace_last_used='codex' → prompt receives default='codex'."""
        from scc_cli.commands.launch.provider_choice import choose_start_provider

        prompt = MagicMock(return_value="codex")

        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            config_provider="ask",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=prompt,
        )

        assert result == "codex"
        prompt.assert_called_once()
        # Third arg to prompt_choice is the default — should be "codex"
        _, _, default_arg = prompt.call_args[0]
        assert default_arg == "codex"

    def test_ask_with_disconnected_workspace_last_used_auto_selects_single(self) -> None:
        """ask + workspace_last_used='codex' but only claude connected → auto-selects claude.

        When only one provider is connected, the auto-single logic kicks in
        before the prompt is reached — no prompt needed.
        """
        from scc_cli.commands.launch.provider_choice import choose_start_provider

        prompt = MagicMock(return_value="claude")

        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="codex",
            config_provider="ask",
            connected_provider_ids=("claude",),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=prompt,
        )

        assert result == "claude"
        # Single connected provider auto-selects without prompting
        prompt.assert_not_called()

    def test_ask_with_disconnected_workspace_last_used_prompts_with_none_default(self) -> None:
        """ask + workspace_last_used not connected + multiple connected → default=None.

        When workspace_last_used references a provider that isn't connected,
        and multiple other providers are connected, the prompt default is None.
        """
        from scc_cli.commands.launch.provider_choice import choose_start_provider

        prompt = MagicMock(return_value="claude")

        # workspace_last_used="gemini" but gemini isn't in connected_provider_ids
        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used="gemini",
            config_provider="ask",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=prompt,
        )

        assert result == "claude"
        prompt.assert_called_once()
        _, _, default_arg = prompt.call_args[0]
        assert default_arg is None

    def test_ask_without_workspace_last_used_has_no_preselection(self) -> None:
        """ask + no workspace_last_used → default=None."""
        from scc_cli.commands.launch.provider_choice import choose_start_provider

        prompt = MagicMock(return_value="claude")

        result = choose_start_provider(
            cli_flag=None,
            resume_provider=None,
            workspace_last_used=None,
            config_provider="ask",
            connected_provider_ids=("claude", "codex"),
            allowed_providers=(),
            non_interactive=False,
            prompt_choice=prompt,
        )

        assert result == "claude"
        prompt.assert_called_once()
        _, _, default_arg = prompt.call_args[0]
        assert default_arg is None


# ──────────────────────────────────────────────────────────────────────────────
# Helper: apply all flow patches as a context manager
# ──────────────────────────────────────────────────────────────────────────────


class _PatchAll:
    """Context manager that applies all flow base patches from a mocks dict."""

    def __init__(self, mocks: dict[str, MagicMock]) -> None:
        self._mocks = mocks
        self._patchers: list[patch] = []  # type: ignore[type-arg]

    def __enter__(self) -> dict[str, MagicMock]:
        for patch_path in _FLOW_BASE_PATCHES:
            short_name = patch_path.rsplit(".", 1)[-1]
            p = patch(patch_path, self._mocks[short_name])
            p.start()
            self._patchers.append(p)
        return self._mocks

    def __exit__(self, *args: object) -> None:
        for p in reversed(self._patchers):
            p.stop()


def _patch_all(mocks: dict[str, MagicMock]) -> _PatchAll:
    return _PatchAll(mocks)
