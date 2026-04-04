"""Provide CLI commands for managing teams, configuration, and setup.

Validation logic lives in config_validate.py; paths/exceptions in
config_inspect.py. This module keeps config_cmd, setup_cmd, _config_explain,
and small helpers.

Re-exports public names for backward compatibility.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer

from .. import config, setup
from ..application.compute_effective_config import (
    ConfigDecision,
    EffectiveConfig,
    compute_effective_config,
)
from ..cli_common import console, handle_errors
from ..core import personal_profiles
from ..core.enums import NetworkPolicy
from ..core.exit_codes import EXIT_USAGE
from ..core.network_policy import collect_proxy_env, is_more_or_equal_restrictive
from ..panels import create_error_panel, create_info_panel
from ..source_resolver import ResolveError, resolve_source

# Re-export extracted symbols for backward compatibility
from .config_inspect import _config_paths, _render_active_exceptions
from .config_validate import (
    _config_validate,
    _render_blocked_items,
    _render_denied_additions,
)

# ─────────────────────────────────────────────────────────────────────────────
# Config App
# ─────────────────────────────────────────────────────────────────────────────

config_app = typer.Typer(
    name="config",
    help="Manage configuration and team profiles.",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@dataclass(frozen=True)
class EnforcementStatusEntry:
    """Describe runtime enforcement status for a config surface."""

    surface: str
    status: str
    detail: str


# ─────────────────────────────────────────────────────────────────────────────
# Setup Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def setup_cmd(
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick setup with defaults"),
    reset: bool = typer.Option(False, "--reset", help="Reset configuration"),
    org: str | None = typer.Option(
        None,
        "--org",
        help="Organization source (URL or shorthand like github:org/repo)",
    ),
    org_url: str | None = typer.Option(
        None, "--org-url", help="Organization config URL (deprecated, use --org)"
    ),
    profile: str | None = typer.Option(None, "--profile", "-p", help="Profile/team to select"),
    team: str | None = typer.Option(
        None, "--team", "-t", help="Team profile to select (alias for --profile)"
    ),
    auth: str | None = typer.Option(None, "--auth", help="Auth spec (env:VAR or command:CMD)"),
    standalone: bool = typer.Option(
        False, "--standalone", help="Standalone mode (no organization)"
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--no-interactive",
        help="Fail fast instead of prompting for missing setup inputs",
    ),
) -> None:
    """Run initial setup wizard."""
    if reset:
        setup.reset_setup(console)
        return

    selected_profile = profile or team

    resolved_url: str | None = None
    if org:
        result = resolve_source(org)
        if isinstance(result, ResolveError):
            console.print(
                create_error_panel(
                    "Invalid Source",
                    result.message,
                    hint=result.suggestion or "",
                )
            )
            raise typer.Exit(1)
        resolved_url = result.resolved_url
    elif org_url:
        resolved_url = org_url

    if non_interactive and not (resolved_url or standalone):
        console.print(
            create_error_panel(
                "Missing Setup Inputs",
                "Non-interactive setup requires --org or --standalone.",
                hint="Provide --org <source> or use interactive setup without --non-interactive.",
            )
        )
        raise typer.Exit(EXIT_USAGE)

    if resolved_url or standalone:
        success = setup.run_non_interactive_setup(
            console,
            org_url=resolved_url,
            team=selected_profile,
            auth=auth,
            standalone=standalone,
        )
        if not success:
            raise typer.Exit(1)
        return

    setup.run_setup_wizard(console)


# ─────────────────────────────────────────────────────────────────────────────
# Config Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def config_cmd(
    action: str = typer.Argument(
        None, help="Action: set, get, show, edit, explain, validate, paths"
    ),
    key: str = typer.Argument(None, help="Config key (for set/get, e.g. hooks.enabled)"),
    value: str = typer.Argument(None, help="Value (for set only)"),
    show: bool = typer.Option(False, "--show", help="Show current config"),
    edit: bool = typer.Option(False, "--edit", help="Open config in editor"),
    field: str | None = typer.Option(
        None, "--field", help="Filter explain output to specific field (plugins, session, etc.)"
    ),
    workspace: str | None = typer.Option(
        None, "--workspace", help="Workspace path for project config (default: current directory)"
    ),
    team: str | None = typer.Option(
        None, "--team", "-t", help="Team profile to use for explain/validate"
    ),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON (paths/explain/validate)."),
    ] = False,
    show_env: Annotated[
        bool,
        typer.Option("--show-env", help="Show XDG environment variables (for paths action)."),
    ] = False,
) -> None:
    """View or edit configuration."""
    if action == "paths":
        _config_paths(json_output=json_output, show_env=show_env)
        return

    if action == "set":
        if not key or value is None:
            console.print("[red]Usage: scc config set <key> <value>[/red]")
            raise typer.Exit(1)
        _config_set(key, value)
        return

    if action == "get":
        if not key:
            console.print("[red]Usage: scc config get <key>[/red]")
            raise typer.Exit(1)
        _config_get(key)
        return

    if action == "explain":
        if json_output:
            from ..output_mode import json_command_mode, json_output_mode

            with json_output_mode(), json_command_mode():
                _config_explain(
                    field_filter=field,
                    workspace_path=workspace,
                    team_override=team,
                    json_output=True,
                )
        else:
            _config_explain(
                field_filter=field,
                workspace_path=workspace,
                team_override=team,
                json_output=False,
            )
        return
    if action == "validate":
        if json_output:
            from ..output_mode import json_command_mode, json_output_mode

            with json_output_mode(), json_command_mode():
                _config_validate(
                    workspace_path=workspace,
                    team_override=team,
                    json_output=True,
                )
        else:
            _config_validate(
                workspace_path=workspace,
                team_override=team,
                json_output=False,
            )
        return

    if show or action == "show":
        cfg = config.load_user_config()
        console.print(
            create_info_panel(
                "Configuration",
                f"Current settings loaded from {config.CONFIG_FILE}",
            )
        )
        console.print()
        console.print_json(data=cfg)
    elif edit or action == "edit":
        config.open_in_editor()
    else:
        console.print(
            create_info_panel(
                "Configuration Help",
                "Commands:\n  scc config --show     View current settings\n  scc config --edit     Edit in your editor\n  scc config get <key>  Get a specific value\n  scc config set <key> <value>  Set a value",
                f"Config location: {config.CONFIG_FILE}",
            )
        )


def _config_set(key: str, value: str) -> None:
    """Set a configuration value by dotted key path."""
    cfg = config.load_user_config()

    keys = key.split(".")
    obj = cfg
    for k in keys[:-1]:
        if k not in obj:
            obj[k] = {}
        obj = obj[k]

    parsed_value: bool | int | str
    if value.lower() == "true":
        parsed_value = True
    elif value.lower() == "false":
        parsed_value = False
    elif value.isdigit():
        parsed_value = int(value)
    else:
        parsed_value = value

    obj[keys[-1]] = parsed_value
    config.save_user_config(cfg)
    console.print(f"[green]✓ Set {key} = {parsed_value}[/green]")


def _config_get(key: str) -> None:
    """Get a configuration value by dotted key path."""
    cfg = config.load_user_config()

    keys = key.split(".")
    obj = cfg
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            console.print(f"[yellow]Key '{key}' not found[/yellow]")
            return

    if isinstance(obj, dict):
        console.print_json(data=obj)
    else:
        console.print(str(obj))


def _config_explain(
    field_filter: str | None = None,
    workspace_path: str | None = None,
    team_override: str | None = None,
    json_output: bool = False,
) -> None:
    """Explain the effective configuration with source attribution."""
    org_config = config.load_cached_org_config()
    if not org_config:
        console.print("[red]No organization config found. Run 'scc setup' first.[/red]")
        raise typer.Exit(1)

    team = team_override or config.get_selected_profile()
    if not team:
        console.print("[red]No team selected. Run 'scc team switch <name>' first.[/red]")
        raise typer.Exit(1)

    ws_path = Path(workspace_path) if workspace_path else Path.cwd()

    effective = compute_effective_config(
        org_config=org_config,
        team_name=team,
        workspace_path=ws_path,
    )

    enforcement_status = _build_enforcement_status_entries()
    enforcement_payload = _serialize_enforcement_status_entries(enforcement_status)
    warnings = _collect_advisory_warnings(
        org_config=org_config,
        team_name=team,
        workspace_path=ws_path,
        effective_network_policy=effective.network_policy,
    )

    if json_output:
        from ..output_mode import print_json
        from ..presentation.json.config_json import (
            build_config_explain_data,
            build_config_explain_envelope,
        )

        data = build_config_explain_data(
            org_config=org_config,
            team_name=team,
            effective=effective,
            enforcement_status=enforcement_payload,
            warnings=warnings,
            workspace_path=ws_path,
        )
        envelope = build_config_explain_envelope(data, warnings=warnings)
        print_json(envelope)
        return

    console.print(
        create_info_panel(
            "Effective Configuration",
            f"Organization: {org_config.get('organization', {}).get('name', 'Unknown')}",
            f"Team: {team}",
        )
    )
    console.print()

    _render_enforcement_status(enforcement_status, field_filter)
    _render_config_decisions(effective, field_filter)
    _render_personal_profile(ws_path, field_filter)

    if effective.blocked_items and (not field_filter or field_filter == "blocked"):
        _render_blocked_items(effective.blocked_items)

    if effective.denied_additions and (not field_filter or field_filter == "denied"):
        _render_denied_additions(effective.denied_additions)

    if not field_filter or field_filter == "exceptions":
        expired_count = _render_active_exceptions()
        if expired_count > 0:
            console.print(
                f"[dim]Note: {expired_count} expired local overrides "
                f"(run `scc exceptions cleanup`)[/dim]"
            )
            console.print()

    _render_advisory_warnings(warnings, field_filter)


def _build_enforcement_status_entries() -> list[EnforcementStatusEntry]:
    return [
        EnforcementStatusEntry(
            surface="Plugins",
            status="Enforced",
            detail="SCC-managed plugins are injected into runtime settings.",
        ),
        EnforcementStatusEntry(
            surface="Marketplaces",
            status="Enforced",
            detail="Managed marketplaces are materialized and injected.",
        ),
        EnforcementStatusEntry(
            surface="MCP servers (org/team/project)",
            status="Enforced",
            detail="SCC-managed MCP servers are injected after policy gates.",
        ),
        EnforcementStatusEntry(
            surface="MCP servers (.mcp.json)",
            status="Advisory",
            detail="SCC does not modify repo MCP files in v1.",
        ),
        EnforcementStatusEntry(
            surface="MCP servers (plugin-bundled)",
            status="Out of scope",
            detail="Plugins are the trust unit; block the plugin to restrict.",
        ),
        EnforcementStatusEntry(
            surface="network_policy",
            status="Partially enforced",
            detail="Proxy env injection and MCP suppression, not full egress control.",
        ),
        EnforcementStatusEntry(
            surface="safety_net policy",
            status="Enforced when enabled",
            detail="Policy is enforced by the scc-safety-net plugin.",
        ),
        EnforcementStatusEntry(
            surface="session.auto_resume",
            status="Advisory",
            detail="Accepted in config but not enforced yet.",
        ),
    ]


def _render_enforcement_status(
    entries: list[EnforcementStatusEntry], field_filter: str | None
) -> None:
    if field_filter and field_filter not in {"enforcement", "enforcement_status"}:
        return

    console.print("[bold cyan]Enforcement Status[/bold cyan]")
    for entry in entries:
        console.print(f"  {entry.surface}: {entry.status}")
        console.print(f"    [dim]{entry.detail}[/dim]")
    console.print()


def _serialize_enforcement_status_entries(
    entries: list[EnforcementStatusEntry],
) -> list[dict[str, str]]:
    return [
        {"surface": entry.surface, "status": entry.status, "detail": entry.detail}
        for entry in entries
    ]


def _collect_advisory_warnings(
    *,
    org_config: dict[str, Any],
    team_name: str,
    workspace_path: Path,
    effective_network_policy: str | None,
) -> list[str]:
    warnings: list[str] = []

    defaults_session = org_config.get("defaults", {}).get("session", {})
    team_session = org_config.get("profiles", {}).get(team_name, {}).get("session", {})
    project_config = config.read_project_config(workspace_path) or {}
    project_session = project_config.get("session", {})

    auto_resume_sources: list[str] = []
    if "auto_resume" in defaults_session:
        auto_resume_sources.append("org.defaults")
    if "auto_resume" in team_session:
        auto_resume_sources.append(f"team.{team_name}")
    if "auto_resume" in project_session:
        auto_resume_sources.append("project")

    if auto_resume_sources:
        sources = ", ".join(auto_resume_sources)
        warnings.append(
            f"session.auto_resume is advisory only and not enforced (set by {sources})."
        )

    default_network_policy = org_config.get("defaults", {}).get("network_policy")
    team_network_policy = org_config.get("profiles", {}).get(team_name, {}).get("network_policy")
    if (
        default_network_policy
        and team_network_policy
        and not is_more_or_equal_restrictive(team_network_policy, default_network_policy)
    ):
        warnings.append(
            "team network_policy is less restrictive than org default and is ignored "
            f"({team_network_policy} < {default_network_policy})."
        )

    if effective_network_policy == NetworkPolicy.WEB_EGRESS_ENFORCED.value:
        proxy_env = collect_proxy_env()
        if not proxy_env:
            warnings.append(
                "network_policy is web-egress-enforced but no proxy env vars are set "
                "(HTTP_PROXY/HTTPS_PROXY/NO_PROXY)."
            )

    return warnings


def _render_advisory_warnings(warnings: list[str], field_filter: str | None) -> None:
    if not warnings:
        return
    if field_filter and field_filter not in {"warnings", "enforcement"}:
        return

    console.print("[bold yellow]Warnings[/bold yellow]")
    for warning in warnings:
        console.print(f"  [yellow]⚠[/yellow] {warning}")
    console.print()


def _render_config_decisions(effective: EffectiveConfig, field_filter: str | None) -> None:
    """Render config decisions grouped by field."""
    by_field: dict[str, list[ConfigDecision]] = {}
    for decision in effective.decisions:
        field = decision.field.split(".")[0]
        if field_filter and field != field_filter:
            continue
        if field not in by_field:
            by_field[field] = []
        by_field[field].append(decision)

    if not field_filter or field_filter == "plugins":
        console.print("[bold cyan]Plugins[/bold cyan]")
        if effective.plugins:
            for plugin in sorted(effective.plugins):
                plugin_decision = next(
                    (d for d in effective.decisions if d.field == "plugins" and d.value == plugin),
                    None,
                )
                if plugin_decision:
                    console.print(
                        f"  [green]✓[/green] {plugin} [dim](from {plugin_decision.source})[/dim]"
                    )
                else:
                    console.print(f"  [green]✓[/green] {plugin}")
            console.print()
            console.print(
                "  [dim]Note: Plugins may bundle .mcp.json MCP servers. "
                "SCC does not inspect plugin contents; to restrict, block the plugin.[/dim]"
            )
        else:
            console.print("  [dim]None configured[/dim]")
        console.print()

    if not field_filter or field_filter == "session":
        console.print("[bold cyan]Session Config[/bold cyan]")
        timeout = effective.session_config.timeout_hours or 8
        auto_resume = effective.session_config.auto_resume
        timeout_decision = next(
            (d for d in effective.decisions if "timeout" in d.field.lower()),
            None,
        )
        auto_resume_decision = next(
            (d for d in effective.decisions if d.field == "session.auto_resume"),
            None,
        )
        if timeout_decision:
            console.print(f"  timeout_hours: {timeout} [dim](from {timeout_decision.source})[/dim]")
        else:
            console.print(f"  timeout_hours: {timeout} [dim](default)[/dim]")
        if auto_resume_decision:
            console.print(
                f"  auto_resume: {auto_resume} [dim](from {auto_resume_decision.source})[/dim]"
            )
        else:
            console.print(f"  auto_resume: {auto_resume}")
        console.print()

    if not field_filter or field_filter == "network":
        console.print("[bold cyan]Network Policy[/bold cyan]")
        policy = effective.network_policy or "default"
        policy_decision = next(
            (d for d in effective.decisions if d.field == "network_policy"),
            None,
        )
        if policy_decision:
            console.print(f"  {policy} [dim](from {policy_decision.source})[/dim]")
        else:
            console.print(f"  {policy}")
        console.print()

    if not field_filter or field_filter == "mcp_servers":
        console.print("[bold cyan]MCP Servers[/bold cyan]")
        if effective.mcp_servers:
            for server in effective.mcp_servers:
                server_decision = next(
                    (
                        d
                        for d in effective.decisions
                        if d.field == "mcp_servers" and d.value == server.name
                    ),
                    None,
                )
                server_info = f"{server.name} ({server.type})"
                if server_decision:
                    console.print(
                        f"  [green]✓[/green] {server_info} [dim](from {server_decision.source})[/dim]"
                    )
                else:
                    console.print(f"  [green]✓[/green] {server_info}")
        else:
            console.print("  [dim]None configured[/dim]")
        console.print()


def _render_personal_profile(ws_path: Path, field_filter: str | None) -> None:
    profile = personal_profiles.load_personal_profile(ws_path)
    if profile is None:
        return

    if field_filter and field_filter not in {"plugins", "mcp_servers"}:
        return

    console.print("[bold magenta]Personal Profile[/bold magenta]")
    console.print(f"  Repo: {profile.repo_id}")

    plugins = personal_profiles.extract_personal_plugins(profile)
    if not field_filter or field_filter == "plugins":
        if plugins:
            for plugin in sorted(plugins):
                console.print(f"  [green]+[/green] {plugin} [dim](personal)[/dim]")
        else:
            console.print("  [dim]No personal plugins saved[/dim]")

    if not field_filter or field_filter == "mcp_servers":
        if profile.mcp:
            console.print("  [green]+[/green] .mcp.json [dim](personal)[/dim]")
        else:
            console.print("  [dim]No personal MCP config saved[/dim]")

    console.print()
