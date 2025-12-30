"""
Define team management commands for SCC CLI.

Provide structured team management:
- scc team list      - List available teams
- scc team current   - Show current team
- scc team switch    - Switch to a different team (interactive picker)
- scc team info      - Show detailed team information
- scc team validate  - Validate team configuration (plugins, security, cache)

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
from .marketplace.compute import TeamNotFoundError
from .marketplace.resolve import ConfigFetchError, EffectiveConfig, resolve_effective_config
from .marketplace.schema import OrganizationConfig
from .marketplace.team_fetch import TeamFetchResult, fetch_team_config
from .marketplace.trust import TrustViolationError
from .output_mode import is_json_mode, print_human
from .panels import create_warning_panel
from .ui.gate import InteractivityContext
from .ui.picker import TeamSwitchRequested, pick_team

# ═══════════════════════════════════════════════════════════════════════════════
# Federation Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _get_config_source_from_raw(
    org_config: dict[str, Any] | None, team_name: str
) -> dict[str, Any] | None:
    """Extract config_source from raw org_config dict for a team.

    Args:
        org_config: Raw org config dict (or None)
        team_name: Team profile name

    Returns:
        Raw config_source dict if team is federated, None if inline or not found
    """
    if org_config is None:
        return None

    profiles = org_config.get("profiles", {})
    if not profiles or team_name not in profiles:
        return None

    profile = profiles[team_name]
    if not isinstance(profile, dict):
        return None

    return profile.get("config_source")


def _parse_config_source(raw_source: dict[str, Any]) -> Any:
    """Parse raw config_source dict into ConfigSource model.

    The org config uses a nested structure like:
        {"github": {"owner": "...", "repo": "..."}}

    The Pydantic models use a flat structure with a discriminator field:
        {"source": "github", "owner": "...", "repo": "..."}

    This function bridges the two formats.

    Args:
        raw_source: Raw config_source dict from org config

    Returns:
        Parsed ConfigSource model (ConfigSourceGitHub, ConfigSourceGit, or ConfigSourceURL)

    Raises:
        ValueError: If config_source format is invalid
    """
    from .marketplace.schema import (
        ConfigSourceGit,
        ConfigSourceGitHub,
        ConfigSourceURL,
    )

    # Config source is a dict with a single key indicating type
    # Add the discriminator field when parsing
    if "github" in raw_source:
        config_data = {**raw_source["github"], "source": "github"}
        return ConfigSourceGitHub.model_validate(config_data)
    elif "git" in raw_source:
        config_data = {**raw_source["git"], "source": "git"}
        return ConfigSourceGit.model_validate(config_data)
    elif "url" in raw_source:
        config_data = {**raw_source["url"], "source": "url"}
        return ConfigSourceURL.model_validate(config_data)
    else:
        raise ValueError(f"Unknown config_source type: {list(raw_source.keys())}")


def _fetch_federated_team_config(
    org_config: dict[str, Any] | None, team_name: str
) -> TeamFetchResult | None:
    """Fetch team config if team is federated, return None if inline.

    This eagerly fetches the team config to prime the cache when
    switching to a federated team.

    Args:
        org_config: Raw org config dict
        team_name: Team name to fetch config for

    Returns:
        TeamFetchResult if federated team, None if inline
    """
    raw_source = _get_config_source_from_raw(org_config, team_name)
    if raw_source is None:
        return None

    try:
        config_source = _parse_config_source(raw_source)
        return fetch_team_config(config_source, team_name)
    except ValueError:
        # Invalid config_source format - treat as inline
        return None


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
            # Provide context-aware messaging based on mode
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
        # Provide context-aware messaging based on mode
        if config.is_standalone_mode():
            print_human(
                "[yellow]Teams are not available in standalone mode.[/yellow]\n"
                "[dim]Run 'scc setup' with an organization URL to enable teams[/dim]"
            )
        else:
            print_human(
                "[yellow]No teams available to switch to.[/yellow]\n"
                "[dim]No team profiles defined in organization config[/dim]"
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

    # Check if team is federated and fetch config to prime cache
    fetch_result = _fetch_federated_team_config(org_config, resolved_name)
    is_federated = fetch_result is not None

    print_human(f"[green]✓ Switched to team: {resolved_name}[/green]")
    if previous and previous != resolved_name:
        print_human(f"[dim]Previous: {previous}[/dim]")

    details = teams.get_team_details(resolved_name, cfg, org_config=org_config)
    if details:
        description = details.get("description")
        plugin = details.get("plugin") or "none"
        marketplace = details.get("marketplace") or "default"
        if description:
            print_human(f"[dim]Description:[/dim] {description}")
        print_human(f"[dim]Plugin:[/dim] {plugin}")
        print_human(f"[dim]Marketplace:[/dim] {marketplace}")

    # Display federation status
    if fetch_result is not None:
        if fetch_result.success:
            print_human(f"[dim]Federated config synced from {fetch_result.source_url}[/dim]")
        else:
            print_human(f"[yellow]⚠ Could not sync federated config: {fetch_result.error}[/yellow]")

    # Build response with federation metadata
    response: dict[str, Any] = {
        "success": True,
        "previous": previous,
        "current": resolved_name,
        "is_federated": is_federated,
    }

    if is_federated and fetch_result is not None:
        response["source_type"] = fetch_result.source_type
        response["source_url"] = fetch_result.source_url
        if fetch_result.commit_sha:
            response["commit_sha"] = fetch_result.commit_sha
        if fetch_result.etag:
            response["etag"] = fetch_result.etag
        if not fetch_result.success:
            response["fetch_error"] = fetch_result.error

    return response


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
    federation status (federated vs inline), config source, and trust grants.
    """
    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    details = teams.get_team_details(team_name, cfg, org_config=org_config)

    # Detect if team is federated (has config_source)
    raw_source = _get_config_source_from_raw(org_config, team_name)
    is_federated = raw_source is not None

    # Get config source description for federated teams
    config_source_display: str | None = None
    if is_federated and raw_source is not None:
        if "github" in raw_source:
            gh = raw_source["github"]
            config_source_display = f"github.com/{gh.get('owner', '?')}/{gh.get('repo', '?')}"
        elif "git" in raw_source:
            git = raw_source["git"]
            url = git.get("url", "")
            # Normalize for display
            if url.startswith("https://"):
                url = url[8:]
            elif url.startswith("git@"):
                url = url[4:].replace(":", "/", 1)
            if url.endswith(".git"):
                url = url[:-4]
            config_source_display = url
        elif "url" in raw_source:
            url = raw_source["url"].get("url", "")
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
    validation = teams.validate_team_profile(team_name, cfg, org_config=org_config)

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

        plugin = details.get("plugin")
        if plugin:
            marketplace = details.get("marketplace", "sundsvall")
            grid.add_row("Plugin:", f"{plugin}@{marketplace}")
            if details.get("marketplace_repo"):
                grid.add_row("Marketplace:", details.get("marketplace_repo", "-"))
        else:
            grid.add_row("Plugin:", "[dim]None (base profile)[/dim]")

        # Show trust grants for federated teams
        if trust_grants:
            grid.add_row("", "")
            grid.add_row("[bold]Trust Grants:[/bold]", "")
            inherit = trust_grants.get("inherit_org_marketplaces", True)
            allow_add = trust_grants.get("allow_additional_marketplaces", False)
            grid.add_row(
                "  Inherit Org Marketplaces:", "[green]yes[/green]" if inherit else "[red]no[/red]"
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

    # Add federation details for federated teams
    if is_federated:
        response["config_source"] = config_source_display
        if trust_grants:
            response["trust"] = trust_grants

    return response


@team_app.command("validate")
@json_command(Kind.TEAM_VALIDATE)
@handle_errors
def team_validate(
    team_name: str = typer.Argument(..., help="Team name to validate"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any]:
    """Validate team configuration and show effective plugins.

    Resolves the team configuration (inline or federated) and validates:
    - Plugin security compliance (blocked_plugins patterns)
    - Plugin allowlists (allowed_plugins patterns)
    - Marketplace trust grants (for federated teams)
    - Cache freshness status (for federated teams)

    Use --verbose to see detailed validation information including
    individual blocked/disabled plugins and their reasons.
    """
    org_config_data = config.load_cached_org_config()
    if not org_config_data:
        if not is_json_mode():
            console.print(
                create_warning_panel(
                    "No Org Config",
                    "No organization configuration found.",
                    "Run 'scc setup' to configure your organization",
                )
            )
        return {
            "team": team_name,
            "valid": False,
            "error": "No organization configuration found",
        }

    # Parse org config
    try:
        org_config = OrganizationConfig.model_validate(org_config_data)
    except Exception as e:
        if not is_json_mode():
            console.print(
                create_warning_panel(
                    "Invalid Org Config",
                    f"Organization configuration is invalid: {e}",
                    "Run 'scc org update' to refresh your configuration",
                )
            )
        return {
            "team": team_name,
            "valid": False,
            "error": f"Invalid org config: {e}",
        }

    # Resolve effective config (validates team exists, trust, security)
    try:
        effective = resolve_effective_config(org_config, team_name)
    except TeamNotFoundError as e:
        if not is_json_mode():
            console.print(
                create_warning_panel(
                    "Team Not Found",
                    f"Team '{team_name}' not found in org config.",
                    f"Available teams: {', '.join(e.available_teams[:5])}",
                )
            )
        return {
            "team": team_name,
            "valid": False,
            "error": f"Team not found: {team_name}",
            "available_teams": e.available_teams,
        }
    except TrustViolationError as e:
        if not is_json_mode():
            console.print(
                create_warning_panel(
                    "Trust Violation",
                    f"Team configuration violates trust policy: {e.violation}",
                    "Check team config_source and trust grants in org config",
                )
            )
        return {
            "team": team_name,
            "valid": False,
            "error": f"Trust violation: {e.violation}",
            "team_name": e.team_name,
        }
    except ConfigFetchError as e:
        if not is_json_mode():
            console.print(
                create_warning_panel(
                    "Config Fetch Failed",
                    f"Failed to fetch config for team '{e.team_id}' from {e.source_type}",
                    str(e),  # Includes remediation hint
                )
            )
        return {
            "team": team_name,
            "valid": False,
            "error": str(e),
            "source_type": e.source_type,
            "source_url": e.source_url,
        }

    # Determine overall validity
    is_valid = not effective.has_security_violations

    # Human output
    if not is_json_mode():
        _render_validation_result(effective, verbose)

    # Build JSON response
    response: dict[str, Any] = {
        "team": team_name,
        "valid": is_valid,
        "is_federated": effective.is_federated,
        "enabled_plugins_count": effective.plugin_count,
        "blocked_plugins_count": len(effective.blocked_plugins),
        "disabled_plugins_count": len(effective.disabled_plugins),
        "not_allowed_plugins_count": len(effective.not_allowed_plugins),
    }

    # Add federation metadata
    if effective.is_federated:
        response["config_source"] = effective.source_description
        if effective.config_commit_sha:
            response["config_commit_sha"] = effective.config_commit_sha
        if effective.config_etag:
            response["config_etag"] = effective.config_etag

    # Add cache status
    if effective.used_cached_config:
        response["used_cached_config"] = True
        response["cache_is_stale"] = effective.cache_is_stale
        if effective.staleness_warning:
            response["staleness_warning"] = effective.staleness_warning

    # Add verbose details
    if verbose or json_output or pretty:
        response["enabled_plugins"] = sorted(effective.enabled_plugins)
        response["blocked_plugins"] = [
            {"plugin_id": bp.plugin_id, "reason": bp.reason, "pattern": bp.pattern}
            for bp in effective.blocked_plugins
        ]
        response["disabled_plugins"] = effective.disabled_plugins
        response["not_allowed_plugins"] = effective.not_allowed_plugins
        response["extra_marketplaces"] = effective.extra_marketplaces

    return response


def _render_validation_result(effective: EffectiveConfig, verbose: bool) -> None:
    """Render validation result to terminal.

    Args:
        effective: Resolved effective configuration
        verbose: Whether to show detailed output
    """
    console.print()

    # Header with validation status
    if effective.has_security_violations:
        status = "[red]FAILED[/red]"
        border_style = "red"
    else:
        status = "[green]PASSED[/green]"
        border_style = "green"

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column()

    # Basic info
    grid.add_row("Status:", status)
    grid.add_row(
        "Mode:", "[cyan]federated[/cyan]" if effective.is_federated else "[dim]inline[/dim]"
    )

    if effective.is_federated:
        grid.add_row("Config Source:", effective.source_description)
        if effective.config_commit_sha:
            grid.add_row("Commit SHA:", effective.config_commit_sha[:8])

    # Cache status
    if effective.used_cached_config:
        cache_status = (
            "[yellow]stale[/yellow]" if effective.cache_is_stale else "[green]fresh[/green]"
        )
        grid.add_row("Cache:", cache_status)
        if effective.staleness_warning:
            grid.add_row("", f"[dim]{effective.staleness_warning}[/dim]")

    grid.add_row("", "")

    # Plugin summary
    grid.add_row("Enabled Plugins:", f"[green]{effective.plugin_count}[/green]")
    if effective.blocked_plugins:
        grid.add_row("Blocked Plugins:", f"[red]{len(effective.blocked_plugins)}[/red]")
    if effective.disabled_plugins:
        grid.add_row("Disabled Plugins:", f"[yellow]{len(effective.disabled_plugins)}[/yellow]")
    if effective.not_allowed_plugins:
        grid.add_row("Not Allowed:", f"[yellow]{len(effective.not_allowed_plugins)}[/yellow]")

    # Verbose details
    if verbose:
        grid.add_row("", "")
        if effective.enabled_plugins:
            grid.add_row("[bold]Enabled:[/bold]", "")
            for plugin in sorted(effective.enabled_plugins):
                grid.add_row("", f"  [green]✓[/green] {plugin}")

        if effective.blocked_plugins:
            grid.add_row("[bold]Blocked:[/bold]", "")
            for bp in effective.blocked_plugins:
                grid.add_row("", f"  [red]✗[/red] {bp.plugin_id}")
                grid.add_row("", f"    [dim]Reason: {bp.reason}[/dim]")
                grid.add_row("", f"    [dim]Pattern: {bp.pattern}[/dim]")

        if effective.disabled_plugins:
            grid.add_row("[bold]Disabled:[/bold]", "")
            for plugin in effective.disabled_plugins:
                grid.add_row("", f"  [yellow]○[/yellow] {plugin}")

        if effective.not_allowed_plugins:
            grid.add_row("[bold]Not Allowed:[/bold]", "")
            for plugin in effective.not_allowed_plugins:
                grid.add_row("", f"  [yellow]○[/yellow] {plugin}")

    panel = Panel(
        grid,
        title=f"[bold cyan]Team Validation: {effective.team_id}[/bold cyan]",
        border_style=border_style,
        padding=(1, 2),
    )
    console.print(panel)

    # Hint
    if not verbose and (
        effective.blocked_plugins or effective.disabled_plugins or effective.not_allowed_plugins
    ):
        console.print()
        console.print("[dim]Use --verbose for detailed plugin information[/dim]")

    console.print()
