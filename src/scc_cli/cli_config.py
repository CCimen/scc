"""Provide CLI commands for managing teams, configuration, and setup."""

from pathlib import Path

import typer

from . import config, profiles, setup
from .cli_common import console, handle_errors
from .exit_codes import EXIT_USAGE
from .panels import create_error_panel, create_info_panel
from .source_resolver import ResolveError, resolve_source
from .stores.exception_store import RepoStore, UserStore
from .utils.ttl import format_relative

# ─────────────────────────────────────────────────────────────────────────────
# Config App
# ─────────────────────────────────────────────────────────────────────────────

config_app = typer.Typer(
    name="config",
    help="Manage configuration and team profiles.",
    no_args_is_help=False,
)


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
    """Run initial setup wizard.

    Examples:
        scc setup                                    # Interactive wizard
        scc setup --standalone                       # Standalone mode
        scc setup --org github:acme/config --profile dev  # Non-interactive with shorthand
        scc setup --org-url <url> --team dev         # Non-interactive (legacy)
    """
    if reset:
        setup.reset_setup(console)
        return

    # Handle --profile/--team alias (prefer --profile)
    selected_profile = profile or team

    # Handle --org/--org-url (prefer --org)
    resolved_url: str | None = None
    if org:
        # Resolve shorthand to URL
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

    # Non-interactive mode if org source or standalone specified
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

    # Run the setup wizard (--quick flag is a no-op for now, wizard handles all cases)
    setup.run_setup_wizard(console)


# ─────────────────────────────────────────────────────────────────────────────
# Config Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def config_cmd(
    action: str = typer.Argument(None, help="Action: set, get, show, edit, explain"),
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
) -> None:
    """View or edit configuration.

    Examples:
        scc config --show                    # Show all config
        scc config get selected_profile      # Get specific key
        scc config set hooks.enabled true    # Set a value
        scc config --edit                    # Open in editor
        scc config explain                   # Explain effective config
        scc config explain --field plugins   # Explain only plugins
    """
    # Handle action-based commands
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
        _config_explain(field_filter=field, workspace_path=workspace)
        return

    # Handle --show and --edit flags
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

    # Parse dotted key path (e.g., "hooks.enabled")
    keys = key.split(".")
    obj = cfg
    for k in keys[:-1]:
        if k not in obj:
            obj[k] = {}
        obj = obj[k]

    # Parse value (handle booleans and numbers)
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

    # Navigate dotted key path
    keys = key.split(".")
    obj = cfg
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            console.print(f"[yellow]Key '{key}' not found[/yellow]")
            return

    # Display value
    if isinstance(obj, dict):
        console.print_json(data=obj)
    else:
        console.print(str(obj))


def _config_explain(field_filter: str | None = None, workspace_path: str | None = None) -> None:
    """Explain the effective configuration with source attribution.

    Shows:
    - Effective config values and where they came from
    - Blocked items and the patterns that blocked them
    - Denied additions and why they were denied
    """
    # Load org config
    org_config = config.load_cached_org_config()
    if not org_config:
        console.print("[red]No organization config found. Run 'scc setup' first.[/red]")
        raise typer.Exit(1)

    # Get selected profile/team
    team = config.get_selected_profile()
    if not team:
        console.print("[red]No team selected. Run 'scc team switch <name>' first.[/red]")
        raise typer.Exit(1)

    # Determine workspace path
    ws_path = Path(workspace_path) if workspace_path else Path.cwd()

    # Compute effective config
    effective = profiles.compute_effective_config(
        org_config=org_config,
        team_name=team,
        workspace_path=ws_path,
    )

    # Build output
    console.print(
        create_info_panel(
            "Effective Configuration",
            f"Organization: {org_config.get('organization', {}).get('name', 'Unknown')}",
            f"Team: {team}",
        )
    )
    console.print()

    # Show decisions (config values with source attribution)
    _render_config_decisions(effective, field_filter)

    # Show blocked items
    if effective.blocked_items and (not field_filter or field_filter == "blocked"):
        _render_blocked_items(effective.blocked_items)

    # Show denied additions
    if effective.denied_additions and (not field_filter or field_filter == "denied"):
        _render_denied_additions(effective.denied_additions)

    # Show active exceptions
    if not field_filter or field_filter == "exceptions":
        expired_count = _render_active_exceptions()
        if expired_count > 0:
            console.print(
                f"[dim]Note: {expired_count} expired local overrides "
                f"(run `scc exceptions cleanup`)[/dim]"
            )
            console.print()


def _render_config_decisions(effective: profiles.EffectiveConfig, field_filter: str | None) -> None:
    """Render config decisions grouped by field."""
    # Group decisions by field
    by_field: dict[str, list[profiles.ConfigDecision]] = {}
    for decision in effective.decisions:
        field = decision.field.split(".")[0]  # Get top-level field
        if field_filter and field != field_filter:
            continue
        if field not in by_field:
            by_field[field] = []
        by_field[field].append(decision)

    # Also show effective values even if no explicit decisions
    if not field_filter or field_filter == "plugins":
        console.print("[bold cyan]Plugins[/bold cyan]")
        if effective.plugins:
            for plugin in sorted(effective.plugins):
                # Find decision for this plugin
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
            # Plugin trust model note
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
        # Find decision for timeout
        timeout_decision = next(
            (d for d in effective.decisions if "timeout" in d.field.lower()),
            None,
        )
        if timeout_decision:
            console.print(f"  timeout_hours: {timeout} [dim](from {timeout_decision.source})[/dim]")
        else:
            console.print(f"  timeout_hours: {timeout} [dim](default)[/dim]")
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
                # Find decision for this server
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


