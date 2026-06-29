"""Team validation command and rendering.

Extracted from team.py to reduce module size. Contains:
- team_validate: validates team configuration (plugins, security, cache)
- _render_validation_result: renders validation result to terminal

These are plain functions, registered on team_app by team.py.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.panel import Panel
from rich.table import Table

from .. import config
from ..cli_common import console
from ..marketplace.compute import TeamNotFoundError
from ..marketplace.resolve import ConfigFetchError, MarketplaceResolution, resolve_effective_config
from ..marketplace.schema import OrganizationConfig, normalize_org_config_data
from ..marketplace.trust import TrustViolationError
from ..output_mode import is_json_mode
from ..panels import create_warning_panel


def _validation_error_response(
    *,
    team_name: str | None,
    title: str,
    message: str,
    error: str,
    hint: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not is_json_mode():
        console.print(create_warning_panel(title, message, hint or ""))

    response: dict[str, Any] = {
        "mode": "team",
        "team": team_name,
        "valid": False,
        "error": error,
    }
    if extra:
        response.update(extra)
    return response


def _validation_success_response(
    *,
    effective: MarketplaceResolution,
    team_name: str,
    verbose: bool,
    json_output: bool,
    pretty: bool,
) -> dict[str, Any]:
    if not is_json_mode():
        _render_validation_result(effective, verbose)

    response: dict[str, Any] = {
        "mode": "team",
        "team": team_name,
        "valid": not effective.has_security_violations,
        "is_federated": effective.is_federated,
        "enabled_plugins_count": effective.plugin_count,
        "blocked_plugins_count": len(effective.blocked_plugins),
        "disabled_plugins_count": len(effective.disabled_plugins),
        "not_allowed_plugins_count": len(effective.not_allowed_plugins),
    }

    if effective.is_federated:
        response["config_source"] = effective.source_description
        if effective.config_commit_sha:
            response["config_commit_sha"] = effective.config_commit_sha
        if effective.config_etag:
            response["config_etag"] = effective.config_etag

    if effective.used_cached_config:
        response["used_cached_config"] = True
        response["cache_is_stale"] = effective.cache_is_stale
        if effective.staleness_warning:
            response["staleness_warning"] = effective.staleness_warning

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


def team_validate(
    team_name: str | None = typer.Argument(
        None, help="Team name to validate (defaults to current)"
    ),
    file: str | None = typer.Option(
        None, "--file", "-f", help="Path to a team config file to validate"
    ),
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

    Use --file to validate a local team config file against the schema.
    Use --verbose to see detailed validation information.
    """
    from .team import _looks_like_path, _validate_team_config_file

    if file and team_name:
        return _validation_error_response(
            team_name=team_name,
            title="Conflicting Inputs",
            message="Use either TEAM_NAME or --file, not both.",
            hint="Examples: scc team validate backend | scc team validate --file team.json",
            error="Conflicting inputs: provide TEAM_NAME or --file, not both",
        )

    # File validation mode (explicit or detected)
    if file or (team_name and _looks_like_path(team_name)):
        source = file or team_name or ""
        return _validate_team_config_file(source, verbose)

    # Default to current team if omitted
    if not team_name:
        cfg = config.load_user_config()
        team_name = cfg.get("selected_profile")
        if not team_name:
            return _validation_error_response(
                team_name=None,
                title="No Team Selected",
                message="No team provided and no current team is selected.",
                hint="Run 'scc team list' or 'scc team switch <team>' to select one.",
                error="No team selected",
            )

    org_config_data = config.load_cached_org_config()
    if not org_config_data:
        return _validation_error_response(
            team_name=team_name,
            title="No Org Config",
            message="No organization configuration found.",
            hint="Run 'scc setup' to configure your organization",
            error="No organization configuration found",
        )

    # Parse org config
    try:
        org_config = OrganizationConfig.model_validate(normalize_org_config_data(org_config_data))
    except Exception as e:
        return _validation_error_response(
            team_name=team_name,
            title="Invalid Org Config",
            message=f"Organization configuration is invalid: {e}",
            hint="Run 'scc org update' to refresh your configuration",
            error=f"Invalid org config: {e}",
        )

    # Resolve effective config
    assert team_name is not None
    try:
        effective = resolve_effective_config(org_config, team_name)
    except TeamNotFoundError as e:
        return _validation_error_response(
            team_name=team_name,
            title="Team Not Found",
            message=f"Team '{team_name}' not found in org config.",
            hint=f"Available teams: {', '.join(e.available_teams[:5])}",
            error=f"Team not found: {team_name}",
            extra={"available_teams": e.available_teams},
        )
    except TrustViolationError as e:
        return _validation_error_response(
            team_name=team_name,
            title="Trust Violation",
            message=f"Team configuration violates trust policy: {e.violation}",
            hint="Check team config_source and trust grants in org config",
            error=f"Trust violation: {e.violation}",
            extra={"team_name": e.team_name},
        )
    except ConfigFetchError as e:
        return _validation_error_response(
            team_name=team_name,
            title="Config Fetch Failed",
            message=f"Failed to fetch config for team '{e.team_id}' from {e.source_type}",
            hint=str(e),
            error=str(e),
            extra={"source_type": e.source_type, "source_url": e.source_url},
        )

    return _validation_success_response(
        effective=effective,
        team_name=team_name,
        verbose=verbose,
        json_output=json_output,
        pretty=pretty,
    )


def _render_validation_result(effective: MarketplaceResolution, verbose: bool) -> None:
    """Render validation result to terminal."""
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
