"""Picker functions for the start wizard.

Extracted from wizard.py: workspace source option builders and
sub-screen pickers (pick_workspace_source, pick_recent_workspace,
pick_team_repo).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from scc_cli.application.launch.start_wizard import (
    TeamRepoOption,
    WorkspaceSource,
    WorkspaceSourceOption,
    WorkspaceSourceViewModel,
    WorkspaceSummary,
)

from ..services.workspace import has_project_markers
from .keys import BACK, _BackSentinel
from .list_screen import ListItem

if TYPE_CHECKING:
    from ..ports.session_models import SessionSummary

T = TypeVar("T")


def _get_picker() -> Any:
    """Late-bound lookup of _run_single_select_picker through wizard module.

    Tests patch scc_cli.ui.wizard._run_single_select_picker, so we must
    resolve through that module at call time for the mock to take effect.
    """
    from . import wizard as _wizard_mod

    return _wizard_mod._run_single_select_picker


# ═══════════════════════════════════════════════════════════════════════════════
# Workspace Source Option Builders
# ═══════════════════════════════════════════════════════════════════════════════


def build_workspace_source_options(
    *,
    has_team_repos: bool,
    include_current_dir: bool = True,
) -> list[WorkspaceSourceOption]:
    options: list[WorkspaceSourceOption] = []

    if include_current_dir:
        from scc_cli.services import git as git_service

        cwd = Path.cwd()
        cwd_name = cwd.name or str(cwd)
        is_git = git_service.is_git_repo(cwd)

        from ..services.workspace import is_suspicious_directory

        if not is_suspicious_directory(cwd):
            if has_project_markers(cwd):
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

    if view_model.cwd_context is not None:
        ctx = view_model.cwd_context
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

    options.append(
        WorkspaceSourceOption(
            source=WorkspaceSource.RECENT,
            label="• Recent workspaces",
            description="Continue working on previous project",
        )
    )

    if view_model.has_team_repos:
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
    """Run picker for sub-screens with three-state return contract."""
    result: T | _BackSentinel | None = _get_picker()(
        items,
        title=title,
        subtitle=subtitle,
        standalone=standalone,
        allow_back=True,
        context_label=context_label,
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Top-Level Picker: Workspace Source
# ═══════════════════════════════════════════════════════════════════════════════


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
    """
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

    items: list[ListItem[WorkspaceSource]] = []

    source_options = options
    if not source_options:
        if view_model is not None:
            source_options = build_workspace_source_options_from_view_model(view_model)
        else:
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
        result = _get_picker()(
            items=items,
            title="Where is your project?",
            subtitle=resolved_subtitle,
            standalone=standalone,
            allow_back=True,
            context_label=resolved_context_label,
        )
    else:
        result = _get_picker()(
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
    """Show picker for recent workspace selection."""
    from .wizard import _format_relative_time, _normalize_path

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

    for summary in summaries:
        items.append(
            ListItem(
                label=summary.label,
                description=summary.description,
                value=summary.workspace,
            )
        )

    if len(items) == 1:
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
# Sub-Screen Picker: Team Repositories
# ═══════════════════════════════════════════════════════════════════════════════


def pick_team_repo(
    repos: list[dict[str, Any]],
    workspace_base: str = "~/projects",
    *,
    standalone: bool = False,
    context_label: str | None = None,
    options: list[TeamRepoOption] | None = None,
) -> str | _BackSentinel | None:
    """Show picker for team repository selection."""
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

    for repo_option in resolved_options:
        items.append(
            ListItem(
                label=repo_option.name,
                description=repo_option.description,
                value=repo_option,
            )
        )

    if len(items) == 1:
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

    if result is None:
        return None
    if result is BACK:
        return BACK

    from .git_interactive import clone_repo

    clone_handler = clone_repo

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

        return BACK

    return BACK
