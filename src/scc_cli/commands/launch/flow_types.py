"""Shared typing helpers for launch flow modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from ...application.launch import (
    StartWizardContext,
    StartWizardState,
    StartWizardStep,
    WorkspaceSource,
)
from ...contexts import WorkContext
from ...ui.keys import _BackSentinel

StartWizardResult: TypeAlias = tuple[
    str | _BackSentinel | None,
    str | None,
    str | None,
    str | None,
]
QuickResumeResolution: TypeAlias = StartWizardState | StartWizardResult
WorkspaceResumeResolution: TypeAlias = StartWizardState | StartWizardResult | None


@dataclass(frozen=True)
class WizardResumeContext:
    """Explicit inputs for quick-resume helper flows."""

    standalone_mode: bool
    allow_back: bool
    effective_team: str | None
    team_override: str | None
    active_team_label: str
    active_team_context: str
    current_branch: str | None


def set_team_context(state: StartWizardState, team: str | None) -> StartWizardState:
    """Return new wizard state with updated team, preserving other context fields."""
    context = StartWizardContext(
        team=team,
        workspace_source=state.context.workspace_source,
        workspace=state.context.workspace,
        worktree_name=state.context.worktree_name,
        session_name=state.context.session_name,
    )
    return StartWizardState(step=state.step, context=context, config=state.config)


def set_workspace(
    state: StartWizardState,
    workspace: str,
    workspace_source: WorkspaceSource | None = None,
    *,
    standalone_mode: bool,
    team_override: str | None,
    effective_team: str | None,
) -> StartWizardState:
    """Return new wizard state with workspace set and step advanced to WORKTREE_DECISION."""
    resolved_team = state.context.team
    if resolved_team is None and not standalone_mode:
        resolved_team = team_override or effective_team
    context = StartWizardContext(
        team=resolved_team,
        workspace_source=workspace_source or state.context.workspace_source,
        workspace=workspace,
        worktree_name=state.context.worktree_name,
        session_name=state.context.session_name,
    )
    return StartWizardState(
        step=StartWizardStep.WORKTREE_DECISION, context=context, config=state.config
    )


def reset_for_team_switch(state: StartWizardState) -> StartWizardState:
    """Reset wizard state for team switch, clearing workspace selections."""
    next_step = (
        StartWizardStep.TEAM_SELECTION
        if state.config.team_selection_required
        else StartWizardStep.WORKSPACE_SOURCE
    )
    reset_team = None if state.config.team_selection_required else state.context.team
    return StartWizardState(
        step=next_step,
        context=StartWizardContext(team=reset_team),
        config=state.config,
    )


def filter_contexts_for_workspace(
    workspace: Path,
    contexts: list[WorkContext],
) -> list[WorkContext]:
    """Filter work contexts that match the given workspace path."""
    result: list[WorkContext] = []
    for ctx in contexts:
        if ctx.worktree_path == workspace:
            result.append(ctx)
            continue
        if ctx.repo_root == workspace:
            result.append(ctx)
            continue
        try:
            if workspace.is_relative_to(ctx.worktree_path):
                result.append(ctx)
                continue
            if workspace.is_relative_to(ctx.repo_root):
                result.append(ctx)
        except ValueError:
            pass
    return result
