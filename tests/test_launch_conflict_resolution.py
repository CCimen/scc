from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.commands.launch.conflict_resolution import (
    LaunchConflictDecision,
    _ConflictAction,
    resolve_launch_conflict,
)
from scc_cli.core.errors import ExistingSandboxConflictError
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.models import (
    MountSpec,
    SandboxConflict,
    SandboxHandle,
    SandboxSpec,
    SandboxState,
)


@dataclass
class _ConflictRuntime:
    conflict: SandboxConflict | None = None

    def ensure_available(self) -> None:
        return None

    def run(self, spec: SandboxSpec):  # pragma: no cover - not used in these tests
        raise NotImplementedError

    def detect_launch_conflict(self, spec: SandboxSpec) -> SandboxConflict | None:
        return self.conflict

    def resume(self, handle):  # pragma: no cover - protocol completeness
        return None

    def stop(self, handle):  # pragma: no cover - protocol completeness
        return None

    def remove(self, handle):  # pragma: no cover - protocol completeness
        return None

    def list_running(self):  # pragma: no cover - protocol completeness
        return []

    def status(self, handle):  # pragma: no cover - protocol completeness
        raise NotImplementedError


def _build_plan(tmp_path: Path) -> StartSessionPlan:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    resolver = ResolverResult(
        workspace_root=workspace,
        entry_dir=workspace,
        mount_root=workspace,
        container_workdir=str(workspace),
        is_auto_detected=False,
        is_suspicious=False,
        reason="test",
    )
    sandbox_spec = SandboxSpec(
        image="scc-agent-codex:latest",
        workspace_mount=MountSpec(source=workspace, target=workspace),
        workdir=workspace,
        provider_id="codex",
    )
    return StartSessionPlan(
        resolver_result=resolver,
        workspace_path=workspace,
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


def _build_dependencies(conflict: SandboxConflict | None) -> StartSessionDependencies:
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=MagicMock(),
        agent_runner=MagicMock(),
        sandbox_runtime=_ConflictRuntime(conflict=conflict),
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
    )


def _console() -> Console:
    return Console(file=StringIO(), force_terminal=False, width=120)


def _conflict() -> SandboxConflict:
    return SandboxConflict(
        handle=SandboxHandle(sandbox_id="cid-123", name="scc-oci-123"),
        state=SandboxState.RUNNING,
        process_summary="codex --dangerously-bypass-approvals-and-sandbox",
    )


def test_resolve_launch_conflict_returns_proceed_when_no_conflict(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path)
    resolution = resolve_launch_conflict(
        plan,
        dependencies=_build_dependencies(None),
        console=_console(),
        display_name="Codex",
        json_mode=False,
        non_interactive=False,
    )

    assert resolution.decision is LaunchConflictDecision.PROCEED
    assert resolution.plan is plan
    assert resolution.conflict is None


def test_resolve_launch_conflict_non_interactive_raises_actionable_error(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path)

    with pytest.raises(ExistingSandboxConflictError, match="already running"):
        resolve_launch_conflict(
            plan,
            dependencies=_build_dependencies(_conflict()),
            console=_console(),
            display_name="Codex",
            json_mode=False,
            non_interactive=True,
        )


@patch("scc_cli.commands.launch.conflict_resolution.is_interactive_allowed", return_value=True)
@patch("scc_cli.commands.launch.conflict_resolution._prompt_for_conflict")
def test_resolve_launch_conflict_replace_marks_plan_fresh(
    mock_prompt: MagicMock,
    mock_interactive_allowed: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    mock_prompt.return_value = _ConflictAction.REPLACE

    resolution = resolve_launch_conflict(
        plan,
        dependencies=_build_dependencies(_conflict()),
        console=_console(),
        display_name="Codex",
        json_mode=False,
        non_interactive=False,
    )

    assert resolution.decision is LaunchConflictDecision.PROCEED
    assert resolution.conflict is not None
    assert resolution.plan.sandbox_spec is not None
    assert resolution.plan.sandbox_spec.force_new is True
    assert plan.sandbox_spec is not None
    assert plan.sandbox_spec.force_new is False


@patch("scc_cli.commands.launch.conflict_resolution.is_interactive_allowed", return_value=True)
@patch("scc_cli.commands.launch.conflict_resolution._prompt_for_conflict")
def test_resolve_launch_conflict_keep_existing_returns_keep_decision(
    mock_prompt: MagicMock,
    mock_interactive_allowed: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    mock_prompt.return_value = _ConflictAction.KEEP

    resolution = resolve_launch_conflict(
        plan,
        dependencies=_build_dependencies(_conflict()),
        console=_console(),
        display_name="Codex",
        json_mode=False,
        non_interactive=False,
    )

    assert resolution.decision is LaunchConflictDecision.KEEP_EXISTING
    assert resolution.plan is plan


@patch("scc_cli.commands.launch.conflict_resolution.is_interactive_allowed", return_value=True)
@patch("scc_cli.commands.launch.conflict_resolution._prompt_for_conflict")
def test_resolve_launch_conflict_cancel_returns_cancelled(
    mock_prompt: MagicMock,
    mock_interactive_allowed: MagicMock,
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path)
    mock_prompt.return_value = _ConflictAction.CANCEL

    resolution = resolve_launch_conflict(
        plan,
        dependencies=_build_dependencies(_conflict()),
        console=_console(),
        display_name="Codex",
        json_mode=False,
        non_interactive=False,
    )

    assert resolution.decision is LaunchConflictDecision.CANCELLED
    assert resolution.plan is plan
