"""
Workspace validation and preparation functions.

This module handles workspace-related operations for the launch command:
- Path validation and resolution
- Worktree creation and mounting
- Dependency installation
- Team-workspace association resolution
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.status import Status

from ... import config, deps, git
from ... import platform as platform_module
from ...cli_common import console
from ...confirm import Confirm
from ...core.constants import WORKTREE_BRANCH_PREFIX
from ...core.errors import NotAGitRepoError, WorkspaceNotFoundError
from ...core.exit_codes import EXIT_CANCELLED
from ...output_mode import print_human
from ...panels import create_info_panel, create_success_panel, create_warning_panel
from ...theme import Indicators, Spinners
from ...ui.gate import is_interactive_allowed

if TYPE_CHECKING:
    pass


def validate_and_resolve_workspace(
    workspace: str | None, *, no_interactive: bool = False
) -> Path | None:
    """
    Validate workspace path and handle platform-specific warnings.

    Raises:
        WorkspaceNotFoundError: If workspace path doesn't exist.
        typer.Exit: If user declines to continue after WSL2 warning.
    """
    if workspace is None:
        return None

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # WSL2 performance warning
    if platform_module.is_wsl2():
        is_optimal, warning = platform_module.check_path_performance(workspace_path)
        if not is_optimal and warning:
            print_human(
                "[yellow]Warning:[/yellow] Workspace is on the Windows filesystem."
                " Performance may be slow.",
                file=sys.stderr,
                highlight=False,
            )
            if is_interactive_allowed(no_interactive_flag=no_interactive):
                console.print()
                console.print(
                    create_warning_panel(
                        "Performance Warning",
                        "Your workspace is on the Windows filesystem.",
                        "For better performance, move to ~/projects inside WSL.",
                    )
                )
                console.print()
                if not Confirm.ask("[cyan]Continue anyway?[/cyan]", default=True):
                    console.print("[dim]Cancelled.[/dim]")
                    raise typer.Exit(EXIT_CANCELLED)

    return workspace_path


def prepare_workspace(
    workspace_path: Path | None,
    worktree_name: str | None,
    install_deps: bool,
) -> Path | None:
    """
    Prepare workspace: create worktree, install deps, check git safety.

    Returns:
        The (possibly updated) workspace path after worktree creation.
    """
    if workspace_path is None:
        return None

    # Handle worktree creation
    if worktree_name:
        workspace_path = git.create_worktree(workspace_path, worktree_name)
        console.print(
            create_success_panel(
                "Worktree Created",
                {
                    "Path": str(workspace_path),
                    "Branch": f"{WORKTREE_BRANCH_PREFIX}{worktree_name}",
                },
            )
        )

    # Install dependencies if requested
    if install_deps:
        with Status(
            "[cyan]Installing dependencies...[/cyan]", console=console, spinner=Spinners.SETUP
        ):
            success = deps.auto_install_dependencies(workspace_path)
        if success:
            console.print(f"[green]{Indicators.get('PASS')} Dependencies installed[/green]")
        else:
            console.print("[yellow]⚠ Could not detect package manager or install failed[/yellow]")

    # Check git safety (handles protected branch warnings)
    if workspace_path.exists():
        if not git.check_branch_safety(workspace_path, console):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(EXIT_CANCELLED)

    return workspace_path


def resolve_workspace_team(
    workspace_path: Path | None,
    team: str | None,
    cfg: dict[str, Any],
    *,
    json_mode: bool = False,
    standalone: bool = False,
    no_interactive: bool = False,
) -> str | None:
    """Resolve team selection using workspace pinning when available.

    Prefers explicit team, then workspace-pinned team, then global selected profile.
    Prompts if pinned team differs from the global profile in interactive mode.
    """
    if standalone or workspace_path is None:
        return team

    if team:
        return team

    pinned_team = config.get_workspace_team_from_config(cfg, workspace_path)
    selected_profile: str | None = cfg.get("selected_profile")

    if pinned_team and selected_profile and pinned_team != selected_profile:
        if is_interactive_allowed(json_mode=json_mode, no_interactive_flag=no_interactive):
            message = (
                f"Workspace '{workspace_path}' was last used with team '{pinned_team}'."
                " Use that team for this session?"
            )
            if Confirm.ask(message, default=True):
                return pinned_team
            return selected_profile

        if not json_mode:
            print_human(
                "[yellow]Notice:[/yellow] "
                f"Workspace '{workspace_path}' was last used with team '{pinned_team}'. "
                "Using it. Pass --team to override.",
                file=sys.stderr,
                highlight=False,
            )
        return pinned_team

    if pinned_team:
        return pinned_team

    return selected_profile


def resolve_mount_and_branch(workspace_path: Path | None) -> tuple[Path | None, str | None]:
    """
    Resolve mount path for worktrees and get current branch.

    For worktrees, expands mount scope to include main repo.
    Returns (mount_path, current_branch).
    """
    if workspace_path is None:
        return None, None

    # Get current branch
    current_branch = None
    try:
        current_branch = git.get_current_branch(workspace_path)
    except (NotAGitRepoError, OSError):
        pass

    # Handle worktree mounting
    mount_path, is_expanded = git.get_workspace_mount_path(workspace_path)
    if is_expanded:
        console.print()
        console.print(
            create_info_panel(
                "Worktree Detected",
                f"Mounting parent directory for worktree support:\n{mount_path}",
                "Both worktree and main repo will be accessible",
            )
        )
        console.print()

    return mount_path, current_branch
