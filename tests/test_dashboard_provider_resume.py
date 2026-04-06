"""Tests for provider-neutral dashboard start and resume handlers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from scc_cli.application import dashboard as app_dashboard
from scc_cli.commands.launch.conflict_resolution import LaunchConflictDecision
from scc_cli.commands.launch.preflight import (
    AuthStatus,
    ImageStatus,
    LaunchReadiness,
    ProviderResolutionSource,
)
from scc_cli.ports.session_models import SessionSummary
from scc_cli.ui.dashboard.orchestrator_handlers import (
    _handle_session_resume,
    _handle_worktree_start,
)


def _fake_adapters() -> MagicMock:
    adapters = MagicMock()
    adapters.sandbox_runtime.ensure_available.return_value = None
    provider = MagicMock()
    provider.capability_profile.return_value.display_name = "Codex"
    provider.auth_check.return_value.status = "present"
    adapters.agent_provider = provider
    adapters.codex_agent_provider = provider
    return adapters


def _ready_readiness(provider_id: str = "codex") -> LaunchReadiness:
    return LaunchReadiness(
        provider_id=provider_id,
        resolution_source=ProviderResolutionSource.GLOBAL_PREFERRED,
        image_status=ImageStatus.AVAILABLE,
        auth_status=AuthStatus.PRESENT,
        requires_image_bootstrap=False,
        requires_auth_bootstrap=False,
        launch_ready=True,
    )


@patch("scc_cli.config.load_user_config", return_value={})
@patch("scc_cli.config.load_cached_org_config", return_value=None)
@patch("scc_cli.commands.launch.workspace.validate_and_resolve_workspace")
@patch("scc_cli.bootstrap.get_default_adapters")
@patch(
    "scc_cli.commands.launch.preflight.resolve_launch_provider",
    return_value=("codex", ProviderResolutionSource.RESUME),
)
@patch("scc_cli.commands.launch.preflight.collect_launch_readiness")
@patch("scc_cli.commands.launch.dependencies.prepare_live_start_plan")
@patch("scc_cli.commands.launch.conflict_resolution.resolve_launch_conflict")
@patch("scc_cli.commands.launch.render.show_launch_panel")
@patch("scc_cli.application.launch.finalize_launch")
@patch("scc_cli.workspace_local_config.set_workspace_last_used_provider")
def test_handle_session_resume_uses_provider_neutral_pipeline(
    mock_set_workspace_provider: MagicMock,
    mock_finalize: MagicMock,
    mock_launch_panel: MagicMock,
    mock_conflict: MagicMock,
    mock_prepare: MagicMock,
    mock_readiness: MagicMock,
    _mock_resolve: MagicMock,
    mock_adapters: MagicMock,
    mock_validate: MagicMock,
    _mock_org: MagicMock,
    _mock_cfg: MagicMock,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "repo"
    workspace.mkdir()
    mock_validate.return_value = workspace
    adapters = _fake_adapters()
    mock_adapters.return_value = adapters
    mock_readiness.return_value = _ready_readiness()
    start_plan = MagicMock()
    start_plan.current_branch = "develop"
    mock_prepare.return_value = (adapters, start_plan)
    mock_conflict.return_value = MagicMock(
        decision=LaunchConflictDecision.PROCEED,
        plan=start_plan,
    )

    session = SessionSummary(
        name="develop",
        workspace=str(workspace),
        team=None,
        last_used=None,
        container_name="scc-oci-123",
        branch="develop",
        provider_id="codex",
    )

    assert _handle_session_resume(session) is True

    request = mock_prepare.call_args.args[0]
    assert request.provider_id == "codex"
    assert request.resume is True
    mock_readiness.assert_called_once()
    mock_launch_panel.assert_called_once()
    mock_finalize.assert_called_once_with(start_plan, dependencies=adapters)
    mock_set_workspace_provider.assert_called_once_with(workspace, "codex")


@patch("scc_cli.config.load_user_config", return_value={})
@patch("scc_cli.config.load_cached_org_config", return_value=None)
@patch("scc_cli.config.get_selected_provider", return_value=None)
@patch("scc_cli.commands.launch.workspace.validate_and_resolve_workspace")
@patch("scc_cli.bootstrap.get_default_adapters")
@patch(
    "scc_cli.commands.launch.preflight.resolve_launch_provider",
    return_value=("codex", ProviderResolutionSource.GLOBAL_PREFERRED),
)
@patch("scc_cli.commands.launch.preflight.collect_launch_readiness")
@patch("scc_cli.commands.launch.dependencies.prepare_live_start_plan")
@patch("scc_cli.commands.launch.conflict_resolution.resolve_launch_conflict")
@patch("scc_cli.commands.launch.render.show_launch_panel")
@patch("scc_cli.application.launch.finalize_launch")
@patch("scc_cli.workspace_local_config.set_workspace_last_used_provider")
def test_handle_worktree_start_uses_provider_neutral_pipeline(
    mock_set_workspace_provider: MagicMock,
    mock_finalize: MagicMock,
    mock_launch_panel: MagicMock,
    mock_conflict: MagicMock,
    mock_prepare: MagicMock,
    mock_readiness: MagicMock,
    _mock_resolve: MagicMock,
    mock_adapters: MagicMock,
    mock_validate: MagicMock,
    _mock_selected: MagicMock,
    _mock_org: MagicMock,
    _mock_cfg: MagicMock,
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "worktree"
    workspace.mkdir()
    mock_validate.return_value = workspace
    adapters = _fake_adapters()
    mock_adapters.return_value = adapters
    mock_readiness.return_value = _ready_readiness()
    start_plan = MagicMock()
    start_plan.current_branch = "feature"
    mock_prepare.return_value = (adapters, start_plan)
    mock_conflict.return_value = MagicMock(
        decision=LaunchConflictDecision.PROCEED,
        plan=start_plan,
    )

    result = _handle_worktree_start(str(workspace))

    assert result.decision is app_dashboard.StartFlowDecision.LAUNCHED
    request = mock_prepare.call_args.args[0]
    assert request.provider_id == "codex"
    assert request.resume is False
    mock_readiness.assert_called_once()
    mock_launch_panel.assert_called_once()
    mock_finalize.assert_called_once_with(start_plan, dependencies=adapters)
    mock_set_workspace_provider.assert_called_once_with(workspace, "codex")