def _render_blocked_items(blocked_items: list[profiles.BlockedItem]) -> None:
    """Render blocked items with patterns and fix-it commands."""
    from scc_cli.utils.fixit import generate_policy_exception_command

    console.print("[bold red]Blocked Items[/bold red]")
    for item in blocked_items:
        console.print(
            f"  [red]✗[/red] [bold]{item.item}[/bold] [dim](blocked by pattern '{item.blocked_by}' from {item.source})[/dim]"
        )
        # Infer target type from source or pattern
        target_type = _infer_target_type(item.item, item.source)
        cmd = generate_policy_exception_command(item.item, target_type)
        console.print("      [dim]To request exception (requires PR):[/dim]")
        console.print(f"      [cyan]{cmd}[/cyan]")
    console.print()


def _infer_target_type(item: str, source: str) -> str:
    """Infer target type from item name or source context.

    Args:
        item: The item name (plugin, server, image)
        source: The source context (e.g., "org.security")

    Returns:
        One of "plugin", "mcp_server", or "base_image"
    """
    # Check for common patterns
    item_lower = item.lower()

    # Image patterns (contains : or @ for tags/digests, or common registries)
    if (
        ":" in item
        or "@" in item
        or any(reg in item_lower for reg in ["docker", "ghcr.io", "registry", ".io/", ".com/"])
    ):
        return "base_image"

    # MCP server patterns (often have -api, -server, -mcp suffix or look like URLs)
    if any(pattern in item_lower for pattern in ["-api", "-server", "-mcp", "/"]):
        return "mcp_server"

    # Default to plugin (most common case for blocked items)
    return "plugin"


def _render_denied_additions(denied_additions: list[profiles.DelegationDenied]) -> None:
    """Render denied additions with reasons and fix-it commands."""
    from scc_cli.utils.fixit import generate_unblock_command

    console.print("[bold yellow]Denied Additions[/bold yellow]")
    for denied in denied_additions:
        console.print(
            f"  [yellow]⚠[/yellow] [bold]{denied.item}[/bold] [dim](requested by {denied.requested_by}: {denied.reason})[/dim]"
        )
        # Infer target type from item name
        target_type = _infer_target_type(denied.item, denied.requested_by)
        cmd = generate_unblock_command(denied.item, target_type)
        console.print("      [dim]To unblock locally:[/dim]")
        console.print(f"      [cyan]{cmd}[/cyan]")
    console.print()


def _render_active_exceptions() -> int:
    """Render active exceptions from user and repo stores.

    Returns the count of expired exceptions found (for user notification).
    """
    from datetime import datetime, timezone

    from .models.exceptions import Exception as SccException

    # Load exceptions from both stores
    user_store = UserStore()
    repo_store = RepoStore(Path.cwd())

    user_file = user_store.read()
    repo_file = repo_store.read()

    # Filter active exceptions
    now = datetime.now(timezone.utc)
    active: list[tuple[str, SccException]] = []  # (source, exception)
    expired_count = 0

    for exc in user_file.exceptions:
        try:
            expires = datetime.fromisoformat(exc.expires_at.replace("Z", "+00:00"))
            if expires > now:
                active.append(("user", exc))
            else:
                expired_count += 1
        except (ValueError, AttributeError):
            expired_count += 1

    for exc in repo_file.exceptions:
        try:
            expires = datetime.fromisoformat(exc.expires_at.replace("Z", "+00:00"))
            if expires > now:
                active.append(("repo", exc))
            else:
                expired_count += 1
        except (ValueError, AttributeError):
            expired_count += 1

    if not active:
        return expired_count

    console.print("[bold cyan]Active Exceptions[/bold cyan]")

    for source, exc in active:
        # Format the exception target
        targets: list[str] = []
        if exc.allow.plugins:
            targets.extend(f"plugin:{p}" for p in exc.allow.plugins)
        if exc.allow.mcp_servers:
            targets.extend(f"mcp:{s}" for s in exc.allow.mcp_servers)
        if exc.allow.base_images:
            targets.extend(f"image:{i}" for i in exc.allow.base_images)

        target_str = ", ".join(targets) if targets else "none"

        # Calculate expires_in
        try:
            expires = datetime.fromisoformat(exc.expires_at.replace("Z", "+00:00"))
            expires_in = format_relative(expires)
        except (ValueError, AttributeError):
            expires_in = "unknown"

        scope_badge = "[dim][local][/dim]" if exc.scope == "local" else "[cyan][policy][/cyan]"
        console.print(
            f"  {scope_badge} {exc.id}  {target_str}  "
            f"[dim]expires in {expires_in}[/dim]  [dim](source: {source})[/dim]"
        )

    console.print()
    return expired_count
