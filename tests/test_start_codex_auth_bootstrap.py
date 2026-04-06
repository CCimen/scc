from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.commands.launch.conflict_resolution import (
    LaunchConflictDecision,
    LaunchConflictResolution,
)
from scc_cli.commands.launch.flow import start
from scc_cli.core.contracts import AuthReadiness, ProviderCapabilityProfile
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


def _build_dependencies_with_missing_codex_auth() -> StartSessionDependencies:
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
        status="missing",
        mechanism="auth_json_file",
        guidance="Run 'scc start --provider codex' to begin one-time browser sign-in.",
    )
    provider.bootstrap_auth = MagicMock()
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=MagicMock(),
        agent_runner=MagicMock(),
        agent_provider=provider,
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
@patch("scc_cli.commands.launch.flow.ensure_provider_image")
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
def test_start_shows_codex_auth_bootstrap_notice_before_launch(
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
    mock_ensure_image: MagicMock,
    mock_show_auth_bootstrap: MagicMock,
    mock_show_launch: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    dependencies = _build_dependencies_with_missing_codex_auth()
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (dependencies, plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.PROCEED,
        plan=plan,
    )

    _invoke_start(tmp_path, non_interactive=False)

    mock_ensure_image.assert_called_once()
    mock_show_auth_bootstrap.assert_called_once()
    provider = cast(MagicMock, dependencies.agent_provider)
    provider.bootstrap_auth.assert_called_once()
    mock_show_launch.assert_called_once()
    mock_finalize_launch.assert_called_once()
    mock_set_workspace_provider.assert_called_once_with(tmp_path, "codex")


@patch("scc_cli.commands.launch.flow.finalize_launch")
@patch("scc_cli.commands.launch.flow.show_launch_panel")
@patch("scc_cli.commands.launch.flow.show_auth_bootstrap_panel")
@patch("scc_cli.commands.launch.flow.ensure_provider_image")
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
    mock_ensure_image: MagicMock,
    mock_show_auth_bootstrap: MagicMock,
    mock_show_launch: MagicMock,
    mock_finalize_launch: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    dependencies = _build_dependencies_with_missing_codex_auth()
    mock_get_adapters.return_value = _build_adapters()
    mock_validate_workspace.return_value = tmp_path
    mock_prepare_workspace.return_value = tmp_path
    mock_prepare_live_start_plan.return_value = (dependencies, plan)
    mock_resolve_conflict.return_value = LaunchConflictResolution(
        decision=LaunchConflictDecision.PROCEED,
        plan=plan,
    )

    with pytest.raises(ProviderNotReadyError):
        _invoke_start(tmp_path, non_interactive=True)

    mock_ensure_image.assert_called_once()
    mock_show_auth_bootstrap.assert_not_called()
    provider = cast(MagicMock, dependencies.agent_provider)
    provider.bootstrap_auth.assert_not_called()
    mock_show_launch.assert_not_called()
    mock_finalize_launch.assert_not_called()
    mock_set_workspace_provider.assert_not_called()
