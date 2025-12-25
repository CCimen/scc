"""
Define team management commands for SCC CLI.

Provide structured team management:
- scc team list      - List available teams
- scc team current   - Show current team
- scc team switch    - Switch to a different team (interactive picker)
- scc team info      - Show detailed team information

All commands support --json output with proper envelopes.
"""

from typing import Any

import typer
from rich.panel import Panel
from rich.table import Table

from . import config, teams
from .cli_common import console, handle_errors, render_responsive_table
from .json_command import json_command
from .kinds import Kind
from .output_mode import is_json_mode, print_human
from .panels import create_warning_panel
from .ui.gate import InteractivityContext
from .ui.picker import TeamSwitchRequested, pick_team

# ═══════════════════════════════════════════════════════════════════════════════
# Team App Definition
# ═══════════════════════════════════════════════════════════════════════════════

team_app = typer.Typer(
    name="team",
    help="Team profile management",
    no_args_is_help=True,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Team List Command
# ═══════════════════════════════════════════════════════════════════════════════


@team_app.command("list")
@json_command(Kind.TEAM_LIST)
@handle_errors
def team_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full descriptions"),
    sync: bool = typer.Option(False, "--sync", "-s", help="Sync team configs from organization"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any]:
    """List available team profiles.

    Returns a list of teams with their names, descriptions, and plugins.
    Use --verbose to show full descriptions instead of truncated versions.
    Use --sync to refresh the team list from the organization config.
    """
    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    # Sync if requested
    if sync:
        from .remote import fetch_org_config

        org_source = cfg.get("organization_source", {})
        org_url = org_source.get("url")
        org_auth = org_source.get("auth")
        if org_url:
            fetched_config, _etag, status_code = fetch_org_config(org_url, org_auth)
            if fetched_config and status_code == 200:
                org_config = fetched_config
                # Save to cache
                config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
                import json

                cache_file = config.CACHE_DIR / "org_config.json"
                cache_file.write_text(json.dumps(org_config, indent=2))
                print_human("[green]✓ Team list synced from organization[/green]")

    # Get teams
    available_teams = teams.list_teams(cfg, org_config=org_config)

    # Get current team for marking
    current = cfg.get("selected_profile")

    # Build data structure for JSON output
    team_data = []
    for team in available_teams:
        team_data.append(
            {
                "name": team["name"],
                "description": team.get("description", ""),
                "plugin": team.get("plugin"),
                "is_current": team["name"] == current,
            }
        )

    # Human-readable output
    if not is_json_mode():
        if not available_teams:
            console.print(
                create_warning_panel(
                    "No Teams",
                    "No team profiles configured.",
                    "Run 'scc setup' to initialize configuration",
                )
            )
            return {"teams": [], "current": current}

        # Build rows for responsive table
        rows = []
        for team in available_teams:
            name = team["name"]
            if name == current:
                name = f"[bold]{name}[/bold] ←"

            desc = team.get("description", "")
            if not verbose and len(desc) > 40:
                desc = desc[:37] + "..."

            plugin = team.get("plugin") or "-"
            rows.append([name, desc, plugin])

        render_responsive_table(
            title="Available Team Profiles",
            columns=[
                ("Team", "cyan"),
                ("Description", "white"),
            ],
            rows=rows,
            wide_columns=[
                ("Plugin", "yellow"),
            ],
        )

        console.print()
        console.print(
            "[dim]Use: scc team switch <name> to switch, scc team info <name> for details[/dim]"
        )

    return {"teams": team_data, "current": current}


# ═══════════════════════════════════════════════════════════════════════════════
# Team Current Command
# ═══════════════════════════════════════════════════════════════════════════════


@team_app.command("current")
@json_command(Kind.TEAM_CURRENT)
@handle_errors
def team_current(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any]:
    """Show the currently selected team profile.

    Displays the current team and basic information about it.
    Returns null for team if no team is selected.
    """
    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    current = cfg.get("selected_profile")

    if not current:
        print_human(
            "[yellow]No team currently selected.[/yellow]\n"
            "[dim]Use 'scc team switch <name>' to select a team[/dim]"
        )
        return {"team": None, "profile": None}

    # Get team details
    details = teams.get_team_details(current, cfg, org_config=org_config)

    if not details:
        print_human(
            f"[yellow]Current team '{current}' not found in configuration.[/yellow]\n"
            "[dim]Run 'scc team list --sync' to refresh[/dim]"
        )
        return {"team": current, "profile": None, "error": "team_not_found"}

    # Human output
    print_human(f"[bold cyan]Current team:[/bold cyan] {current}")
    if details.get("description"):
        print_human(f"[dim]{details['description']}[/dim]")
    if details.get("plugin"):
        print_human(f"[dim]Plugin: {details['plugin']}[/dim]")

    return {
        "team": current,
        "profile": {
            "name": details.get("name"),
            "description": details.get("description"),
            "plugin": details.get("plugin"),
            "marketplace": details.get("marketplace"),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Team Switch Command
# ═══════════════════════════════════════════════════════════════════════════════


@team_app.command("switch")
@json_command(Kind.TEAM_SWITCH)
@handle_errors
def team_switch(
    team_name: str = typer.Argument(
        None, help="Team name to switch to (interactive picker if not provided)"
    ),
    non_interactive: bool = typer.Option(
        False, "--non-interactive", help="Fail if team name not provided"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any]:
    """Switch to a different team profile.

    If team_name is not provided, shows an interactive picker (if TTY).
    Use --non-interactive to fail instead of showing picker.
    """
    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    available_teams = teams.list_teams(cfg, org_config=org_config)

    if not available_teams:
        print_human(
            "[yellow]No teams available to switch to.[/yellow]\n"
            "[dim]Run 'scc setup' to configure teams[/dim]"
        )
        return {"success": False, "error": "no_teams_available", "previous": None, "current": None}

    # Get current team for picker display
    current = cfg.get("selected_profile")

    # Resolve team name (explicit arg, picker, or error)
    resolved_name: str | None = team_name

    if resolved_name is None:
        # Create interactivity context from flags
        ctx = InteractivityContext.create(
            json_mode=is_json_mode(),
            no_interactive=non_interactive,
        )

        if ctx.allows_prompt():
            # Show interactive picker
            try:
                selected_team = pick_team(available_teams, current_team=current)
                if selected_team is None:
                    # User cancelled - exit cleanly
                    return {
                        "success": False,
                        "cancelled": True,
                        "previous": current,
                        "current": None,
                    }
                resolved_name = selected_team["name"]
            except TeamSwitchRequested:
                # Already in team picker - treat as cancel
                return {"success": False, "cancelled": True, "previous": current, "current": None}
        else:
            # Non-interactive mode with no team specified
            raise typer.BadParameter(
                "Team name required in non-interactive mode. "
                f"Available: {', '.join(t['name'] for t in available_teams)}"
            )

    # Validate team exists (when name provided directly as arg)
    team_names = [t["name"] for t in available_teams]
    if resolved_name not in team_names:
        print_human(
            f"[red]Team '{resolved_name}' not found.[/red]\n"
            f"[dim]Available: {', '.join(team_names)}[/dim]"
        )
        return {"success": False, "error": "team_not_found", "team": resolved_name}

    # Get previous team
    previous = cfg.get("selected_profile")

    # Switch team
    cfg["selected_profile"] = resolved_name
    config.save_user_config(cfg)

    print_human(f"[green]✓ Switched to team: {resolved_name}[/green]")
    if previous and previous != resolved_name:
        print_human(f"[dim]Previous: {previous}[/dim]")

    return {
        "success": True,
        "previous": previous,
        "current": resolved_name,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Team Info Command
# ═══════════════════════════════════════════════════════════════════════════════


@team_app.command("info")
@json_command(Kind.TEAM_INFO)
@handle_errors
def team_info(
    team_name: str = typer.Argument(..., help="Team name to show details for"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any]:
    """Show detailed information for a specific team profile.

    Displays team description, plugin configuration, marketplace info,
    and other team-specific settings.
    """
    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    details = teams.get_team_details(team_name, cfg, org_config=org_config)

    if not details:
        if not is_json_mode():
            console.print(
                create_warning_panel(
                    "Team Not Found",
                    f"No team profile named '{team_name}'.",
                    "Run 'scc team list' to see available profiles",
                )
            )
        return {"team": team_name, "found": False, "profile": None}

    # Get validation info
    validation = teams.validate_team_profile(team_name, cfg, org_config=org_config)

    # Human output
    if not is_json_mode():
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", no_wrap=True)
        grid.add_column(style="white")

        grid.add_row("Description:", details.get("description", "-"))

        plugin = details.get("plugin")
        if plugin:
            marketplace = details.get("marketplace", "sundsvall")
            grid.add_row("Plugin:", f"{plugin}@{marketplace}")
            if details.get("marketplace_repo"):
                grid.add_row("Marketplace:", details.get("marketplace_repo", "-"))
        else:
            grid.add_row("Plugin:", "[dim]None (base profile)[/dim]")

        # Show validation warnings
        if validation.get("warnings"):
            grid.add_row("", "")
            for warning in validation["warnings"]:
                grid.add_row("[yellow]Warning:[/yellow]", warning)

        panel = Panel(
            grid,
            title=f"[bold cyan]Team: {team_name}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )

        console.print()
        console.print(panel)
        console.print()
        console.print(f"[dim]Use: scc start -t {team_name} to use this profile[/dim]")

    return {
        "team": team_name,
        "found": True,
        "profile": {
            "name": details.get("name"),
            "description": details.get("description"),
            "plugin": details.get("plugin"),
            "marketplace": details.get("marketplace"),
            "marketplace_type": details.get("marketplace_type"),
            "marketplace_repo": details.get("marketplace_repo"),
        },
        "validation": {
            "valid": validation.get("valid", True),
            "warnings": validation.get("warnings", []),
            "errors": validation.get("errors", []),
        },
    }
