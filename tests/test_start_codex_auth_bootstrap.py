"""Tests for Codex auth bootstrap integration through the start flow.

Verifies that flow.py delegates to the shared preflight readiness path
(collect_launch_readiness + ensure_launch_ready) which handles image
and auth bootstrap for all providers.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.commands.launch.conflict_resolution import (
    LaunchConflictDecision,
    LaunchConflictResolution,
)
from scc_cli.commands.launch.flow import start
from scc_cli.commands.launch.preflight import (
    AuthStatus,
    ImageStatus,
    LaunchReadiness,
    ProviderResolutionSource,
)
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.models import MountSpec, SandboxSpec


def _build_plan(tmp_path: Path) -> StartSessionPlan:
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
        image="scc-agent-codex:latest",
        workspace_mount=MountSpec(source=tmp_path, target=tmp_path),
        workdir=tmp_path,
        provider_id="codex",
    )
    return StartSessionPlan(
        resolver_result=resolver,
        workspace_path=tmp_path,
        team=None,
        session_name="demo",
        resume=False,
        fresh=False,
        current_branch="feature/demo",
        effective_config=None,
        sync_result=None,
        sync_error_message=None,
        agent_settings=None,
        sandbox_spec=sandbox_spec,
        agent_launch_spec=None,
    )


def _build_dependencies() -> StartSessionDependencies:
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=MagicMock(),
        agent_runner=MagicMock(),
        agent_provider=MagicMock(),
        sandbox_runtime=MagicMock(),
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
    )


def _build_adapters() -> MagicMock:
    adapters = MagicMock()
    adapters.sandbox_runtime.ensure_available.return_value = None
    adapters.filesystem = MagicMock()
    adapters.personal_profile_service.workspace_has_overrides.return_value = False
    return adapters


def _readiness_auth_missing() -> LaunchReadiness:
    """Build a readiness snapshot indicating missing auth."""
    return LaunchReadiness(
        provider_id="codex",
        resolution_source=ProviderResolutionSource.EXPLICIT,
        image_status=ImageStatus.AVAILABLE,
        auth_status=AuthStatus.MISSING,
        requires_image_bootstrap=False,
        requires_auth_bootstrap=True,
        launch_ready=False,
    )


def _readiness_all_good() -> LaunchReadiness:
    """Build a readiness snapshot indicating everything is ready."""
    return LaunchReadiness(
        provider_id="codex",
        resolution_source=ProviderResolutionSource.EXPLICIT,
        image_status=ImageStatus.AVAILABLE,
        auth_status=AuthStatus.PRESENT,
        requires_image_bootstrap=False,
        requires_auth_bootstrap=False,
        launch_ready=True,
    )


def _invoke_start(tmp_path: Path, *, non_interactive: bool) -> None:
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
        non_interactive=non_interactive,
        debug=False,
        allow_suspicious_workspace=False,
        provider="codex",
    )


@patch("scc_cli.commands.launch.flow.finalize_launch")
@patch("scc_cli.commands.launch.flow.show_launch_panel")
@patch("scc_cli.commands.launch.flow.show_auth_bootstrap_panel")
@patch("scc_cli.commands.launch.flow.ensure_launch_ready")
@patch("scc_cli.commands.launch.flow.collect_launch_readiness")
@patch("scc_cli.commands.launch.flow.set_workspace_last_used_provider")
@patch("scc_cli.commands.launch.flow._record_session_and_context")
@patch("scc_cli.commands.launch.flow.resolve_launch_conflict")
@patch("scc_cli.commands.launch.flow.warn_if_non_worktree")
@patch("scc_cli.commands.launch.flow._apply_personal_profile", return_value=(None, False))
@patch("scc_cli.commands.launch.flow.render_launch_output")
@patch("scc_cli.commands.launch.flow.build_sync_output_view_model")
@patch("scc_cli.commands.launch.flow.prepare_live_start_plan")
@patch("scc_cli.commands.launch.flow.resolve_launch_provider", return_value=("codex", "explicit"))
@patch("scc_cli.commands.launch.flow.resolve_workspace_team", return_value=None)
@patch("scc_cli.commands.launch.flow.prepare_workspace")
@patch("scc_cli.commands.launch.flow.validate_and_resolve_workspace")
@patch("scc_cli.commands.launch.flow.sessions.get_session_service")
@patch("scc_cli.commands.launch.flow.get_default_adapters")
@patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={})
@patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False)
def test_start_calls_ensure_launch_ready_when_auth_missing(
    mock_setup: MagicMock,
    mock_cfg: MagicMock,
    mock_get_adapters: MagicMock,
    mock_session_service: MagicMock,
    mock_validate_workspace: MagicMock,
    mock_prepare_workspace: MagicMock,
    mock_resolve_team: MagicMock,
    mock_resolve_provider: MagicMock,
    mock_prepare_live_start_plan: MagicMock,
    mock_build_output: MagicMock,
    mock_render_output: MagicMock,
    mock_apply_profile: MagicMock,
    mock_warn_non_worktree: MagicMock,
    mock_resolve_conflict: MagicMock,
    mock_record_session: MagicMock,
    mock_set_workspace_provider: MagicMock,
    mock_collect_readiness: MagicMock,
    mock_ensure_ready: MagicMock,
    mock_show_auth_bootstrap: MagicMock,
    mock_show_launch: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """When auth is missing, flow.py calls ensure_launch_ready which handles
    image pull + auth bootstrap through the shared preflight path."""
    plan = _build_plan(tmp_path)
    dependencies = _build_dependencies()
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (dependencies, plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.PROCEED,
        plan=plan,
    )
    mock_collect_readiness.return_value = _readiness_auth_missing()

    _invoke_start(tmp_path, non_interactive=False)

    mock_collect_readiness.assert_called_once()
    mock_ensure_ready.assert_called_once()
    # Verify the readiness object was passed through
    call_args = mock_ensure_ready.call_args
    assert call_args[0][0].requires_auth_bootstrap is True
    mock_show_launch.assert_called_once()
    mock_finalize_launch.assert_called_once()
    mock_set_workspace_provider.assert_called_once_with(tmp_path, "codex")


@patch("scc_cli.commands.launch.flow.finalize_launch")
@patch("scc_cli.commands.launch.flow.show_launch_panel")
@patch("scc_cli.commands.launch.flow.show_auth_bootstrap_panel")
@patch("scc_cli.commands.launch.flow.ensure_launch_ready")
@patch("scc_cli.commands.launch.flow.collect_launch_readiness")
@patch("scc_cli.commands.launch.flow.set_workspace_last_used_provider")
@patch("scc_cli.commands.launch.flow._record_session_and_context")
@patch("scc_cli.commands.launch.flow.resolve_launch_conflict")
@patch("scc_cli.commands.launch.flow.warn_if_non_worktree")
@patch("scc_cli.commands.launch.flow._apply_personal_profile", return_value=(None, False))
@patch("scc_cli.commands.launch.flow.render_launch_output")
@patch("scc_cli.commands.launch.flow.build_sync_output_view_model")
@patch("scc_cli.commands.launch.flow.prepare_live_start_plan")
@patch("scc_cli.commands.launch.flow.resolve_launch_provider", return_value=("codex", "explicit"))
@patch("scc_cli.commands.launch.flow.resolve_workspace_team", return_value=None)
@patch("scc_cli.commands.launch.flow.prepare_workspace")
@patch("scc_cli.commands.launch.flow.validate_and_resolve_workspace")
@patch("scc_cli.commands.launch.flow.sessions.get_session_service")
@patch("scc_cli.commands.launch.flow.get_default_adapters")
@patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={})
@patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False)
def test_start_non_interactive_codex_missing_auth_fails_early(
    mock_setup: MagicMock,
    mock_cfg: MagicMock,
    mock_get_adapters: MagicMock,
    mock_session_service: MagicMock,
    mock_validate_workspace: MagicMock,
    mock_prepare_workspace: MagicMock,
    mock_resolve_team: MagicMock,
    mock_resolve_provider: MagicMock,
    mock_prepare_live_start_plan: MagicMock,
    mock_build_output: MagicMock,
    mock_render_output: MagicMock,
    mock_apply_profile: MagicMock,
    mock_warn_non_worktree: MagicMock,
    mock_resolve_conflict: MagicMock,
    mock_record_session: MagicMock,
    mock_set_workspace_provider: MagicMock,
    mock_collect_readiness: MagicMock,
    mock_ensure_ready: MagicMock,
    mock_show_auth_bootstrap: MagicMock,
    mock_show_launch: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """When auth is missing in non-interactive mode, ensure_launch_ready raises
    ProviderNotReadyError and the launch does not proceed."""
    plan = _build_plan(tmp_path)
    dependencies = _build_dependencies()
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (dependencies, plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.PROCEED,
        plan=plan,
    )
    mock_collect_readiness.return_value = _readiness_auth_missing()
    mock_ensure_ready.side_effect = ProviderNotReadyError(
        provider_id="codex",
        user_message="Codex auth cache is missing and this start is non-interactive.",
        suggested_action="Run 'scc start --provider codex' interactively once.",
    )

    with pytest.raises(ProviderNotReadyError):
        _invoke_start(tmp_path, non_interactive=True)

    mock_collect_readiness.assert_called_once()
    mock_ensure_ready.assert_called_once()
    mock_show_launch.assert_not_called()
    mock_finalize_launch.assert_not_called()
    mock_set_workspace_provider.assert_not_called()


@patch("scc_cli.commands.launch.flow.finalize_launch")
@patch("scc_cli.commands.launch.flow.show_launch_panel")
@patch("scc_cli.commands.launch.flow.show_auth_bootstrap_panel")
@patch("scc_cli.commands.launch.flow.ensure_launch_ready")
@patch("scc_cli.commands.launch.flow.collect_launch_readiness")
@patch("scc_cli.commands.launch.flow.set_workspace_last_used_provider")
@patch("scc_cli.commands.launch.flow._record_session_and_context")
@patch("scc_cli.commands.launch.flow.resolve_launch_conflict")
@patch("scc_cli.commands.launch.flow.warn_if_non_worktree")
@patch("scc_cli.commands.launch.flow._apply_personal_profile", return_value=(None, False))
@patch("scc_cli.commands.launch.flow.render_launch_output")
@patch("scc_cli.commands.launch.flow.build_sync_output_view_model")
@patch("scc_cli.commands.launch.flow.prepare_live_start_plan")
@patch("scc_cli.commands.launch.flow.resolve_launch_provider", return_value=("codex", "explicit"))
@patch("scc_cli.commands.launch.flow.resolve_workspace_team", return_value=None)
@patch("scc_cli.commands.launch.flow.prepare_workspace")
@patch("scc_cli.commands.launch.flow.validate_and_resolve_workspace")
@patch("scc_cli.commands.launch.flow.sessions.get_session_service")
@patch("scc_cli.commands.launch.flow.get_default_adapters")
@patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={})
@patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False)
def test_start_skips_readiness_check_when_already_ready(
    mock_setup: MagicMock,
    mock_cfg: MagicMock,
    mock_get_adapters: MagicMock,
    mock_session_service: MagicMock,
    mock_validate_workspace: MagicMock,
    mock_prepare_workspace: MagicMock,
    mock_resolve_team: MagicMock,
    mock_resolve_provider: MagicMock,
    mock_prepare_live_start_plan: MagicMock,
    mock_build_output: MagicMock,
    mock_render_output: MagicMock,
    mock_apply_profile: MagicMock,
    mock_warn_non_worktree: MagicMock,
    mock_resolve_conflict: MagicMock,
    mock_record_session: MagicMock,
    mock_set_workspace_provider: MagicMock,
    mock_collect_readiness: MagicMock,
    mock_ensure_ready: MagicMock,
    mock_show_auth_bootstrap: MagicMock,
    mock_show_launch: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    """When readiness is already good, ensure_launch_ready is not called."""
    plan = _build_plan(tmp_path)
    dependencies = _build_dependencies()
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (dependencies, plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.PROCEED,
        plan=plan,
    )
    mock_collect_readiness.return_value = _readiness_all_good()

    _invoke_start(tmp_path, non_interactive=False)

    mock_collect_readiness.assert_called_once()
    mock_ensure_ready.assert_not_called()
    mock_finalize_launch.assert_called_once()
