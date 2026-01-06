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
from dataclasses import dataclass
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
from ...core.workspace import ResolverResult
from ...output_mode import print_human
from ...panels import create_info_panel, create_success_panel, create_warning_panel
from ...theme import Indicators, Spinners
from ...ui.gate import is_interactive_allowed

if TYPE_CHECKING:
    pass


@dataclass
class LaunchContext:
    """Display-focused launch context wrapping ResolverResult.

    This dataclass is used for rendering the launch panel and JSON output.
    It combines resolver results with session-specific information.
    """

    resolver_result: ResolverResult
    team: str | None
    branch: str | None
    session_name: str | None
    mode: str  # "new" or "resume"

    @property
    def workspace_root(self) -> Path:
        """Workspace root (WR)."""
        return self.resolver_result.workspace_root

    @property
    def entry_dir(self) -> Path:
        """Entry directory (ED)."""
        return self.resolver_result.entry_dir

    @property
    def mount_root(self) -> Path:
        """Mount root (MR)."""
        return self.resolver_result.mount_root

    @property
    def container_workdir(self) -> str:
        """Container working directory (CW)."""
        return self.resolver_result.container_workdir

    @property
    def entry_dir_relative(self) -> str:
        """Entry dir path relative to workspace root."""
        try:
            return str(self.entry_dir.relative_to(self.workspace_root))
        except ValueError:
            return str(self.entry_dir)

    @property
    def is_mount_expanded(self) -> bool:
        """Whether mount was expanded for worktree support."""
        return self.resolver_result.is_mount_expanded

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "workspace_root": str(self.workspace_root),
            "entry_dir": str(self.entry_dir),
            "entry_dir_relative": self.entry_dir_relative,
            "mount_root": str(self.mount_root),
            "container_workdir": self.container_workdir,
            "is_mount_expanded": self.is_mount_expanded,
            "team": self.team,
            "branch": self.branch,
            "session_name": self.session_name,
            "mode": self.mode,
            "reason": self.resolver_result.reason,
        }


def validate_and_resolve_workspace(
    workspace: str | None,
    *,
    no_interactive: bool = False,
    allow_suspicious: bool = False,
    json_mode: bool = False,
) -> Path | None:
    """
    Validate workspace path and handle platform-specific warnings.

    Args:
        workspace: Workspace path string.
        no_interactive: If True, fail fast instead of prompting.
        allow_suspicious: If True, allow suspicious workspaces in non-interactive mode.
        json_mode: If True, output is JSON (suppress Rich panels).

    Raises:
        WorkspaceNotFoundError: If workspace path doesn't exist.
        UsageError: If workspace is suspicious in non-interactive mode without --allow-suspicious-workspace.
        typer.Exit: If user declines to continue after warnings.
    """
    from ...core.errors import UsageError
    from ...services.workspace.suspicious import get_suspicious_reason, is_suspicious_directory

    if workspace is None:
        return None

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # Check for suspicious workspace (home, /tmp, system directories)
    if is_suspicious_directory(workspace_path):
        reason = get_suspicious_reason(workspace_path) or "Suspicious directory"

        # If --allow-suspicious-workspace is set, skip confirmation entirely
        if allow_suspicious:
            print_human(
                f"[yellow]Warning:[/yellow] {reason}",
                file=sys.stderr,
                highlight=False,
            )
        elif is_interactive_allowed(json_mode=json_mode, no_interactive_flag=no_interactive):
            # Interactive mode: warn but allow user to continue
            console.print()
            console.print(
                create_warning_panel(
                    "Suspicious Workspace",
                    reason,
                    "Consider using a project-specific directory instead.",
                )
            )
            console.print()
            if not Confirm.ask("[cyan]Continue anyway?[/cyan]", default=True):
                console.print("[dim]Cancelled.[/dim]")
                raise typer.Exit(EXIT_CANCELLED)
        else:
            # Non-interactive mode without flag: block
            raise UsageError(
                user_message=f"Refusing to start in suspicious directory: {workspace_path}\n  → {reason}",
                suggested_action=(
                    "Either:\n"
                    f"  • Run: scc start --allow-suspicious-workspace {workspace_path}\n"
                    "  • Run: scc start --interactive (to choose a different workspace)\n"
                    "  • Run from a project directory inside a git repository"
                ),
            )

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
    """Resolve team selection with proper priority.

    Resolution priority:
    1. Explicit --team flag (if provided)
    2. selected_profile (explicit user choice via `scc team switch`)
    3. Workspace-pinned team (auto-saved from previous session)

    In interactive mode, prompts user when pinned team differs from selected profile.
    In non-interactive mode, prefers selected_profile (explicit user action).
    """
    if standalone or workspace_path is None:
        return team

    if team:
        return team

    pinned_team = config.get_workspace_team_from_config(cfg, workspace_path)
    selected_profile: str | None = cfg.get("selected_profile")

    if pinned_team and selected_profile and pinned_team != selected_profile:
        if is_interactive_allowed(json_mode=json_mode, no_interactive_flag=no_interactive):
            # Default to selected_profile (explicit user choice) for consistency
            # with non-interactive mode behavior
            message = (
                f"[yellow]Note:[/yellow] This workspace was last used with team "
                f"'[cyan]{pinned_team}[/cyan]', but your current profile is "
                f"'[cyan]{selected_profile}[/cyan]'.\n"
                f"Use workspace's previous team '{pinned_team}' instead?"
            )
            if Confirm.ask(message, default=False):
                return pinned_team
            return selected_profile

        # Non-interactive: prefer selected_profile (explicit user choice via `scc team switch`)
        # over workspace pinning (auto-saved from previous session)
        if not json_mode:
            print_human(
                "[yellow]Notice:[/yellow] "
                f"Workspace was last used with team '{pinned_team}', "
                f"but current profile is '{selected_profile}'. Using '{selected_profile}'.",
                file=sys.stderr,
                highlight=False,
            )
        return selected_profile

    if pinned_team:
        return pinned_team

    return selected_profile


def resolve_mount_and_branch(
    workspace_path: Path | None,
    *,
    json_mode: bool = False,
) -> tuple[Path | None, str | None]:
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
    if is_expanded and not json_mode:
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
