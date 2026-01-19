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
from scc_cli.application.launch.start_wizard import (
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
    TeamRepoOption,
    TeamRepoPickerViewModel,
    TeamSelectionViewModel,
    WorkspacePickerViewModel,
    WorkspaceSource,
    WorkspaceSourceOption,
    WorkspaceSourceViewModel,
    WorkspaceSummary,
)

from ..ports.session_models import SessionSummary
from ..services.workspace import has_project_markers, is_suspicious_directory
from .keys import BACK, _BackSentinel
from .list_screen import ListItem
from .picker import (
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


def build_workspace_source_options(
    *,
    has_team_repos: bool,
    include_current_dir: bool = True,
) -> list[WorkspaceSourceOption]:
    options: list[WorkspaceSourceOption] = []

    if include_current_dir:
        # Check current directory for project markers and git status
        # Import here to avoid circular dependencies
        from scc_cli.services import git as git_service

        cwd = Path.cwd()
        cwd_name = cwd.name or str(cwd)
        is_git = git_service.is_git_repo(cwd)

        # Three-tier logic with git awareness:
        # 1. Suspicious directory (home, /, tmp) -> don't show
        # 2. Has project markers + git -> show folder name (confident)
        # 3. Has project markers, no git -> show "folder (no git)"
        # 4. No markers, not suspicious -> show "folder (no git)"
        if not is_suspicious_directory(cwd):
            if _has_project_markers(cwd):
                if is_git:
                    options.append(
                        WorkspaceSourceOption(
                            source=WorkspaceSource.CURRENT_DIR,
                            label="• Current directory",
                            description=cwd_name,
                        )
                    )
                else:
                    options.append(
                        WorkspaceSourceOption(
                            source=WorkspaceSource.CURRENT_DIR,
                            label="• Current directory",
                            description=f"{cwd_name} (no git)",
                        )
                    )
            else:
                options.append(
                    WorkspaceSourceOption(
                        source=WorkspaceSource.CURRENT_DIR,
                        label="• Current directory",
                        description=f"{cwd_name} (no git)",
                    )
                )

    options.append(
        WorkspaceSourceOption(
            source=WorkspaceSource.RECENT,
            label="• Recent workspaces",
            description="Continue working on previous project",
        )
    )

    if has_team_repos:
        options.append(
            WorkspaceSourceOption(
                source=WorkspaceSource.TEAM_REPOS,
                label="• Team repositories",
                description="Choose from team's common repos",
            )
        )

    options.extend(
        [
            WorkspaceSourceOption(
                source=WorkspaceSource.CUSTOM,
                label="• Enter path",
                description="Specify a local directory path",
            ),
            WorkspaceSourceOption(
                source=WorkspaceSource.CLONE,
                label="• Clone repository",
                description="Clone a Git repository",
            ),
        ]
    )

    return options


def build_workspace_source_options_from_view_model(
    view_model: WorkspaceSourceViewModel,
) -> list[WorkspaceSourceOption]:
    """Build workspace source options from view model data flags.

    This function is called by the UI layer when the view model has empty
    options. It builds presentation options based on the data flags
    provided by the application layer (cwd_context, has_team_repos).

    The design follows clean architecture:
    - Application layer provides data (cwd_context, has_team_repos)
    - UI layer decides how to present that data (this function)

    Args:
        view_model: WorkspaceSourceViewModel with data flags populated.

    Returns:
        List of WorkspaceSourceOption for the picker.
    """
    options: list[WorkspaceSourceOption] = []

    # Current directory - only if cwd_context is provided (means it's not suspicious)
    if view_model.cwd_context is not None:
        ctx = view_model.cwd_context
        # Format description based on git status
        if ctx.is_git:
            description = ctx.name
        else:
            description = f"{ctx.name} (no git)"
        options.append(
            WorkspaceSourceOption(
                source=WorkspaceSource.CURRENT_DIR,
                label="• Current directory",
                description=description,
            )
        )

    # Recent workspaces - always available
    options.append(
        WorkspaceSourceOption(
            source=WorkspaceSource.RECENT,
            label="• Recent workspaces",
            description="Continue working on previous project",
        )
    )

    # Team repositories - only if available
    if view_model.has_team_repos:
        options.append(
            WorkspaceSourceOption(
                source=WorkspaceSource.TEAM_REPOS,
                label="• Team repositories",
                description="Choose from team's common repos",
            )
        )

    # Enter path and Clone - always available
    options.extend(
        [
            WorkspaceSourceOption(
                source=WorkspaceSource.CUSTOM,
                label="• Enter path",
                description="Specify a local directory path",
            ),
            WorkspaceSourceOption(
                source=WorkspaceSource.CLONE,
                label="• Clone repository",
                description="Clone a Git repository",
            ),
        ]
    )

    return options


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-screen Picker Wrapper
# ═══════════════════════════════════════════════════════════════════════════════


def _run_subscreen_picker(
    items: list[ListItem[T]],
    title: str,
    subtitle: str | None = None,
    *,
    standalone: bool = False,
    context_label: str | None = None,
) -> T | _BackSentinel | None:
    """Run picker for sub-screens with three-state return contract.

    Sub-screen pickers distinguish between:
    - Esc (go back to previous screen) → BACK sentinel
    - q (quit app entirely) → None

    Args:
        items: List items to display (first item should be "← Back").
        title: Title for chrome header.
        subtitle: Optional subtitle.
        standalone: If True, dim the "t teams" hint (not available without org).

    Returns:
        Selected item value, BACK if Esc pressed, or None if q pressed (quit).
    """
    # Pass allow_back=True so picker distinguishes Esc (BACK) from q (None)
    result = _run_single_select_picker(
        items,
        title=title,
        subtitle=subtitle,
        standalone=standalone,
        allow_back=True,
        context_label=context_label,
    )
    # Three-state contract:
    # - T value: user selected an item
    # - BACK: user pressed Esc (go back)
    # - None: user pressed q (quit app)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Top-Level Picker: Workspace Source
# ═══════════════════════════════════════════════════════════════════════════════


# ─────────────────────────────────────────────────────────────────────────────
# Project Marker Detection (delegates to services layer)
# ─────────────────────────────────────────────────────────────────────────────


def _has_project_markers(path: Path) -> bool:
    """Check if a directory has common project markers.

    Delegates to the service layer for the actual check.
    This wrapper is kept for backwards compatibility with existing callers.

    Args:
        path: Directory to check.

    Returns:
        True if directory has any recognizable project markers.
    """
    return has_project_markers(path)


def _is_valid_workspace(path: Path) -> bool:
    """Check if a directory looks like a valid workspace.

    A valid workspace must have at least one of:
    - .git directory or file (for worktrees)
    - .scc.yaml config file
    - Common project markers (package.json, pyproject.toml, etc.)

    Random directories (like $HOME) are NOT valid workspaces.

    Delegates to the service layer for the actual check.

    Args:
        path: Directory to check.

    Returns:
        True if directory exists and has workspace markers.
    """
    return has_project_markers(path)


def pick_workspace_source(
    has_team_repos: bool = False,
    team: str | None = None,
    *,
    standalone: bool = False,
    allow_back: bool = False,
    context_label: str | None = None,
    include_current_dir: bool = True,
    subtitle: str | None = None,
    options: list[WorkspaceSourceOption] | None = None,
    view_model: WorkspaceSourceViewModel | None = None,
) -> WorkspaceSource | _BackSentinel | None:
    """Show picker for workspace source selection.

    Three-state return contract:
    - Success: Returns WorkspaceSource (user selected an option)
    - Back: Returns BACK sentinel (user pressed Esc, only if allow_back=True)
    - Quit: Returns None (user pressed q)

    Args:
        has_team_repos: Whether team repositories are available.
        team: Current team name (used for context label if not provided).
        standalone: If True, dim the "t teams" hint (not available without org).
        allow_back: If True, Esc returns BACK (for sub-screen context like Dashboard).
            If False, Esc returns None (for top-level CLI context).
        context_label: Optional context label (e.g., "Team: platform") shown in header.
        include_current_dir: Whether to include current directory as an option.
        subtitle: Optional subtitle override.
        options: Optional prebuilt workspace source options to render.
        view_model: Optional view model with data flags (cwd_context, has_team_repos).
            When provided with empty options, uses these flags to build options.

    Returns:
        Selected WorkspaceSource, BACK if allow_back and Esc pressed, or None if quit.
    """
    # Build subtitle based on context
    resolved_subtitle = subtitle
    if resolved_subtitle is None:
        resolved_subtitle = "Pick a project source (press 't' to switch team)"
        if options is not None:
            resolved_subtitle = None
        elif standalone:
            resolved_subtitle = "Pick a project source"
    resolved_context_label = context_label
    if resolved_context_label is None and team:
        resolved_context_label = f"Team: {team}"

    # Build items list - start with CWD option if appropriate
    items: list[ListItem[WorkspaceSource]] = []

    source_options = options
    if not source_options:
        # If view model is provided, build options from it
        # This is the clean architecture approach: application provides data,
        # UI layer builds presentation options
        if view_model is not None:
            source_options = build_workspace_source_options_from_view_model(view_model)
        else:
            # Fallback to original logic for backwards compatibility
            # (when called without view_model from legacy code paths)
            source_options = build_workspace_source_options(
                has_team_repos=has_team_repos,
                include_current_dir=include_current_dir,
            )

    for option in source_options:
        items.append(
            ListItem(
                label=option.label,
                description=option.description,
                value=option.source,
            )
        )

    if allow_back:
        result = _run_single_select_picker(
            items=items,
            title="Where is your project?",
            subtitle=resolved_subtitle,
            standalone=standalone,
            allow_back=True,
            context_label=resolved_context_label,
        )
    else:
        result = _run_single_select_picker(
            items=items,
            title="Where is your project?",
            subtitle=resolved_subtitle,
            standalone=standalone,
            allow_back=False,
            context_label=resolved_context_label,
        )

    if result is BACK:
        return BACK
    if result is None:
        return None
    if isinstance(result, WorkspaceSource):
        return result
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-Screen Picker: Recent Workspaces
# ═══════════════════════════════════════════════════════════════════════════════


def pick_recent_workspace(
    recent: list[SessionSummary],
    *,
    standalone: bool = False,
    context_label: str | None = None,
    options: list[WorkspaceSummary] | None = None,
) -> str | _BackSentinel | None:
    """Show picker for recent workspace selection.

    This is a sub-screen picker with three-state return contract:
    - str: User selected a workspace path
    - BACK: User pressed Esc (go back to previous screen)
    - None: User pressed q (quit app entirely)

    Args:
        recent: List of recent session summaries with workspace and last_used fields.
        standalone: If True, dim the "t teams" hint (not available without org).
        context_label: Optional context label (e.g., "Team: platform") shown in header.
        options: Optional prebuilt workspace summaries to render.

    Returns:
        Selected workspace path, BACK if Esc pressed, or None if q pressed (quit).
    """
    # Build items with "← Back" first
    items: list[ListItem[str | _BackSentinel]] = [
        ListItem(
            label="← Back",
            description="",
            value=BACK,
        ),
    ]

    summaries = options or []
    if not summaries:
        for session in recent:
            workspace = session.workspace
            last_used = session.last_used or ""
            summaries.append(
                WorkspaceSummary(
                    label=_normalize_path(workspace),
                    description=_format_relative_time(last_used),
                    workspace=workspace,
                )
            )

    # Add recent workspaces
    for summary in summaries:
        items.append(
            ListItem(
                label=summary.label,
                description=summary.description,
                value=summary.workspace,
            )
        )

    # Empty state hint in subtitle
    if len(items) == 1:  # Only "← Back"
        subtitle = "No recent workspaces found"
    else:
        subtitle = None

    return _run_subscreen_picker(
        items=items,
        title="Recent Workspaces",
        subtitle=subtitle,
        standalone=standalone,
        context_label=context_label,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-Screen Picker: Team Repositories (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════════


def pick_team_repo(
    repos: list[dict[str, Any]],
    workspace_base: str = "~/projects",
    *,
    standalone: bool = False,
    context_label: str | None = None,
    options: list[TeamRepoOption] | None = None,
) -> str | _BackSentinel | None:
    """Show picker for team repository selection.

    This is a sub-screen picker with three-state return contract:
    - str: User selected a repo (returns existing local_path or newly cloned path)
    - BACK: User pressed Esc (go back to previous screen)
    - None: User pressed q (quit app entirely)

    If the selected repo has a local_path that exists, returns that path.
    Otherwise, clones the repository and returns the new path.

    Args:
        repos: List of repo dicts with 'name', 'url', optional 'description', 'local_path'.
        workspace_base: Base directory for cloning new repos.
        standalone: If True, dim the "t teams" hint (not available without org).
        context_label: Optional context label (e.g., "Team: platform") shown in header.
        options: Optional prebuilt repo options to render.

    Returns:
        Workspace path (existing or newly cloned), BACK if Esc pressed, or None if q pressed.
    """
    # Build items with "← Back" first
    items: list[ListItem[TeamRepoOption | _BackSentinel]] = [
        ListItem(
            label="← Back",
            description="",
            value=BACK,
        ),
    ]

    resolved_options: list[TeamRepoOption] = list(options) if options is not None else []
    if not resolved_options:
        for repo in repos:
            resolved_options.append(
                TeamRepoOption(
                    name=repo.get("name", repo.get("url", "Unknown")),
                    description=repo.get("description", ""),
                    url=repo.get("url"),
                    local_path=repo.get("local_path"),
                )
            )

    # Add team repos
    for repo_option in resolved_options:
        items.append(
            ListItem(
                label=repo_option.name,
                description=repo_option.description,
                value=repo_option,
            )
        )

    # Empty state hint
    if len(items) == 1:  # Only "← Back"
        subtitle = "No team repositories configured"
    else:
        subtitle = None

    result = _run_subscreen_picker(
        items=items,
        title="Team Repositories",
        subtitle=subtitle,
        standalone=standalone,
        context_label=context_label,
    )

    # Handle quit (q pressed)
    if result is None:
        return None

    # Handle BACK (Esc pressed)
    if result is BACK:
        return BACK

    # Need to clone - import here to avoid circular imports
    from .git_interactive import clone_repo

    clone_handler = clone_repo

    # Handle repo selection - check for existing local path or clone
    if isinstance(result, TeamRepoOption):
        local_path = result.local_path
        if local_path:
            expanded = Path(local_path).expanduser()
            if expanded.exists():
                return str(expanded)

        repo_url = result.url or ""
        if repo_url:
            cloned_path = clone_handler(repo_url, workspace_base)
            if cloned_path:
                return cloned_path

        # Cloning failed or no URL - return BACK to let user try again
        return BACK

    # Shouldn't happen, but handle gracefully
    return BACK
