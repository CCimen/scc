"""Complete a prepared live launch plan."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from rich.console import Console

from scc_cli import workspace_local_config
from scc_cli.application import launch as app_launch
from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.core.provider_resolution import get_provider_display_name

from . import conflict_resolution, flow_session, render


class PreparedLaunchCompletionDecision(Enum):
    """Outcome from completing an already-prepared live launch."""

    LAUNCHED = auto()
    CANCELLED = auto()
    KEPT_EXISTING = auto()


@dataclass(frozen=True)
class PreparedLaunchCompletionRequest:
    """Inputs needed after launch planning has succeeded."""

    workspace_path: Path
    team: str | None
    session_name: str | None
    current_branch: str | None
    provider_id: str
    start_plan: StartSessionPlan
    dependencies: StartSessionDependencies
    is_resume: bool
    json_mode: bool
    non_interactive: bool
    record_session: bool


@dataclass(frozen=True)
class PreparedLaunchCompletionResult:
    """Result from completing a prepared live launch."""

    decision: PreparedLaunchCompletionDecision
    message: str | None = None


def complete_prepared_launch(
    request: PreparedLaunchCompletionRequest,
    *,
    console: Console,
) -> PreparedLaunchCompletionResult:
    """Resolve conflicts, launch, and persist provider selection."""
    display_name = get_provider_display_name(request.provider_id)
    conflict = conflict_resolution.resolve_launch_conflict(
        request.start_plan,
        dependencies=request.dependencies,
        console=console,
        display_name=display_name,
        json_mode=request.json_mode,
        non_interactive=request.non_interactive,
    )
    if conflict.decision is conflict_resolution.LaunchConflictDecision.KEEP_EXISTING:
        workspace_local_config.set_workspace_last_used_provider(
            request.workspace_path,
            request.provider_id,
        )
        return PreparedLaunchCompletionResult(
            decision=PreparedLaunchCompletionDecision.KEPT_EXISTING,
            message="Kept existing sandbox",
        )
    if conflict.decision is conflict_resolution.LaunchConflictDecision.CANCELLED:
        return PreparedLaunchCompletionResult(
            decision=PreparedLaunchCompletionDecision.CANCELLED,
            message="Start cancelled",
        )

    if request.record_session:
        flow_session._record_session_and_context(
            request.workspace_path,
            request.team,
            request.session_name,
            request.current_branch,
            provider_id=request.provider_id,
        )
    render.show_launch_panel(
        workspace=request.workspace_path,
        team=request.team,
        session_name=request.session_name,
        branch=request.current_branch,
        is_resume=request.is_resume,
        display_name=display_name,
    )
    app_launch.finalize_launch(conflict.plan, dependencies=request.dependencies)
    workspace_local_config.set_workspace_last_used_provider(
        request.workspace_path,
        request.provider_id,
    )
    return PreparedLaunchCompletionResult(
        decision=PreparedLaunchCompletionDecision.LAUNCHED,
    )
