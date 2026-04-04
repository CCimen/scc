"""Handler functions for dashboard orchestrator effects.

Extracted from orchestrator.py to keep that module focused on the
dashboard event loop and flow state management. These functions execute
OUTSIDE the Rich Live context after an intent exception unwinds.

All handlers follow the same pattern:
1. Get err console
2. Prepare terminal for nested UI
3. Execute the handler logic
4. Return result for apply_dashboard_effect_result
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scc_cli.application import dashboard as app_dashboard

from ...confirm import Confirm
from ...console import get_err_console
from ..chrome import print_with_layout

# ── Re-exports from orchestrator_container_actions.py ───────────────────────
from .orchestrator_container_actions import (  # noqa: F401
    _handle_container_remove,
    _handle_container_resume,
    _handle_container_stop,
)

# ── Re-exports from orchestrator_menus.py (preserve test-patch targets) ─────
from .orchestrator_menus import (  # noqa: F401
    _handle_profile_menu,
    _handle_sandbox_import,
    _handle_settings,
    _show_onboarding_banner,
)

if TYPE_CHECKING:
    from rich.console import Console

    from scc_cli.ports.session_models import SessionSummary


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
    from ..keys import TeamSwitchRequested
    from ..picker import pick_team

    console = get_err_console()
    _prepare_for_nested_ui(console)

    try:
        # Load config and org config for team list
        cfg = config.load_user_config()
        org_config = config.load_cached_org_config()

        available_teams = teams.list_teams(org_config)
        if not available_teams:
            print_with_layout(console, "[yellow]No teams available[/yellow]", max_width=120)
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
            print_with_layout(
                console,
                f"[green]Switched to team: {team_name}[/green]",
                max_width=120,
            )
        # If cancelled, just return to dashboard

    except TeamSwitchRequested:
        # Nested team switch (shouldn't happen, but handle gracefully)
        pass
    except Exception as e:
        print_with_layout(
            console,
            f"[red]Error switching team: {e}[/red]",
            max_width=120,
        )


def _handle_start_flow(reason: str) -> app_dashboard.StartFlowResult:
    """Handle start flow request from dashboard."""
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
        print_with_layout(console, "[dim]Starting a new session...[/dim]")
    elif reason == "no_sessions":
        print_with_layout(console, "[dim]Starting your first session...[/dim]")
    console.print()

    # Run the wizard with allow_back=True for dashboard context
    # Returns: True (success), False (Esc/back), None (q/quit)
    result = run_start_wizard_flow(skip_quick_resume=skip_quick_resume, allow_back=True)
    return app_dashboard.StartFlowResult.from_legacy(result)


def _handle_worktree_start(worktree_path: str) -> app_dashboard.StartFlowResult:
    """Handle starting a session in a specific worktree."""
    from pathlib import Path

    from rich.status import Status

    from ... import config
    from ...application.start_session import (
        StartSessionDependencies,
        StartSessionRequest,
        sync_marketplace_settings_for_start,
    )
    from ...bootstrap import get_default_adapters
    from ...commands.launch import (
        _launch_sandbox,
        _resolve_mount_and_branch,
        _validate_and_resolve_workspace,
    )
    from ...commands.launch.team_settings import _configure_team_settings
    from ...marketplace.materialize import materialize_marketplace
    from ...marketplace.resolve import resolve_effective_config
    from ...theme import Spinners

    console = get_err_console()

    workspace_path = Path(worktree_path)
    workspace_name = workspace_path.name

    # Validate workspace exists
    if not workspace_path.exists():
        console.print(f"[red]Worktree no longer exists: {worktree_path}[/red]")
        return app_dashboard.StartFlowResult.from_legacy(False)

    console.print(f"[cyan]Starting session in:[/cyan] {workspace_name}")
    console.print()

    try:
        # Obtain adapters early so the probe-backed runtime check can run
        adapters = get_default_adapters()

        # Docker availability check (via RuntimeProbe)
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            adapters.sandbox_runtime.ensure_available()

        # Validate and resolve workspace
        resolved_path = _validate_and_resolve_workspace(str(workspace_path))
        if resolved_path is None:
            console.print("[red]Workspace validation failed[/red]")
            return app_dashboard.StartFlowResult.from_legacy(False)
        workspace_path = resolved_path

        # Get current team from config
        cfg = config.load_user_config()
        team = cfg.get("selected_profile")
        _configure_team_settings(team, cfg)
        start_dependencies = StartSessionDependencies(
            filesystem=adapters.filesystem,
            remote_fetcher=adapters.remote_fetcher,
            clock=adapters.clock,
            git_client=adapters.git_client,
            agent_runner=adapters.agent_runner,
            sandbox_runtime=adapters.sandbox_runtime,
            resolve_effective_config=resolve_effective_config,
            materialize_marketplace=materialize_marketplace,
        )
        start_request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=team,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=team is None,
            dry_run=False,
            allow_suspicious=False,
            org_config=config.load_cached_org_config(),
            org_config_url=None,
        )
        sync_result, _sync_error = sync_marketplace_settings_for_start(
            start_request,
            start_dependencies,
        )
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
        return app_dashboard.StartFlowResult.from_legacy(True)

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        return app_dashboard.StartFlowResult.from_legacy(False)
    except Exception as e:
        console.print(f"[red]Error starting session: {e}[/red]")
        return app_dashboard.StartFlowResult.from_legacy(False)


def _handle_session_resume(session: SessionSummary) -> bool:
    """Resume a Claude Code session from the dashboard.

    This function executes OUTSIDE Rich Live context (the dashboard has
    already exited via the exception unwind before this is called).

    Args:
        session: Session summary containing workspace, team, branch, container_name, etc.

    Returns:
        True if session was resumed successfully, False if resume failed
        (e.g., workspace no longer exists).
    """

    from pathlib import Path

    from rich.status import Status

    from ... import config
    from ...application.start_session import (
        StartSessionDependencies,
        StartSessionRequest,
        sync_marketplace_settings_for_start,
    )
    from ...bootstrap import get_default_adapters
    from ...commands.launch import (
        _launch_sandbox,
        _resolve_mount_and_branch,
        _validate_and_resolve_workspace,
    )
    from ...commands.launch.team_settings import _configure_team_settings
    from ...marketplace.materialize import materialize_marketplace
    from ...marketplace.resolve import resolve_effective_config
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    # Extract session info
    workspace = session.workspace
    team = session.team  # May be None for standalone
    session_name = session.name
    branch = session.branch

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
        # Obtain adapters early so the probe-backed runtime check can run
        adapters = get_default_adapters()

        # Docker availability check (via RuntimeProbe)
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            adapters.sandbox_runtime.ensure_available()

        # Validate and resolve workspace (we know it exists from earlier check)
        resolved_path = _validate_and_resolve_workspace(str(workspace_path))
        if resolved_path is None:
            console.print("[red]Workspace validation failed[/red]")
            return False
        workspace_path = resolved_path

        # Configure team settings
        cfg = config.load_user_config()
        _configure_team_settings(team, cfg)
        start_dependencies = StartSessionDependencies(
            filesystem=adapters.filesystem,
            remote_fetcher=adapters.remote_fetcher,
            clock=adapters.clock,
            git_client=adapters.git_client,
            agent_runner=adapters.agent_runner,
            sandbox_runtime=adapters.sandbox_runtime,
            resolve_effective_config=resolve_effective_config,
            materialize_marketplace=materialize_marketplace,
        )
        start_request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=team,
            session_name=session_name,
            resume=True,
            fresh=False,
            offline=False,
            standalone=team is None,
            dry_run=False,
            allow_suspicious=False,
            org_config=config.load_cached_org_config(),
            org_config_url=None,
        )
        sync_result, _sync_error = sync_marketplace_settings_for_start(
            start_request,
            start_dependencies,
        )
        plugin_settings = sync_result.rendered_settings if sync_result else None

        # Resolve mount path and branch
        mount_path, current_branch = _resolve_mount_and_branch(workspace_path)

        # Use session's stored branch if available (more accurate than detected)
        if branch:
            current_branch = branch

        # Show resume info
        workspace_name = workspace_path.name
        print_with_layout(console, f"[cyan]Resuming session:[/cyan] {workspace_name}")
        if team:
            print_with_layout(console, f"[dim]Team: {team}[/dim]")
        if current_branch:
            print_with_layout(console, f"[dim]Branch: {current_branch}[/dim]")
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


def _handle_session_action_menu(session: SessionSummary) -> str | None:
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
        workspace = session.workspace
        branch = session.branch
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
        if result.decision is app_dashboard.StartFlowDecision.QUIT:
            return "Cancelled"
        if result.decision is app_dashboard.StartFlowDecision.LAUNCHED:
            return "Started session"
        return "Start cancelled"

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
