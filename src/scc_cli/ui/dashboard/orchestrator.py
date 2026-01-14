"""Orchestration functions for the dashboard module.

This module contains the entry point and flow handlers:
- run_dashboard: Main entry point for `scc` with no arguments
- _handle_team_switch: Team picker integration
- _handle_start_flow: Start wizard integration
- _handle_session_resume: Session resume logic

The orchestrator manages the dashboard lifecycle including intent exceptions
that exit the Rich Live context before handling nested UI components.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...console import get_err_console

if TYPE_CHECKING:
    from rich.console import Console

from ...confirm import Confirm
from ..keys import (
    ContainerActionMenuRequested,
    ContainerRemoveRequested,
    ContainerResumeRequested,
    ContainerStopRequested,
    CreateWorktreeRequested,
    GitInitRequested,
    ProfileMenuRequested,
    RecentWorkspacesRequested,
    RefreshRequested,
    SandboxImportRequested,
    SessionActionMenuRequested,
    SessionResumeRequested,
    SettingsRequested,
    StartRequested,
    StatuslineInstallRequested,
    TeamSwitchRequested,
    VerboseToggleRequested,
    WorktreeActionMenuRequested,
)
from ..list_screen import ListState
from ._dashboard import Dashboard
from .loaders import _load_all_tab_data
from .models import DashboardState, DashboardTab


def run_dashboard() -> None:
    """Run the main SCC dashboard.

    This is the entry point for `scc` with no arguments in a TTY.
    It loads current resource data and displays the interactive dashboard.

    Handles intent exceptions by executing the requested flow outside the
    Rich Live context (critical to avoid nested Live conflicts), then
    reloading the dashboard with restored tab state.

    Intent Exceptions:
        - TeamSwitchRequested: Show team picker, reload with new team
        - StartRequested: Run start wizard, return to source tab with fresh data
        - RefreshRequested: Reload tab data, return to source tab
        - VerboseToggleRequested: Toggle verbose worktree status display
    """
    from ... import config as scc_config

    # Show one-time onboarding banner for new users
    if not scc_config.has_seen_onboarding():
        _show_onboarding_banner()
        scc_config.mark_onboarding_seen()

    # Track which tab to restore after flow (uses .name for stability)
    restore_tab: str | None = None
    # Toast message to show on next dashboard iteration (e.g., "Start cancelled")
    toast_message: str | None = None
    # Track verbose worktree status display (persists across reloads)
    verbose_worktrees: bool = False

    while True:
        # Load real data for all tabs (pass verbose flag for worktrees)
        tabs = _load_all_tab_data(verbose_worktrees=verbose_worktrees)

        # Determine initial tab (restore previous or default to STATUS)
        initial_tab = DashboardTab.STATUS
        if restore_tab:
            # Find tab by name (stable identifier)
            for tab in DashboardTab:
                if tab.name == restore_tab:
                    initial_tab = tab
                    break
            restore_tab = None  # Clear after use

        state = DashboardState(
            active_tab=initial_tab,
            tabs=tabs,
            list_state=ListState(items=tabs[initial_tab].items),
            status_message=toast_message,  # Show any pending toast
            verbose_worktrees=verbose_worktrees,  # Preserve verbose state
        )
        toast_message = None  # Clear after use

        dashboard = Dashboard(state)
        try:
            dashboard.run()
            break  # Normal exit (q or Esc)
        except TeamSwitchRequested:
            # User pressed 't' - show team picker then reload dashboard
            _handle_team_switch()
            # Loop continues to reload dashboard with new team

        except StartRequested as start_req:
            # User pressed Enter on startable placeholder
            # Execute start flow OUTSIDE Rich Live (critical: avoids nested Live)
            restore_tab = start_req.return_to
            result = _handle_start_flow(start_req.reason)

            if result is None:
                # User pressed q: quit app entirely
                break

            if result is False:
                # User pressed Esc: go back to dashboard, show toast
                toast_message = "Start cancelled"
            # Loop continues to reload dashboard with fresh data

        except RefreshRequested as refresh_req:
            # User pressed 'r' - just reload data
            restore_tab = refresh_req.return_to
            # Loop continues with fresh data (no additional action needed)

        except SessionResumeRequested as resume_req:
            # User pressed Enter on a session item → resume it
            restore_tab = resume_req.return_to
            success = _handle_session_resume(resume_req.session)

            if not success:
                # Resume failed (e.g., missing workspace) - show toast
                toast_message = "Session resume failed"
            else:
                # Successfully launched - exit dashboard
                # (container is running, user is now in Claude)
                break

        except StatuslineInstallRequested as statusline_req:
            # User pressed 'y' on statusline row - install statusline
            restore_tab = statusline_req.return_to
            success = _handle_statusline_install()

            if success:
                toast_message = "Statusline installed successfully"
            else:
                toast_message = "Statusline installation failed"
            # Loop continues to reload dashboard with fresh data

        except RecentWorkspacesRequested as recent_req:
            # User pressed 'w' - show recent workspaces picker
            restore_tab = recent_req.return_to
            selected_workspace = _handle_recent_workspaces()

            if selected_workspace is None:
                # User cancelled or quit
                toast_message = "Cancelled"
            elif selected_workspace:
                # User selected a workspace - start session in it
                # For now, just show message; full integration comes later
                toast_message = f"Selected: {selected_workspace}"
            # Loop continues to reload dashboard

        except GitInitRequested as init_req:
            # User pressed 'i' - initialize git repo
            restore_tab = init_req.return_to
            success = _handle_git_init()

            if success:
                toast_message = "Git repository initialized"
            else:
                toast_message = "Git init cancelled or failed"
            # Loop continues to reload dashboard

        except CreateWorktreeRequested as create_req:
            # User pressed 'c' - create worktree or clone
            restore_tab = create_req.return_to

            if create_req.is_git_repo:
                success = _handle_create_worktree()
                if success:
                    toast_message = "Worktree created"
                else:
                    toast_message = "Worktree creation cancelled"
            else:
                success = _handle_clone()
                if success:
                    toast_message = "Repository cloned"
                else:
                    toast_message = "Clone cancelled"
            # Loop continues to reload dashboard

        except VerboseToggleRequested as verbose_req:
            # User pressed 'v' - toggle verbose worktree status
            restore_tab = verbose_req.return_to
            verbose_worktrees = verbose_req.verbose
            toast_message = "Status on" if verbose_worktrees else "Status off"
            # Loop continues with new verbose setting

        except SettingsRequested as settings_req:
            # User pressed 's' - open settings and maintenance screen
            restore_tab = settings_req.return_to
            settings_result = _handle_settings()

            if settings_result:
                toast_message = settings_result  # Success message from settings action
            # Loop continues to reload dashboard

        except ContainerStopRequested as container_req:
            restore_tab = container_req.return_to
            success, message = _handle_container_stop(
                container_req.container_id,
                container_req.container_name,
            )
            toast_message = (
                message if message else ("Container stopped" if success else "Stop failed")
            )

        except ContainerResumeRequested as container_req:
            restore_tab = container_req.return_to
            success, message = _handle_container_resume(
                container_req.container_id,
                container_req.container_name,
            )
            toast_message = (
                message if message else ("Container resumed" if success else "Resume failed")
            )

        except ContainerRemoveRequested as container_req:
            restore_tab = container_req.return_to
            success, message = _handle_container_remove(
                container_req.container_id,
                container_req.container_name,
            )
            toast_message = (
                message if message else ("Container removed" if success else "Remove failed")
            )

        except ProfileMenuRequested as profile_req:
            # User pressed 'p' - show profile quick menu
            restore_tab = profile_req.return_to
            profile_result = _handle_profile_menu()

            if profile_result:
                toast_message = profile_result  # Success message from profile action

        except SandboxImportRequested as import_req:
            # User pressed 'i' - import sandbox plugins
            restore_tab = import_req.return_to
            import_result = _handle_sandbox_import()

            if import_result:
                toast_message = import_result  # Success message from import

        except ContainerActionMenuRequested as action_req:
            # User triggered container action menu (Enter or Space on container)
            restore_tab = action_req.return_to
            action_result = _handle_container_action_menu(
                action_req.container_id, action_req.container_name
            )

            if action_result:
                toast_message = action_result

        except SessionActionMenuRequested as action_req:
            # User triggered session action menu (Enter or Space on session)
            restore_tab = action_req.return_to
            action_result = _handle_session_action_menu(action_req.session)

            if action_result:
                toast_message = action_result

        except WorktreeActionMenuRequested as action_req:
            # User triggered worktree action menu (Enter or Space on worktree)
            restore_tab = action_req.return_to
            action_result = _handle_worktree_action_menu(action_req.worktree_path)

            if action_result:
                toast_message = action_result


def _prepare_for_nested_ui(console: Console) -> None:
    """Prepare terminal state for launching nested UI components.

    Restores cursor visibility, ensures clean newline, and flushes
    any buffered input to prevent ghost keypresses from Rich Live context.

    This should be called before launching any interactive picker or wizard
    from the dashboard to ensure clean terminal state.

    Args:
        console: Rich Console instance for terminal operations.
    """
    import io
    import sys

    # Restore cursor (Rich Live may hide it)
    console.show_cursor(True)
    console.print()  # Ensure clean newline

    # Flush buffered input (best-effort, Unix only)
    try:
        import termios

        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (
        ModuleNotFoundError,  # Windows - no termios module
        OSError,  # Redirected stdin, no TTY
        ValueError,  # Invalid file descriptor
        TypeError,  # Mock stdin without fileno
        io.UnsupportedOperation,  # Stdin without fileno support
    ):
        pass  # Non-Unix or non-TTY environment - safe to ignore


def _handle_team_switch() -> None:
    """Handle team switch request from dashboard.

    Shows the team picker and switches team if user selects one.
    """
    from ... import config, teams
    from ..picker import pick_team

    console = get_err_console()
    _prepare_for_nested_ui(console)

    try:
        # Load config and org config for team list
        cfg = config.load_user_config()
        org_config = config.load_cached_org_config()

        available_teams = teams.list_teams(cfg, org_config=org_config)
        if not available_teams:
            console.print("[yellow]No teams available[/yellow]")
            return

        # Get current team for marking
        current_team = cfg.get("selected_profile")

        selected = pick_team(
            available_teams,
            current_team=str(current_team) if current_team else None,
            title="Switch Team",
        )

        if selected:
            # Update team selection
            team_name = selected.get("name", "")
            cfg["selected_profile"] = team_name
            config.save_user_config(cfg)
            console.print(f"[green]Switched to team: {team_name}[/green]")
        # If cancelled, just return to dashboard

    except TeamSwitchRequested:
        # Nested team switch (shouldn't happen, but handle gracefully)
        pass
    except Exception as e:
        console.print(f"[red]Error switching team: {e}[/red]")


def _handle_start_flow(reason: str) -> bool | None:
    """Handle start flow request from dashboard.

    Runs the interactive start wizard and launches a sandbox if user completes it.
    Executes OUTSIDE Rich Live context (the dashboard has already exited
    via the exception unwind before this is called).

    Three-state return contract:
    - True: Sandbox launched successfully
    - False: User pressed Esc (back to dashboard)
    - None: User pressed q (quit app entirely)

    Args:
        reason: Why the start flow was triggered. Can be:
            - "no_containers", "no_sessions": Empty state triggers (show wizard)
            - "worktree:/path/to/worktree": Start session in specific worktree

    Returns:
        True if wizard completed successfully, False if user wants to go back,
        None if user wants to quit entirely.
    """
    from ...commands.launch import run_start_wizard_flow

    console = get_err_console()
    _prepare_for_nested_ui(console)

    # Handle worktree-specific start (Enter on worktree in details pane)
    if reason.startswith("worktree:"):
        worktree_path = reason[9:]  # Remove "worktree:" prefix
        return _handle_worktree_start(worktree_path)

    # For empty-state starts, skip Quick Resume (user intent is "create new")
    skip_quick_resume = reason in ("no_containers", "no_sessions")

    # Show contextual message based on reason
    if reason == "no_containers":
        console.print("[dim]Starting a new session...[/dim]")
    elif reason == "no_sessions":
        console.print("[dim]Starting your first session...[/dim]")
    console.print()

    # Run the wizard with allow_back=True for dashboard context
    # Returns: True (success), False (Esc/back), None (q/quit)
    return run_start_wizard_flow(skip_quick_resume=skip_quick_resume, allow_back=True)


def _handle_worktree_start(worktree_path: str) -> bool | None:
    """Handle starting a session in a specific worktree.

    Launches a new session directly in the selected worktree, bypassing
    the wizard workspace selection since the user already selected a worktree.

    Args:
        worktree_path: Absolute path to the worktree directory.

    Returns:
        True if session started successfully, False if cancelled,
        None if user wants to quit entirely.
    """
    from pathlib import Path

    from rich.status import Status

    from ... import config, docker
    from ...commands.launch import (
        _configure_team_settings,
        _launch_sandbox,
        _resolve_mount_and_branch,
        _sync_marketplace_settings,
        _validate_and_resolve_workspace,
    )
    from ...theme import Spinners

    console = get_err_console()

    workspace_path = Path(worktree_path)
    workspace_name = workspace_path.name

    # Validate workspace exists
    if not workspace_path.exists():
        console.print(f"[red]Worktree no longer exists: {worktree_path}[/red]")
        return False

    console.print(f"[cyan]Starting session in:[/cyan] {workspace_name}")
    console.print()

    try:
        # Docker availability check
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            docker.check_docker_available()

        # Validate and resolve workspace
        resolved_path = _validate_and_resolve_workspace(str(workspace_path))
        if resolved_path is None:
            console.print("[red]Workspace validation failed[/red]")
            return False
        workspace_path = resolved_path

        # Get current team from config
        cfg = config.load_config()
        team = cfg.get("selected_profile")
        _configure_team_settings(team, cfg)

        # Sync marketplace settings
        sync_result = _sync_marketplace_settings(workspace_path, team)
        plugin_settings = sync_result.rendered_settings if sync_result else None

        # Resolve mount path and branch
        mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

        # Show session info
        if team:
            console.print(f"[dim]Team: {team}[/dim]")
        if current_branch:
            console.print(f"[dim]Branch: {current_branch}[/dim]")
        console.print()

        # Launch sandbox
        _launch_sandbox(
            workspace_path=workspace_path,
            mount_path=mount_path,
            team=team,
            session_name=None,  # No specific session name
            current_branch=current_branch,
            should_continue_session=False,
            fresh=False,
            plugin_settings=plugin_settings,
        )
        return True

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        return False
    except Exception as e:
        console.print(f"[red]Error starting session: {e}[/red]")
        return False


def _handle_session_resume(session: dict[str, Any]) -> bool:
    """Handle session resume request from dashboard.

    Resumes an existing session by launching the Docker container with
    the stored workspace, team, and branch configuration.

    This function executes OUTSIDE Rich Live context (the dashboard has
    already exited via the exception unwind before this is called).

    Args:
        session: Session dict containing workspace, team, branch, container_name, etc.

    Returns:
        True if session was resumed successfully, False if resume failed
        (e.g., workspace no longer exists).
    """
    from pathlib import Path

    from rich.status import Status

    from ... import config, docker
    from ...commands.launch import (
        _configure_team_settings,
        _launch_sandbox,
        _resolve_mount_and_branch,
        _sync_marketplace_settings,
        _validate_and_resolve_workspace,
    )
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    # Extract session info
    workspace = session.get("workspace", "")
    team = session.get("team")  # May be None for standalone
    session_name = session.get("name")
    branch = session.get("branch")

    if not workspace:
        console.print("[red]Session has no workspace path[/red]")
        return False

    # Validate workspace still exists
    workspace_path = Path(workspace)
    if not workspace_path.exists():
        console.print(f"[red]Workspace no longer exists: {workspace}[/red]")
        console.print("[dim]The session may have been deleted or moved.[/dim]")
        return False

    try:
        # Docker availability check
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            docker.check_docker_available()

        # Validate and resolve workspace (we know it exists from earlier check)
        resolved_path = _validate_and_resolve_workspace(str(workspace_path))
        if resolved_path is None:
            console.print("[red]Workspace validation failed[/red]")
            return False
        workspace_path = resolved_path

        # Configure team settings
        cfg = config.load_config()
        _configure_team_settings(team, cfg)

        # Sync marketplace settings
        sync_result = _sync_marketplace_settings(workspace_path, team)
        plugin_settings = sync_result.rendered_settings if sync_result else None

        # Resolve mount path and branch
        mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

        # Use session's stored branch if available (more accurate than detected)
        if branch:
            current_branch = branch

        # Show resume info
        workspace_name = workspace_path.name
        console.print(f"[cyan]Resuming session:[/cyan] {workspace_name}")
        if team:
            console.print(f"[dim]Team: {team}[/dim]")
        if current_branch:
            console.print(f"[dim]Branch: {current_branch}[/dim]")
        console.print()

        # Launch sandbox with resume flag
        _launch_sandbox(
            workspace_path=workspace_path,
            mount_path=mount_path,
            team=team,
            session_name=session_name,
            current_branch=current_branch,
            should_continue_session=True,  # Resume existing container
            fresh=False,
            plugin_settings=plugin_settings,
        )
        return True

    except Exception as e:
        console.print(f"[red]Error resuming session: {e}[/red]")
        return False


def _handle_statusline_install() -> bool:
    """Handle statusline installation request from dashboard.

    Installs the Claude Code statusline enhancement using the same logic
    as `scc statusline`. Works cross-platform (Windows, macOS, Linux).

    Returns:
        True if statusline was installed successfully, False otherwise.
    """
    from rich.status import Status

    from ...commands.admin import install_statusline
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    console.print("[cyan]Installing statusline...[/cyan]")
    console.print()

    try:
        with Status(
            "[cyan]Configuring statusline...[/cyan]",
            console=console,
            spinner=Spinners.DOCKER,
        ):
            result = install_statusline()

        if result:
            console.print("[green]✓ Statusline installed successfully![/green]")
            console.print("[dim]Press any key to continue...[/dim]")
        else:
            console.print("[yellow]Statusline installation completed with warnings[/yellow]")

        return result

    except Exception as e:
        console.print(f"[red]Error installing statusline: {e}[/red]")
        return False


def _handle_recent_workspaces() -> str | None:
    """Handle recent workspaces picker from dashboard.

    Shows a picker with recently used workspaces, allowing the user to
    quickly navigate to a previous project.

    Returns:
        Path of selected workspace, or None if cancelled.
    """
    from ...contexts import load_recent_contexts
    from ..picker import pick_context

    console = get_err_console()
    _prepare_for_nested_ui(console)

    try:
        recent = load_recent_contexts()
        if not recent:
            console.print("[yellow]No recent workspaces found[/yellow]")
            console.print(
                "[dim]Start a session with `scc start <path>` to populate this list.[/dim]"
            )
            return None

        selected = pick_context(
            recent,
            title="Recent Workspaces",
            subtitle="Select a workspace",
        )

        if selected:
            return str(selected.worktree_path)
        return None

    except Exception as e:
        console.print(f"[red]Error loading recent workspaces: {e}[/red]")
        return None


def _handle_git_init() -> bool:
    """Handle git init request from dashboard.

    Initializes a new git repository in the current directory,
    optionally creating an initial commit.

    Returns:
        True if git was initialized successfully, False otherwise.
    """
    import os
    import subprocess

    console = get_err_console()
    _prepare_for_nested_ui(console)

    cwd = os.getcwd()
    console.print(f"[cyan]Initializing git repository in:[/cyan] {cwd}")
    console.print()

    try:
        # Run git init
        result = subprocess.run(
            ["git", "init"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        console.print(f"[green]✓ {result.stdout.strip()}[/green]")

        # Optionally create initial commit
        console.print()
        console.print("[dim]Creating initial empty commit...[/dim]")

        # Try to create an empty commit
        try:
            subprocess.run(
                ["git", "commit", "--allow-empty", "-m", "Initial commit"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True,
            )
            console.print("[green]✓ Initial commit created[/green]")
        except subprocess.CalledProcessError as e:
            # May fail if git identity not configured
            if "user.email" in e.stderr or "user.name" in e.stderr:
                console.print("[yellow]Tip: Configure git identity to enable commits:[/yellow]")
                console.print("  git config user.name 'Your Name'")
                console.print("  git config user.email 'your@email.com'")
            else:
                console.print(
                    f"[yellow]Could not create initial commit: {e.stderr.strip()}[/yellow]"
                )

        console.print()
        console.print("[dim]Press any key to continue...[/dim]")
        return True

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Git init failed: {e.stderr.strip()}[/red]")
        return False
    except FileNotFoundError:
        console.print("[red]Git is not installed or not in PATH[/red]")
        return False


def _handle_create_worktree() -> bool:
    """Handle create worktree request from dashboard.

    Prompts for a worktree name and creates a new git worktree.

    Returns:
        True if worktree was created successfully, False otherwise.
    """
    console = get_err_console()
    _prepare_for_nested_ui(console)

    console.print("[cyan]Create new worktree[/cyan]")
    console.print()
    console.print("[dim]Use `scc worktree create <name>` from the terminal for full options.[/dim]")
    console.print("[dim]Press any key to continue...[/dim]")

    # For now, just inform user of CLI option
    # Full interactive creation can be added in a future phase
    return False


def _handle_clone() -> bool:
    """Handle clone request from dashboard.

    Informs user how to clone a repository.

    Returns:
        True if clone was successful, False otherwise.
    """
    console = get_err_console()
    _prepare_for_nested_ui(console)

    console.print("[cyan]Clone a repository[/cyan]")
    console.print()
    console.print("[dim]Use `git clone <url>` to clone a repository, then run `scc` in it.[/dim]")
    console.print("[dim]Press any key to continue...[/dim]")

    # For now, just inform user of git clone option
    # Full interactive clone can be added in a future phase
    return False


def _handle_container_stop(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Stop a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up") is False:
        return True, f"Already stopped: {container_name}"

    with Status(
        f"[cyan]Stopping {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.stop_container(container_id)

    return success, (f"Stopped {container_name}" if success else f"Failed to stop {container_name}")


def _handle_container_resume(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Resume a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return True, f"Already running: {container_name}"

    with Status(
        f"[cyan]Starting {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.resume_container(container_id)

    return success, (
        f"Resumed {container_name}" if success else f"Failed to resume {container_name}"
    )


def _handle_container_remove(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Remove a stopped container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return False, f"Stop {container_name} before deleting"

    with Status(
        f"[cyan]Removing {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.remove_container(container_name or container_id)

    return success, (
        f"Removed {container_name}" if success else f"Failed to remove {container_name}"
    )


def _handle_container_action_menu(container_id: str, container_name: str) -> str | None:
    """Show a container actions menu and execute the selected action."""
    import subprocess

    from ... import docker
    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name) or ""
    is_running = status.startswith("Up")

    items: list[ListItem[str]] = []

    if is_running:
        items.append(
            ListItem(
                value="attach_shell",
                label="Attach shell",
                description="docker exec -it <container> bash",
            )
        )
        items.append(
            ListItem(
                value="stop",
                label="Stop container",
                description="Stop running container",
            )
        )
    else:
        items.append(
            ListItem(
                value="resume",
                label="Resume container",
                description="Start stopped container",
            )
        )
        items.append(
            ListItem(
                value="delete",
                label="Delete container",
                description="Remove stopped container",
            )
        )

    if not items:
        return "No actions available"

    screen = ListScreen(items, title=f"Actions — {container_name}")
    selected = screen.run()
    if not selected:
        return "Cancelled"

    if selected == "attach_shell":
        cmd = ["docker", "exec", "-it", container_name, "bash"]
        result = subprocess.run(cmd)
        return "Shell closed" if result.returncode == 0 else "Shell exited with errors"

    if selected == "stop":
        _, message = _handle_container_stop(container_id, container_name)
        return message

    if selected == "resume":
        _, message = _handle_container_resume(container_id, container_name)
        return message

    if selected == "delete":
        _, message = _handle_container_remove(container_id, container_name)
        return message

    return None


def _handle_session_action_menu(session: dict[str, Any]) -> str | None:
    """Show a session actions menu and execute the selected action."""
    from ... import sessions as session_store
    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    items: list[ListItem[str]] = [
        ListItem(value="resume", label="Resume session", description="Continue this session"),
    ]

    items.append(
        ListItem(
            value="remove",
            label="Remove from history",
            description="Does not delete any containers",
        )
    )

    screen = ListScreen(items, title="Session Actions")
    selected = screen.run()
    if not selected:
        return "Cancelled"

    if selected == "resume":
        try:
            success = _handle_session_resume(session)
            return "Resumed session" if success else "Resume failed"
        except Exception:
            return "Resume failed"

    if selected == "remove":
        workspace = session.get("workspace")
        branch = session.get("branch")
        if not workspace:
            return "Missing workspace"
        removed = session_store.remove_session(workspace, branch)
        return "Removed from history" if removed else "No matching session found"

    return None


def _handle_worktree_action_menu(worktree_path: str) -> str | None:
    """Show a worktree actions menu and execute the selected action."""
    import subprocess
    from pathlib import Path

    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    items: list[ListItem[str]] = [
        ListItem(value="start", label="Start session here", description="Launch Claude"),
        ListItem(
            value="open_shell",
            label="Open shell",
            description="cd into this worktree",
        ),
        ListItem(
            value="remove",
            label="Remove worktree",
            description="git worktree remove <path>",
        ),
    ]

    screen = ListScreen(items, title=f"Worktree Actions — {Path(worktree_path).name}")
    selected = screen.run()
    if not selected:
        return "Cancelled"

    if selected == "start":
        # Reuse worktree start flow directly
        result = _handle_worktree_start(worktree_path)
        if result is None:
            return "Cancelled"
        return "Started session" if result else "Start cancelled"

    if selected == "open_shell":
        console.print(f"[cyan]cd {worktree_path}[/cyan]")
        console.print("[dim]Copy/paste to jump into this worktree.[/dim]")
        return "Path copied to screen"

    if selected == "remove":
        if not Confirm.ask(
            "[yellow]Remove this worktree? This cannot be undone.[/yellow]",
            default=False,
        ):
            return "Cancelled"
        try:
            subprocess.run(["git", "worktree", "remove", "--force", worktree_path], check=True)
            return "Worktree removed"
        except Exception:
            return "Failed to remove worktree"

    return None


def _handle_settings() -> str | None:
    """Handle settings and maintenance screen request from dashboard.

    Shows the settings and maintenance TUI, allowing users to perform
    maintenance operations like clearing cache, pruning sessions, etc.

    Returns:
        Success message string if an action was performed, None if cancelled.
    """
    from ..settings import run_settings_screen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    try:
        return run_settings_screen()
    except Exception as e:
        console.print(f"[red]Error in settings screen: {e}[/red]")
        return None


def _handle_profile_menu() -> str | None:
    """Handle profile quick menu request from dashboard.

    Shows a quick menu with profile actions: save, apply, diff, settings.

    Returns:
        Success message string if an action was performed, None if cancelled.
    """
    from pathlib import Path

    from ..list_screen import ListItem, ListScreen

    console = get_err_console()
    _prepare_for_nested_ui(console)

    items: list[ListItem[str]] = [
        ListItem(
            value="save",
            label="Save current settings",
            description="Capture workspace settings to profile",
        ),
        ListItem(
            value="apply",
            label="Apply saved profile",
            description="Restore settings from profile",
        ),
        ListItem(
            value="diff",
            label="Show diff",
            description="Compare profile vs workspace",
        ),
        ListItem(
            value="settings",
            label="Open in Settings",
            description="Full profile management",
        ),
    ]

    screen = ListScreen(items, title="[cyan]Profile[/cyan]")
    selected = screen.run()

    if not selected:
        return None

    # Import profile functions
    from ...core.personal_profiles import (
        compute_fingerprints,
        load_personal_profile,
        load_workspace_mcp,
        load_workspace_settings,
        merge_personal_mcp,
        merge_personal_settings,
        save_applied_state,
        save_personal_profile,
        write_workspace_mcp,
        write_workspace_settings,
    )

    workspace = Path.cwd()

    if selected == "save":
        try:
            settings = load_workspace_settings(workspace)
            mcp = load_workspace_mcp(workspace)
            save_personal_profile(workspace, settings, mcp)
            return "Profile saved"
        except Exception as e:
            console.print(f"[red]Save failed: {e}[/red]")
            return "Profile save failed"

    if selected == "apply":
        profile = load_personal_profile(workspace)
        if not profile:
            console.print("[yellow]No profile saved for this workspace[/yellow]")
            return "No profile to apply"
        try:
            # Load current workspace settings
            current_settings = load_workspace_settings(workspace) or {}
            current_mcp = load_workspace_mcp(workspace) or {}

            # Merge profile into workspace
            if profile.settings:
                merged_settings = merge_personal_settings(
                    workspace, current_settings, profile.settings
                )
                write_workspace_settings(workspace, merged_settings)

            if profile.mcp:
                merged_mcp = merge_personal_mcp(current_mcp, profile.mcp)
                write_workspace_mcp(workspace, merged_mcp)

            # Update applied state
            fingerprints = compute_fingerprints(workspace)
            save_applied_state(workspace, profile.profile_id, fingerprints)

            return "Profile applied"
        except Exception as e:
            console.print(f"[red]Apply failed: {e}[/red]")
            return "Profile apply failed"

    if selected == "diff":
        profile = load_personal_profile(workspace)
        if not profile:
            console.print("[yellow]No profile saved for this workspace[/yellow]")
            return "No profile to compare"

        # Show structured diff overlay
        from rich import box
        from rich.panel import Panel

        from ...core.personal_profiles import (
            compute_structured_diff,
            load_workspace_mcp,
            load_workspace_settings,
        )

        current_settings = load_workspace_settings(workspace) or {}
        current_mcp = load_workspace_mcp(workspace) or {}

        diff = compute_structured_diff(
            workspace_settings=current_settings,
            profile_settings=profile.settings,
            workspace_mcp=current_mcp,
            profile_mcp=profile.mcp,
        )

        if diff.is_empty:
            console.print("[green]✓ Profile is in sync with workspace[/green]")
            return "Profile in sync"

        # Build diff content
        lines: list[str] = []
        current_section = ""
        indicators = {
            "added": "[green]+[/green]",
            "removed": "[red]−[/red]",
            "modified": "[yellow]~[/yellow]",
        }
        section_names = {
            "plugins": "plugins",
            "mcp_servers": "mcp_servers",
            "marketplaces": "marketplaces",
        }

        for item in diff.items[:12]:  # Smart fallback: limit to 12 items
            if item.section != current_section:
                if current_section:
                    lines.append("")
                lines.append(f"  [bold]{section_names.get(item.section, item.section)}[/bold]")
                current_section = item.section
            indicator = indicators.get(item.status, " ")
            modifier = "  [dim](modified)[/dim]" if item.status == "modified" else ""
            lines.append(f"    {indicator} {item.name}{modifier}")

        if diff.total_count > 12:
            lines.append("")
            lines.append(f"  [dim]+ {diff.total_count - 12} more...[/dim]")

        lines.append("")
        lines.append(f"  [dim]{diff.total_count} difference(s)[/dim]")

        console.print()
        console.print(
            Panel(
                "\n".join(lines),
                title="[bold]Profile Diff[/bold]",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        return "Diff shown"

    if selected == "settings":
        # Open settings TUI on Profiles tab
        from ..settings import run_settings_screen

        return run_settings_screen(initial_category="PROFILES")

    return None


def _handle_sandbox_import() -> str | None:
    """Handle sandbox plugin import request from dashboard.

    Detects plugins installed in the sandbox but not in the workspace settings,
    and prompts the user to import them.

    Returns:
        Success message string if imports were made, None if cancelled or no imports.
    """
    import os
    from pathlib import Path

    from ...core.personal_profiles import (
        compute_sandbox_import_candidates,
        load_workspace_settings,
        merge_sandbox_imports,
        write_workspace_settings,
    )
    from ...docker.launch import get_sandbox_settings

    console = get_err_console()
    _prepare_for_nested_ui(console)

    workspace = Path(os.getcwd())

    # Get current workspace settings
    workspace_settings = load_workspace_settings(workspace) or {}

    # Get sandbox settings from Docker volume
    console.print("[dim]Checking sandbox for plugin changes...[/dim]")
    sandbox_settings = get_sandbox_settings()

    if not sandbox_settings:
        console.print("[yellow]No sandbox settings found.[/yellow]")
        console.print("[dim]Start a session first to create sandbox settings.[/dim]")
        return None

    # Compute what's in sandbox but not in workspace
    missing_plugins, missing_marketplaces = compute_sandbox_import_candidates(
        workspace_settings, sandbox_settings
    )

    if not missing_plugins and not missing_marketplaces:
        console.print("[green]✓ No new plugins to import.[/green]")
        console.print("[dim]Workspace is in sync with sandbox.[/dim]")
        return "No imports needed"

    # Show preview of what will be imported
    console.print()
    console.print("[yellow]Sandbox plugins available for import:[/yellow]")
    if missing_plugins:
        for plugin in missing_plugins:
            console.print(f"  [cyan]+[/cyan] {plugin}")
    if missing_marketplaces:
        for name in sorted(missing_marketplaces.keys()):
            console.print(f"  [cyan]+[/cyan] marketplace: {name}")
    console.print()

    # Confirm import
    if not Confirm.ask("Import these into workspace settings?", default=True):
        return None

    # Merge and write to workspace settings
    try:
        merged_settings = merge_sandbox_imports(
            workspace_settings, missing_plugins, missing_marketplaces
        )
        write_workspace_settings(workspace, merged_settings)

        total = len(missing_plugins) + len(missing_marketplaces)
        console.print(f"[green]✓ Imported {total} item(s) to workspace settings.[/green]")
        return f"Imported {total} plugin(s)"

    except Exception as e:
        console.print(f"[red]Import failed: {e}[/red]")
        return "Import failed"


def _show_onboarding_banner() -> None:
    """Show one-time onboarding banner for new users.

    Displays a brief tip about `scc worktree enter` as the recommended
    way to switch worktrees without shell configuration.

    Waits for user to press any key before continuing.
    """
    import readchar
    from rich import box
    from rich.panel import Panel

    console = get_err_console()

    # Create a compact onboarding message
    message = (
        "[bold cyan]Welcome to SCC![/bold cyan]\n\n"
        "[yellow]Tip:[/yellow] Use [bold]scc worktree enter[/bold] to switch worktrees.\n"
        "No shell setup required — just type [dim]exit[/dim] to return.\n\n"
        "[dim]Press [bold]?[/bold] anytime for help, or any key to continue...[/dim]"
    )

    console.print()
    console.print(
        Panel(
            message,
            title="[bold]Getting Started[/bold]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
    console.print()

    # Wait for any key
    readchar.readkey()
