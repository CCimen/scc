"""Define team management commands for SCC CLI.

Provide structured team management:
- scc team list      - List available teams
- scc team current   - Show current team
- scc team switch    - Switch to a different team (interactive picker)
- scc team info      - Show detailed team information
- scc team validate  - Validate team configuration (plugins, security, cache)

All commands support --json output with proper envelopes.

team_list and team_info live in team_info.py; team_validate lives in
team_validate.py. This module keeps display helpers, federation helpers,
team_app definition, team_callback, team_switch, and team_current, and
re-exports public names for backward compatibility.
"""

import json
from pathlib import Path
from typing import Any

import typer

from .. import config, teams
from ..cli_common import console, handle_errors
from ..core.constants import CURRENT_SCHEMA_VERSION
from ..json_command import json_command
from ..kinds import Kind
from ..marketplace.team_fetch import TeamFetchResult, fetch_team_config
from ..output_mode import is_json_mode, print_human
from ..panels import create_error_panel, create_success_panel
from ..ui.gate import InteractivityContext
from ..ui.picker import TeamSwitchRequested, pick_team
from ..validate import validate_team_config
from .team_info import team_info as _team_info_fn
from .team_info import team_list as _team_list_fn
from .team_validate import team_validate as _team_validate_fn

# ═══════════════════════════════════════════════════════════════════════════════
# Display Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _format_plugins_for_display(plugins: list[str], max_display: int = 2) -> str:
    """Format a list of plugins for table/summary display."""
    if not plugins:
        return "-"

    if len(plugins) <= max_display:
        names = [p.split("@")[0] for p in plugins]
        return ", ".join(names)
    else:
        names = [p.split("@")[0] for p in plugins[:max_display]]
        remaining = len(plugins) - max_display
    return f"{', '.join(names)} +{remaining} more"


def _looks_like_path(value: str) -> bool:
    """Best-effort detection for file-like inputs."""
    return any(token in value for token in ("/", "\\", "~", ".json", ".jsonc", ".json5"))


def _validate_team_config_file(source: str, verbose: bool) -> dict[str, Any]:
    """Validate a team config file against the bundled schema."""
    path = Path(source).expanduser()
    if not path.exists():
        if not is_json_mode():
            console.print(
                create_error_panel(
                    "File Not Found",
                    f"Cannot find team config file: {source}",
                )
            )
        return {
            "mode": "file",
            "source": source,
            "valid": False,
            "error": f"File not found: {source}",
        }

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        if not is_json_mode():
            console.print(
                create_error_panel(
                    "Invalid JSON",
                    f"Failed to parse JSON: {exc}",
                )
            )
        return {
            "mode": "file",
            "source": str(path),
            "valid": False,
            "error": f"Invalid JSON: {exc}",
        }

    errors = validate_team_config(data)
    is_valid = not errors

    if not is_json_mode():
        if is_valid:
            console.print(
                create_success_panel(
                    "Validation Passed",
                    {
                        "Source": str(path),
                        "Schema Version": CURRENT_SCHEMA_VERSION,
                        "Status": "Valid",
                    },
                )
            )
        else:
            console.print(
                create_error_panel(
                    "Validation Failed",
                    "\n".join(f"• {e}" for e in errors),
                )
            )

    response: dict[str, Any] = {
        "mode": "file",
        "source": str(path),
        "valid": is_valid,
    }
    if "schema_version" in data:
        response["schema_version"] = data.get("schema_version")
    if errors:
        response["errors"] = errors
    if verbose and "errors" not in response:
        response["errors"] = []
    return response


# ═══════════════════════════════════════════════════════════════════════════════
# Federation Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _get_config_source_from_raw(
    org_config: dict[str, Any] | None, team_name: str
) -> dict[str, Any] | None:
    """Extract config_source from raw org_config dict for a team."""
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
    """Parse config_source dict into ConfigSource model."""
    from ..marketplace.schema import (
        ConfigSourceGit,
        ConfigSourceGitHub,
        ConfigSourceURL,
    )

    source_type = raw_source.get("source")
    if source_type == "github":
        return ConfigSourceGitHub.model_validate(raw_source)
    if source_type == "git":
        return ConfigSourceGit.model_validate(raw_source)
    if source_type == "url":
        return ConfigSourceURL.model_validate(raw_source)
    raise ValueError(f"Unknown config_source type: {source_type}")


