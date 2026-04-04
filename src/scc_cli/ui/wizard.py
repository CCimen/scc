"""Wizard-specific pickers with three-state navigation support.

This module provides picker functions for the interactive start wizard,
with proper navigation support for nested screens. All pickers follow
a three-state return contract:

- Success: Returns the selected value (WorkspaceSource, str path, etc.)
- Back: Returns BACK sentinel (Esc pressed - go to previous screen)
- Quit: Returns None (q pressed - exit app entirely)

The BACK sentinel provides type-safe back navigation that callers can
check with identity comparison: `if result is BACK`.

Top-level vs Sub-screen behavior:
- Top-level (pick_workspace_source with allow_back=False): Esc returns None
- Sub-screens (pick_recent_workspace, pick_team_repo): Esc returns BACK, q returns None

Example:
    >>> from scc_cli.ui.wizard import (
    ...     BACK, pick_workspace_source, pick_recent_workspace
    ... )
    >>> from scc_cli.application.launch.start_wizard import WorkspaceSource
    >>>
    >>> while True:
    ...     source = pick_workspace_source(team="platform")
    ...     if source is None:
    ...         break  # User pressed q or Esc at top level - quit
    ...     if source is BACK:
    ...         break
    ...
    ...     if source == WorkspaceSource.RECENT:
    ...         workspace = pick_recent_workspace(recent_sessions)
    ...         if workspace is None:
    ...             break  # User pressed q - quit app
    ...         if workspace is BACK:
    ...             continue  # User pressed Esc - go back to source picker
    ...         return workspace  # Got a valid path
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

from rich.console import Console

from scc_cli.application.interaction_requests import ConfirmRequest, InputRequest, SelectRequest
from scc_cli.application.launch.start_wizard import (  # noqa: F401
    CLONE_REPO_REQUEST_ID,
    CROSS_TEAM_RESUME_REQUEST_ID,
    CUSTOM_WORKSPACE_REQUEST_ID,
    QUICK_RESUME_REQUEST_ID,
    SESSION_NAME_REQUEST_ID,
    TEAM_SELECTION_REQUEST_ID,
    WORKSPACE_PICKER_REQUEST_ID,
    WORKSPACE_SOURCE_REQUEST_ID,
    WORKTREE_CONFIRM_REQUEST_ID,
    WORKTREE_NAME_REQUEST_ID,
    QuickResumeOption,
    QuickResumeViewModel,
    StartWizardPrompt,
    TeamOption,
    TeamRepoPickerViewModel,
    TeamSelectionViewModel,
    WorkspacePickerViewModel,
    WorkspaceSource,
    WorkspaceSourceOption,
    WorkspaceSourceViewModel,
    WorkspaceSummary,
)

from ..ports.session_models import SessionSummary
from ..services.workspace import has_project_markers
from .keys import BACK
from .keys import _BackSentinel as _BackSentinel  # noqa: F401
from .picker import (  # noqa: F401
    QuickResumeResult,
    TeamSwitchRequested,
    _run_single_select_picker,
    pick_context_quick_resume,
    pick_team,
)
from .prompts import (
    confirm_with_layout,
    prompt_custom_workspace,
    prompt_repo_url,
    prompt_with_layout,
)
from .time_format import format_relative_time_calendar
from .wizard_pickers import (  # noqa: F401
    _run_subscreen_picker,
    build_workspace_source_options,
    build_workspace_source_options_from_view_model,
    pick_recent_workspace,
    pick_team_repo,
    pick_workspace_source,
)

if TYPE_CHECKING:
    pass


class StartWizardRendererError(RuntimeError):
    """Error raised for unexpected prompt types in the start wizard renderer."""


# Type variable for generic picker return types
T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════════
# Local Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _normalize_path(path: str) -> str:
    """Collapse HOME to ~ and truncate keeping last 2 segments.

    Uses Path.parts for cross-platform robustness.

    Examples:
        /Users/dev/projects/api → ~/projects/api
        /Users/dev/very/long/path/to/project → ~/…/to/project
        /opt/data/files → /opt/data/files (no home prefix)
    """
    p = Path(path)
    home = Path.home()

    # Try to make path relative to home
    try:
        relative = p.relative_to(home)
        display = "~/" + str(relative)
        starts_with_home = True
    except ValueError:
        display = str(p)
        starts_with_home = False

    # Truncate if too long, keeping last 2 segments for context
    if len(display) > 50:
        parts = p.parts
        if len(parts) >= 2:
            tail = "/".join(parts[-2:])
        elif parts:
            tail = parts[-1]
        else:
            tail = ""

        prefix = "~" if starts_with_home else ""
        display = f"{prefix}/…/{tail}"

    return display


def _format_relative_time(iso_timestamp: str) -> str:
    """Format an ISO timestamp as relative time.

    Examples:
        2 minutes ago → "2m ago"
        3 hours ago → "3h ago"
        yesterday → "yesterday"
        5 days ago → "5d ago"
        older → "Dec 20" (month day format)
    """
    return format_relative_time_calendar(iso_timestamp)


@dataclass(frozen=True)
class StartWizardAnswer:
    """Result of rendering a start wizard prompt."""

    kind: StartWizardAnswerKind
    value: object | None = None


class StartWizardAnswerKind(Enum):
    """Response outcomes for the start wizard prompt renderer."""

    SELECTED = "selected"
    BACK = "back"
    CANCELLED = "cancelled"


class StartWizardAction(Enum):
    """Synthetic wizard actions emitted by the prompt renderer."""

    NEW_SESSION = "new_session"
    TOGGLE_ALL_TEAMS = "toggle_all_teams"
    SWITCH_TEAM = "switch_team"


def _answer_cancelled() -> StartWizardAnswer:
    return StartWizardAnswer(kind=StartWizardAnswerKind.CANCELLED)


def _answer_back() -> StartWizardAnswer:
    return StartWizardAnswer(kind=StartWizardAnswerKind.BACK)


def _answer_selected(value: object) -> StartWizardAnswer:
    return StartWizardAnswer(kind=StartWizardAnswerKind.SELECTED, value=value)


def render_start_wizard_prompt(
    prompt: StartWizardPrompt,
    *,
    console: Console,
    recent_sessions: list[SessionSummary] | None = None,
    available_teams: list[dict[str, Any]] | None = None,
    team_repos: list[dict[str, Any]] | None = None,
    workspace_base: str | None = None,
    allow_back: bool = False,
    standalone: bool = False,
    context_label: str | None = None,
    current_branch: str | None = None,
    effective_team: str | None = None,
) -> StartWizardAnswer:
    """Render a start wizard prompt using existing UI pickers/prompts."""
    request_id = prompt.request.request_id

    if request_id == QUICK_RESUME_REQUEST_ID:
        quick_resume_view = cast(QuickResumeViewModel, prompt.view_model)
        quick_resume_request = cast(SelectRequest[QuickResumeOption], prompt.request)
        contexts = quick_resume_view.contexts
        try:
            result, selected_context = pick_context_quick_resume(
                contexts,
                title=quick_resume_request.title,
                subtitle=quick_resume_request.subtitle,
                standalone=standalone,
                context_label=quick_resume_view.context_label,
                effective_team=effective_team,
                current_branch=current_branch,
            )
        except TeamSwitchRequested:
            return _answer_selected(StartWizardAction.SWITCH_TEAM)
        if result is QuickResumeResult.SELECTED:
            if selected_context is None:
                return _answer_cancelled()
            return _answer_selected(selected_context)
        if result is QuickResumeResult.NEW_SESSION:
            return _answer_selected(StartWizardAction.NEW_SESSION)
        if result is QuickResumeResult.TOGGLE_ALL_TEAMS:
            return _answer_selected(StartWizardAction.TOGGLE_ALL_TEAMS)
        if result is QuickResumeResult.BACK:
            return _answer_back()
        return _answer_cancelled()

    if request_id == TEAM_SELECTION_REQUEST_ID:
        if available_teams is None:
            raise StartWizardRendererError("available_teams required for team selection")
        team_view = cast(TeamSelectionViewModel, prompt.view_model)
        team_request = cast(SelectRequest[TeamOption], prompt.request)
        try:
            selected = pick_team(
                available_teams,
                current_team=team_view.current_team,
                title=team_request.title,
                subtitle=team_request.subtitle,
            )
        except TeamSwitchRequested:
            return _answer_selected(StartWizardAction.SWITCH_TEAM)
        if selected is None:
            return _answer_cancelled()
        return _answer_selected(selected)

    if request_id == WORKSPACE_SOURCE_REQUEST_ID:
        source_view = cast(WorkspaceSourceViewModel, prompt.view_model)
        source_request = cast(SelectRequest[WorkspaceSourceOption], prompt.request)
        try:
            source = pick_workspace_source(
                has_team_repos=any(team_repos or []),
                team=effective_team,
                standalone=standalone,
                allow_back=allow_back,
                context_label=context_label or source_view.context_label,
                subtitle=source_request.subtitle,
                options=list(source_view.options),
                view_model=source_view,
            )
        except TeamSwitchRequested:
            return _answer_selected(StartWizardAction.SWITCH_TEAM)
        if source is BACK:
            return _answer_back()
        if source is None:
            return _answer_cancelled()
        return _answer_selected(source)

    if request_id == WORKSPACE_PICKER_REQUEST_ID:
        if prompt.view_model is None:
            raise StartWizardRendererError("workspace picker view model required")

        if isinstance(prompt.view_model, WorkspacePickerViewModel):
            picker_view = prompt.view_model
            try:
                picker_result = pick_recent_workspace(
                    recent_sessions or [],
                    standalone=standalone,
                    context_label=context_label or picker_view.context_label,
                    options=list(picker_view.options),
                )
            except TeamSwitchRequested:
                return _answer_selected(StartWizardAction.SWITCH_TEAM)
            if picker_result is BACK:
                return _answer_back()
            if picker_result is None:
                return _answer_cancelled()
            return _answer_selected(picker_result)

        if isinstance(prompt.view_model, TeamRepoPickerViewModel):
            repo_view = prompt.view_model
            if team_repos is None:
                raise StartWizardRendererError("team_repos required for team repo selection")
            resolved_workspace_base = workspace_base or repo_view.workspace_base
            try:
                picker_result = pick_team_repo(
                    team_repos,
                    resolved_workspace_base,
                    standalone=standalone,
                    context_label=context_label or repo_view.context_label,
                    options=list(repo_view.options),
                )
            except TeamSwitchRequested:
                return _answer_selected(StartWizardAction.SWITCH_TEAM)
            if picker_result is BACK:
                return _answer_back()
            if picker_result is None:
                return _answer_cancelled()
            return _answer_selected(picker_result)

        msg = f"Unsupported workspace picker view model: {type(prompt.view_model)}"
        raise StartWizardRendererError(msg)

    if request_id == CUSTOM_WORKSPACE_REQUEST_ID:
        custom_request = cast(InputRequest, prompt.request)
        prompt_text = f"[cyan]{custom_request.prompt}[/cyan]"
        workspace_path = prompt_custom_workspace(console, prompt=prompt_text)
        if workspace_path is None:
            return _answer_back()
        return _answer_selected(workspace_path)

    if request_id == CLONE_REPO_REQUEST_ID:
        clone_request = cast(InputRequest, prompt.request)
        prompt_text = f"[cyan]{clone_request.prompt}[/cyan]"
        repo_url = prompt_repo_url(console, prompt=prompt_text)
        if not repo_url:
            return _answer_back()
        from .git_interactive import clone_repo

        resolved_base = workspace_base or "~/projects"
        workspace = clone_repo(repo_url, resolved_base)
        if workspace is None:
            return _answer_back()
        return _answer_selected(workspace)

    if request_id == CROSS_TEAM_RESUME_REQUEST_ID:
        confirm_request = cast(ConfirmRequest, prompt.request)
        prompt_text = confirm_request.prompt
        confirm = confirm_with_layout(
            console,
            prompt_text,
            default=prompt.default_response or False,
        )
        return _answer_selected(confirm)

    if request_id == WORKTREE_CONFIRM_REQUEST_ID:
        confirm_request = cast(ConfirmRequest, prompt.request)
        prompt_text = f"[cyan]{confirm_request.prompt}[/cyan]"
        confirm = confirm_with_layout(
            console,
            prompt_text,
            default=prompt.default_response or False,
        )
        return _answer_selected(confirm)

    if request_id == WORKTREE_NAME_REQUEST_ID:
        worktree_request = cast(InputRequest, prompt.request)
        prompt_text = f"[cyan]{worktree_request.prompt}[/cyan]"
        worktree_name = prompt_with_layout(console, prompt_text)
        if worktree_name is None:
            return _answer_back()
        return _answer_selected(worktree_name)

    if request_id == SESSION_NAME_REQUEST_ID:
        session_request = cast(InputRequest, prompt.request)
        prompt_text = "[cyan]Session name[/cyan] [dim](optional, for easy resume)[/dim]"
        session_name_value = prompt_with_layout(
            console,
            prompt_text,
            default=session_request.default or "",
        )
        return _answer_selected(session_name_value or None)

    msg = f"Unsupported start wizard prompt: {prompt.request.request_id}"
    raise StartWizardRendererError(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# Workspace Source Option Builder
# ═══════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────────
# Project Marker Detection (delegates to services layer)
# ─────────────────────────────────────────────────────────────────────────────


def _has_project_markers(path: Path) -> bool:
    """Check if a directory has common project markers."""
    return has_project_markers(path)


def _is_valid_workspace(path: Path) -> bool:
    """Check if a directory looks like a valid workspace."""
    return has_project_markers(path)
