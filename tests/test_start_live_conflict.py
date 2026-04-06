from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.commands.launch.conflict_resolution import (
    LaunchConflictDecision,
    LaunchConflictResolution,
)
from scc_cli.commands.launch.flow import start
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


def _build_start_dependencies() -> StartSessionDependencies:
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=MagicMock(),
        agent_runner=MagicMock(),
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


def _invoke_start(tmp_path: Path) -> None:
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
        provider="codex",
    )


@patch("scc_cli.commands.launch.flow.finalize_launch")
@patch("scc_cli.commands.launch.flow._record_session_and_context")
@patch("scc_cli.commands.launch.flow.resolve_launch_conflict")
@patch("scc_cli.commands.launch.flow.show_launch_panel")
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
def test_start_keep_existing_exits_cleanly_without_recording_or_launching(
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
    mock_show_launch: MagicMock,
    mock_resolve_conflict: MagicMock,
    mock_record_session: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (_build_start_dependencies(), plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.KEEP_EXISTING,
        plan=plan,
    )

    with pytest.raises(typer.Exit) as exc:
        _invoke_start(tmp_path)

    assert exc.value.exit_code == 0
    mock_record_session.assert_not_called()
    mock_finalize_launch.assert_not_called()


@patch("scc_cli.commands.launch.flow.finalize_launch")
@patch("scc_cli.commands.launch.flow._record_session_and_context")
@patch("scc_cli.commands.launch.flow.resolve_launch_conflict")
@patch("scc_cli.commands.launch.flow.show_launch_panel")
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
def test_start_cancel_conflict_exits_130_without_recording_or_launching(
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
    mock_show_launch: MagicMock,
    mock_resolve_conflict: MagicMock,
    mock_record_session: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (_build_start_dependencies(), plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.CANCELLED,
        plan=plan,
    )

    with pytest.raises(typer.Exit) as exc:
        _invoke_start(tmp_path)

    assert exc.value.exit_code == 130
    mock_record_session.assert_not_called()
    mock_finalize_launch.assert_not_called()


@patch("scc_cli.commands.launch.flow.finalize_launch")
@patch("scc_cli.commands.launch.flow._record_session_and_context")
@patch("scc_cli.commands.launch.flow.resolve_launch_conflict")
@patch("scc_cli.commands.launch.flow.show_launch_panel")
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
def test_start_replace_conflict_records_then_launches_with_updated_plan(
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
    mock_show_launch: MagicMock,
    mock_resolve_conflict: MagicMock,
    mock_record_session: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    assert plan.sandbox_spec is not None
    updated_plan = replace(
        plan,
        fresh=True,
        sandbox_spec=replace(plan.sandbox_spec, force_new=True),
    )
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (_build_start_dependencies(), plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.PROCEED,
        plan=updated_plan,
    )

    _invoke_start(tmp_path)

    mock_record_session.assert_called_once()
    mock_finalize_launch.assert_called_once_with(
        updated_plan, dependencies=mock_prepare_live_start_plan.return_value[0]
    )