def _fetch_federated_team_config(
    org_config: dict[str, Any] | None, team_name: str
) -> TeamFetchResult | None:
    """Fetch team config if team is federated, return None if inline."""
    raw_source = _get_config_source_from_raw(org_config, team_name)
    if raw_source is None:
        return None

    try:
        config_source = _parse_config_source(raw_source)
        return fetch_team_config(config_source, team_name)
    except ValueError:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Team App Definition
# ═══════════════════════════════════════════════════════════════════════════════

team_app = typer.Typer(
    name="team",
    help="Team profile management",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
    invoke_without_command=True,
)


@team_app.callback(invoke_without_command=True)
def team_callback(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full descriptions"),
    sync: bool = typer.Option(False, "--sync", "-s", help="Sync team configs from organization"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON envelope"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON"),
) -> None:
    """List teams by default."""
    if ctx.invoked_subcommand is None:
        team_list(verbose=verbose, sync=sync, json_output=json_output, pretty=pretty)


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
    """Show the currently selected team profile."""
    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    current = cfg.get("selected_profile")

    if not current:
        print_human(
            "[yellow]No team currently selected.[/yellow]\n"
            "[dim]Use 'scc team switch <name>' to select a team[/dim]"
        )
        return {"team": None, "profile": None}

    details = teams.get_team_details(current, org_config)

    if not details:
        print_human(
            f"[yellow]Current team '{current}' not found in configuration.[/yellow]\n"
            "[dim]Run 'scc team list --sync' to refresh[/dim]"
        )
        return {"team": current, "profile": None, "error": "team_not_found"}

    print_human(f"[bold cyan]Current team:[/bold cyan] {current}")
    if details.get("description"):
        print_human(f"[dim]{details['description']}[/dim]")
    plugins = details.get("plugins", [])
    if plugins:
        print_human(f"[dim]Plugins: {_format_plugins_for_display(plugins)}[/dim]")

    return {
        "team": current,
        "profile": {
            "name": details.get("name"),
            "description": details.get("description"),
            "plugins": plugins,
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
    """Switch to a different team profile."""
    cfg = config.load_user_config()
    org_config = config.load_cached_org_config()

    available_teams = teams.list_teams(org_config)

    if not available_teams:
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

    current = cfg.get("selected_profile")

    resolved_name: str | None = team_name

    if resolved_name is None:
        ctx = InteractivityContext.create(
            json_mode=is_json_mode(),
            no_interactive=non_interactive,
        )

        if ctx.allows_prompt():
            try:
                selected_team = pick_team(available_teams, current_team=current)
                if selected_team is None:
                    return {
                        "success": False,
                        "cancelled": True,
                        "previous": current,
                        "current": None,
                    }
                resolved_name = selected_team["name"]
            except TeamSwitchRequested:
                return {"success": False, "cancelled": True, "previous": current, "current": None}
        else:
            raise typer.BadParameter(
                "Team name required in non-interactive mode. "
                f"Available: {', '.join(t['name'] for t in available_teams)}"
            )

    if resolved_name is None:
        return {
            "success": False,
            "error": "team_not_selected",
            "previous": current,
            "current": None,
        }

    # Validate team exists
    team_names = [t["name"] for t in available_teams]
    if resolved_name not in team_names:
        print_human(
            f"[red]Team '{resolved_name}' not found.[/red]\n"
            f"[dim]Available: {', '.join(team_names)}[/dim]"
        )
        return {"success": False, "error": "team_not_found", "team": resolved_name}

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

    details = teams.get_team_details(resolved_name, org_config)
    if details:
        description = details.get("description")
        plugins = details.get("plugins", [])
        marketplace = details.get("marketplace") or "default"
        if description:
            print_human(f"[dim]Description:[/dim] {description}")
        print_human(f"[dim]Plugins:[/dim] {_format_plugins_for_display(plugins)}")
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
# Register extracted commands on team_app
# ═══════════════════════════════════════════════════════════════════════════════

# Wrap with decorators and register
_team_list_cmd = team_app.command("list")(
    json_command(Kind.TEAM_LIST)(handle_errors(_team_list_fn))
)
_team_info_cmd = team_app.command("info")(
    json_command(Kind.TEAM_INFO)(handle_errors(_team_info_fn))
)
_team_validate_cmd = team_app.command("validate")(
    json_command(Kind.TEAM_VALIDATE)(handle_errors(_team_validate_fn))
)

# Keep a module-level reference for team_callback's delegation
team_list = _team_list_fn
