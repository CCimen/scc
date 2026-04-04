"""Team info and list commands.

Extracted from team.py to reduce module size. Contains:
- team_info: shows detailed team profile information
- team_list: lists available team profiles

These are plain functions, registered on team_app by team.py.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.panel import Panel
from rich.table import Table

from .. import config, teams
from ..bootstrap import get_default_adapters
from ..cli_common import console, render_responsive_table
from ..output_mode import is_json_mode, print_human
from ..panels import create_warning_panel


def team_list(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full descriptions"),
    sync: bool = typer.Option(
        False, "--sync", "-s", help="Sync team configs from organization"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(
        False, "--pretty", help="Pretty-print JSON (implies --json)"
    ),
) -> dict[str, Any]:
    """List available team profiles.

    Returns a list of teams with their names, descriptions, and plugins.
    Use --verbose to show full descriptions instead of truncated versions.
    Use --sync to refresh the team list from the organization config.
    """
    from .team import _format_plugins_for_display

    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    # Sync if requested
    if sync:
        from ..remote import fetch_org_config

        org_source = cfg.get("organization_source", {})
        org_url = org_source.get("url")
        org_auth = org_source.get("auth")
        if org_url:
            adapters = get_default_adapters()
            fetched_config, _etag, status_code = fetch_org_config(
                org_url,
                org_auth,
                fetcher=adapters.remote_fetcher,
            )
            if fetched_config and status_code == 200:
                org_config = fetched_config
                # Save to cache
                config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
                import json

                cache_file = config.CACHE_DIR / "org_config.json"
                cache_file.write_text(json.dumps(org_config, indent=2))
                print_human("[green]✓ Team list synced from organization[/green]")

    available_teams = teams.list_teams(org_config)

    current = cfg.get("selected_profile")

    team_data = []
    for team in available_teams:
        team_data.append(
            {
                "name": team["name"],
                "description": team.get("description", ""),
                "plugins": team.get("plugins", []),
                "is_current": team["name"] == current,
            }
        )

    if not is_json_mode():
        if not available_teams:
            if config.is_standalone_mode():
                console.print(
                    create_warning_panel(
                        "Standalone Mode",
                        "Teams are not available in standalone mode.",
                        "Run 'scc setup' with an organization URL to enable teams",
                    )
                )
            else:
                console.print(
                    create_warning_panel(
                        "No Teams",
                        "No team profiles defined in organization config.",
                        "Contact your organization admin to configure teams",
                    )
                )
            return {"teams": [], "current": current}

        rows = []
        for team in available_teams:
            name = team["name"]
            if name == current:
                name = f"[bold]{name}[/bold] ←"

            desc = team.get("description", "")
            if not verbose and len(desc) > 40:
                desc = desc[:37] + "..."

            plugins = team.get("plugins", [])
            plugins_display = _format_plugins_for_display(plugins)
            rows.append([name, desc, plugins_display])

        render_responsive_table(
            title="Available Team Profiles",
            columns=[
                ("Team", "cyan"),
                ("Description", "white"),
            ],
            rows=rows,
            wide_columns=[
                ("Plugins", "yellow"),
            ],
        )

        console.print()
        console.print(
            "[dim]Use: scc team switch <name> to switch, "
            "scc team info <name> for details[/dim]"
        )

    return {"teams": team_data, "current": current}


def team_info(
    team_name: str = typer.Argument(..., help="Team name to show details for"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(
        False, "--pretty", help="Pretty-print JSON (implies --json)"
    ),
) -> dict[str, Any]:
    """Show detailed information for a specific team profile.

    Displays team description, plugin configuration, marketplace info,
    federation status (federated vs inline), config source, and trust grants.
    """
    from .team import _get_config_source_from_raw

    org_config = config.load_cached_org_config()

    details = teams.get_team_details(team_name, org_config)

    # Detect if team is federated (has config_source)
    raw_source = _get_config_source_from_raw(org_config, team_name)
    is_federated = raw_source is not None

    # Get config source description for federated teams
    config_source_display: str | None = None
    if is_federated and raw_source is not None:
        source_type = raw_source.get("source")
        if source_type == "github":
            config_source_display = (
                f"github.com/{raw_source.get('owner', '?')}/{raw_source.get('repo', '?')}"
            )
        elif source_type == "git":
            url = raw_source.get("url", "")
            if url.startswith("https://"):
                url = url[8:]
            elif url.startswith("git@"):
                url = url[4:].replace(":", "/", 1)
            if url.endswith(".git"):
                url = url[:-4]
            config_source_display = url
        elif source_type == "url":
            url = raw_source.get("url", "")
            if url.startswith("https://"):
                url = url[8:]
            config_source_display = url

    # Get trust grants for federated teams
    trust_grants: dict[str, Any] | None = None
    if is_federated and org_config:
        profiles = org_config.get("profiles", {})
        profile = profiles.get(team_name, {})
        if isinstance(profile, dict):
            trust_grants = profile.get("trust")

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
    validation = teams.validate_team_profile(team_name, org_config)

    # Human output
    if not is_json_mode():
        grid = Table.grid(padding=(0, 2))
        grid.add_column(style="dim", no_wrap=True)
        grid.add_column(style="white")

        grid.add_row("Description:", details.get("description", "-"))

        # Show federation mode
        if is_federated:
            grid.add_row("Mode:", "[cyan]federated[/cyan]")
            if config_source_display:
                grid.add_row("Config Source:", config_source_display)
        else:
            grid.add_row("Mode:", "[dim]inline[/dim]")

        plugins = details.get("plugins", [])
        if plugins:
            plugins_display = ", ".join(plugins)
            grid.add_row("Plugins:", plugins_display)
            if details.get("marketplace_repo"):
                grid.add_row("Marketplace:", details.get("marketplace_repo", "-"))
        else:
            grid.add_row("Plugins:", "[dim]None (base profile)[/dim]")

        # Show trust grants for federated teams
        if trust_grants:
            grid.add_row("", "")
            grid.add_row("[bold]Trust Grants:[/bold]", "")
            inherit = trust_grants.get("inherit_org_marketplaces", True)
            allow_add = trust_grants.get("allow_additional_marketplaces", False)
            grid.add_row(
                "  Inherit Org Marketplaces:",
                "[green]yes[/green]" if inherit else "[red]no[/red]",
            )
            grid.add_row(
                "  Allow Additional Marketplaces:",
                "[green]yes[/green]" if allow_add else "[red]no[/red]",
            )

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

    # Build response with federation metadata
    response: dict[str, Any] = {
        "team": team_name,
        "found": True,
        "is_federated": is_federated,
        "profile": {
            "name": details.get("name"),
            "description": details.get("description"),
            "plugins": details.get("plugins", []),
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

    # Add federation details for federated teams
    if is_federated:
        response["config_source"] = config_source_display
        if trust_grants:
            response["trust"] = trust_grants

    return response
