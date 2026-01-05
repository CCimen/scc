"""
Launch render functions - pure output with no business logic.

This module contains display/rendering functions extracted from launch.py.
These are pure output functions that format and display information.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.panel import Panel
from rich.table import Table

from ... import git
from ...cli_common import MAX_DISPLAY_PATH_LENGTH, PATH_TRUNCATE_LENGTH, console
from ...output_mode import print_human
from ...theme import Indicators

if TYPE_CHECKING:
    from .workspace import LaunchContext


def warn_if_non_worktree(workspace_path: Path | None, *, json_mode: bool = False) -> None:
    """Warn when running from a main repo without a worktree.

    Args:
        workspace_path: Path to the workspace directory, or None.
        json_mode: If True, suppress the warning.
    """
    import sys

    if json_mode or workspace_path is None:
        return

    if not git.is_git_repo(workspace_path):
        return

    if git.is_worktree(workspace_path):
        return

    print_human(
        "[yellow]Tip:[/yellow] You're working in the main repo. "
        "For isolation, try: scc worktree create . <feature> or "
        "scc start --worktree <feature>",
        file=sys.stderr,
        highlight=False,
    )


def build_dry_run_data(
    workspace_path: Path,
    team: str | None,
    org_config: dict[str, Any] | None,
    project_config: dict[str, Any] | None,
    *,
    entry_dir: Path | None = None,
    mount_root: Path | None = None,
    container_workdir: str | None = None,
    resolution_reason: str | None = None,
) -> dict[str, Any]:
    """
    Build dry run data showing resolved configuration.

    This pure function assembles configuration information for preview
    without performing any side effects like Docker launch.

    Args:
        workspace_path: Path to the workspace root (WR).
        team: Selected team profile name (or None).
        org_config: Organization configuration dict (or None).
        project_config: Project-level .scc.yaml config (or None).
        entry_dir: Entry directory (ED), defaults to workspace_path if not provided.
        mount_root: Mount root (MR), defaults to workspace_path if not provided.
        container_workdir: Container workdir (CW), defaults to entry_dir if not provided.
        resolution_reason: Debug explanation for how workspace was resolved.

    Returns:
        Dictionary with resolved configuration data including path information.
    """
    plugins: list[dict[str, Any]] = []
    blocked_items: list[str] = []

    if org_config and team:
        from ... import profiles

        workspace_for_project = None if project_config is not None else workspace_path
        effective = profiles.compute_effective_config(
            org_config,
            team,
            project_config=project_config,
            workspace_path=workspace_for_project,
        )

        for plugin in sorted(effective.plugins):
            plugins.append({"name": plugin, "source": "resolved"})

        for blocked in effective.blocked_items:
            if blocked.blocked_by:
                blocked_items.append(f"{blocked.item} (blocked by '{blocked.blocked_by}')")
            else:
                blocked_items.append(blocked.item)

    # Compute defaults for optional path fields
    effective_entry = entry_dir if entry_dir is not None else workspace_path
    effective_mount = mount_root if mount_root is not None else workspace_path
    effective_cw = container_workdir if container_workdir is not None else str(effective_entry)

    return {
        "workspace_root": str(workspace_path),
        "entry_dir": str(effective_entry),
        "mount_root": str(effective_mount),
        "container_workdir": effective_cw,
        "team": team,
        "plugins": plugins,
        "blocked_items": blocked_items,
        "ready_to_start": len(blocked_items) == 0,
        "resolution_reason": resolution_reason,
    }


def show_launch_panel(
    workspace: Path | None,
    team: str | None,
    session_name: str | None,
    branch: str | None,
    is_resume: bool,
) -> None:
    """Display launch info panel with session details.

    Args:
        workspace: Path to the workspace directory, or None.
        team: Team profile name, or None for base profile.
        session_name: Optional session name for identification.
        branch: Current git branch, or None if not in a git repo.
        is_resume: True if resuming an existing container.
    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    if workspace:
        # Shorten path for display
        display_path = str(workspace)
        if len(display_path) > MAX_DISPLAY_PATH_LENGTH:
            display_path = "..." + display_path[-PATH_TRUNCATE_LENGTH:]
        grid.add_row("Workspace:", display_path)

    grid.add_row("Team:", team or "standalone")

    if branch:
        grid.add_row("Branch:", branch)

    if session_name:
        grid.add_row("Session:", session_name)

    mode = "[green]Resume existing[/green]" if is_resume else "[cyan]New container[/cyan]"
    grid.add_row("Mode:", mode)

    panel = Panel(
        grid,
        title="[bold green]Launching Claude Code[/bold green]",
        border_style="green",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()
    console.print("[dim]Starting Docker sandbox...[/dim]")
    console.print()


def show_dry_run_panel(data: dict[str, Any]) -> None:
    """Display dry run configuration preview.

    Args:
        data: Dictionary containing workspace paths, team, plugins, and ready_to_start status.
    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    # Workspace root (WR)
    workspace_root = data.get("workspace_root", data.get("workspace", ""))
    if len(workspace_root) > MAX_DISPLAY_PATH_LENGTH:
        workspace_root = "..." + workspace_root[-PATH_TRUNCATE_LENGTH:]
    grid.add_row("Workspace root:", workspace_root)

    # Entry dir (ED) - only show if different from workspace_root
    entry_dir = data.get("entry_dir", "")
    if entry_dir and entry_dir != data.get("workspace_root"):
        if len(entry_dir) > MAX_DISPLAY_PATH_LENGTH:
            entry_dir = "..." + entry_dir[-PATH_TRUNCATE_LENGTH:]
        grid.add_row("Entry dir:", entry_dir)

    # Mount root (MR) - only show if different (worktree expansion)
    mount_root = data.get("mount_root", "")
    if mount_root and mount_root != data.get("workspace_root"):
        if len(mount_root) > MAX_DISPLAY_PATH_LENGTH:
            mount_root = "..." + mount_root[-PATH_TRUNCATE_LENGTH:]
        grid.add_row("Mount root:", f"{mount_root} [dim](worktree)[/dim]")

    # Container workdir (CW)
    container_workdir = data.get("container_workdir", "")
    if container_workdir:
        if len(container_workdir) > MAX_DISPLAY_PATH_LENGTH:
            container_workdir = "..." + container_workdir[-PATH_TRUNCATE_LENGTH:]
        grid.add_row("Container cwd:", container_workdir)

    # Team
    grid.add_row("Team:", data.get("team") or "standalone")

    # Plugins
    plugins = data.get("plugins", [])
    if plugins:
        plugin_list = ", ".join(p.get("name", "unknown") for p in plugins)
        grid.add_row("Plugins:", plugin_list)
    else:
        grid.add_row("Plugins:", "[dim]none[/dim]")

    # Ready status
    ready = data.get("ready_to_start", True)
    status = (
        f"[green]{Indicators.get('PASS')} Ready to start[/green]"
        if ready
        else f"[red]{Indicators.get('FAIL')} Blocked[/red]"
    )
    grid.add_row("Status:", status)

    # Blocked items
    blocked = data.get("blocked_items", [])
    if blocked:
        for item in blocked:
            grid.add_row("[red]Blocked:[/red]", item)

    panel = Panel(
        grid,
        title="[bold cyan]Dry Run Preview[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()
    if ready:
        console.print("[dim]Remove --dry-run to launch[/dim]")
    console.print()


def show_launch_context_panel(ctx: LaunchContext) -> None:
    """Display enhanced launch context panel with path information.

    Shows:
    - Workspace root (WR)
    - Entry dir (ED) with relative path if different from WR
    - Mount root (MR) only if different from WR (worktree expansion)
    - Container workdir (CW)
    - Team / branch / session / mode
    """
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    # Workspace root (WR)
    grid.add_row("Workspace:", str(ctx.workspace_root))

    # Entry dir (ED) - show relative if different from WR
    if ctx.entry_dir != ctx.workspace_root:
        rel = ctx.entry_dir_relative
        if rel != ".":
            grid.add_row("Entry dir:", f"{rel} [dim](relative)[/dim]")

    # Mount root (MR) - only show if different (worktree expansion)
    if ctx.mount_root != ctx.workspace_root:
        grid.add_row("Mount root:", f"{ctx.mount_root} [dim](expanded for worktree)[/dim]")

    # Container workdir (CW)
    grid.add_row("Container cwd:", ctx.container_workdir)

    # Team
    grid.add_row("Team:", ctx.team or "standalone")

    # Branch
    if ctx.branch:
        grid.add_row("Branch:", ctx.branch)

    # Session
    if ctx.session_name:
        grid.add_row("Session:", ctx.session_name)

    # Mode
    mode_display = (
        "[green]Resume existing[/green]" if ctx.mode == "resume" else "[cyan]New container[/cyan]"
    )
    grid.add_row("Mode:", mode_display)

    panel = Panel(
        grid,
        title="[bold green]Launching Claude Code[/bold green]",
        border_style="green",
        padding=(0, 1),
    )

    console.print()
    console.print(panel)
    console.print()
