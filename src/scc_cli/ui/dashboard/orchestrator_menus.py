"""Settings, profile, sandbox, and onboarding handlers for the dashboard.

Extracted from orchestrator_handlers.py to reduce module size.
All handlers follow the same pattern: get err console, prepare terminal,
execute handler logic, return result for apply_dashboard_effect_result.
"""

from __future__ import annotations

from ...confirm import Confirm
from ...console import get_err_console
from ..chrome import print_with_layout


def _prepare_for_nested_ui_menu() -> None:
    """Prepare console for nested UI - local helper to avoid cross-import."""
    console = get_err_console()
    console.clear()
    console.show_cursor(True)


def _handle_settings() -> str | None:
    """Handle settings and maintenance screen request from dashboard.

    Shows the settings and maintenance TUI, allowing users to perform
    maintenance operations like clearing cache, pruning sessions, etc.

    Returns:
        Success message string if an action was performed, None if cancelled.
    """
    from ..settings import run_settings_screen

    console = get_err_console()
    _prepare_for_nested_ui_menu()

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
    _prepare_for_nested_ui_menu()

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
    from scc_cli.marketplace.managed import load_managed_state

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
                    workspace, current_settings, profile.settings,
                    managed_state_loader=load_managed_state,
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
    _prepare_for_nested_ui_menu()

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
    print_with_layout(
        console,
        Panel(
            message,
            title="[bold]Getting Started[/bold]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
        ),
        max_width=120,
        constrain=True,
    )
    console.print()

    # Wait for any key
    readchar.readkey()
