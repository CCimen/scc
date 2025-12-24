"""Provide CLI commands for plugin audit functionality.

Audit installed Claude Code plugins via the `scc audit plugins` command,
including manifest validation and MCP server/hooks discovery.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scc_cli.audit.reader import audit_all_plugins
from scc_cli.constants import AGENT_CONFIG_DIR
from scc_cli.models.plugin_audit import (
    AuditOutput,
    ManifestStatus,
    PluginAuditResult,
)

console = Console()

# Create the audit sub-app
audit_app = typer.Typer(
    name="audit",
    help="Audit installed plugins and configurations.",
    no_args_is_help=True,
)


def get_claude_dir() -> Path:
    """Get the Claude Code directory path."""
    return Path.home() / AGENT_CONFIG_DIR


def format_status(status: str) -> str:
    """Format status with color for Rich output."""
    if status == "clean":
        return "[dim]clean[/dim]"
    elif status == "parsed":
        return "[green]parsed[/green]"
    elif status == "malformed":
        return "[red]malformed[/red]"
    elif status == "unreadable":
        return "[yellow]unreadable[/yellow]"
    elif status == "not installed":
        return "[dim]not installed[/dim]"
    return status


def render_human_output(output: AuditOutput) -> None:
    """Render audit output in human-readable format."""
    # Header
    console.print()
    header_body = Text()
    header_body.append("Plugin Audit Report", style="bold")
    header_body.append("\n")
    header_body.append(f"Discovered {output.total_plugins} plugin(s)", style="dim")
    console.print(
        Panel(
            header_body,
            border_style="cyan",
            padding=(0, 1),
        )
    )
    console.print()

    if output.total_plugins == 0:
        console.print("[dim]No plugins installed.[/dim]")
        console.print()
        _print_disclaimer()
        return

    # Create table for plugins with rounded borders
    table = Table(
        show_header=True,
        header_style="bold",
        box=box.ROUNDED,
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Plugin", style="cyan", no_wrap=True)
    table.add_column("Version", style="dim")
    table.add_column("Status", justify="center")
    table.add_column("MCP", justify="right", style="green")
    table.add_column("Hooks", justify="right", style="yellow")

    for plugin in output.plugins:
        # Format MCP server count
        mcp_count = 0
        if plugin.manifests and plugin.manifests.mcp.status == ManifestStatus.PARSED:
            mcp_count = len(plugin.manifests.mcp_servers)
        mcp_display = str(mcp_count) if mcp_count > 0 else "[dim]-[/dim]"

        # Format hooks count
        hooks_count = 0
        if plugin.manifests and plugin.manifests.hooks.status == ManifestStatus.PARSED:
            hooks_count = len(plugin.manifests.hooks_info)
        hooks_display = str(hooks_count) if hooks_count > 0 else "[dim]-[/dim]"

        table.add_row(
            plugin.plugin_name,
            plugin.version,
            format_status(plugin.status_summary),
            mcp_display,
            hooks_display,
        )

    console.print(table)
    console.print()

    # Show details for plugins with declarations
    for plugin in output.plugins:
        if plugin.manifests and plugin.manifests.has_declarations:
            _render_plugin_details(plugin)

    # Show problems in a warning panel
    problem_plugins = [p for p in output.plugins if p.has_ci_failures]
    if problem_plugins:
        _render_problems_panel(problem_plugins)

    # Disclaimer
    _print_disclaimer()


def _render_plugin_details(plugin: PluginAuditResult) -> None:
    """Render details for a plugin with declarations."""
    if not plugin.manifests:
        return

    # Create a details grid
    details = Text()
    details.append(f"  {plugin.plugin_name}", style="bold cyan")
    details.append("\n")

    # Show MCP servers
    if plugin.manifests.mcp_servers:
        details.append("  MCP Servers: ", style="dim")
        server_names = [s.name for s in plugin.manifests.mcp_servers]
        details.append(", ".join(server_names), style="green")
        details.append("\n")

    # Show hooks
    if plugin.manifests.hooks_info:
        details.append("  Hooks: ", style="dim")
        hook_events = [h.event for h in plugin.manifests.hooks_info]
        details.append(", ".join(hook_events), style="yellow")
        details.append("\n")

    console.print(details)


def _render_problems_panel(plugins: list[PluginAuditResult]) -> None:
    """Render a warning panel for all plugins with CI failures."""
    problems_text = Text()

    for i, plugin in enumerate(plugins):
        if not plugin.manifests:
            continue

        if i > 0:
            problems_text.append("\n")

        problems_text.append(f"⚠ {plugin.plugin_name}", style="bold red")
        problems_text.append("\n")

        # Check MCP manifest
        if plugin.manifests.mcp.has_problems:
            mcp = plugin.manifests.mcp
            if mcp.status == ManifestStatus.MALFORMED and mcp.error:
                problems_text.append("  .mcp.json: ", style="dim")
                problems_text.append(f"malformed ({mcp.error.format()})", style="red")
                problems_text.append("\n")
            elif mcp.status == ManifestStatus.UNREADABLE:
                problems_text.append("  .mcp.json: ", style="dim")
                problems_text.append(f"unreadable ({mcp.error_message})", style="yellow")
                problems_text.append("\n")

        # Check hooks manifest
        if plugin.manifests.hooks.has_problems:
            hooks = plugin.manifests.hooks
            if hooks.status == ManifestStatus.MALFORMED and hooks.error:
                problems_text.append("  hooks/hooks.json: ", style="dim")
                problems_text.append(f"malformed ({hooks.error.format()})", style="red")
                problems_text.append("\n")
            elif hooks.status == ManifestStatus.UNREADABLE:
                problems_text.append("  hooks/hooks.json: ", style="dim")
                problems_text.append(f"unreadable ({hooks.error_message})", style="yellow")
                problems_text.append("\n")

    console.print(
        Panel(
            problems_text,
            title="[bold yellow]Manifest Problems[/bold yellow]",
            border_style="yellow",
            padding=(0, 1),
        )
    )
    console.print()


def _print_disclaimer() -> None:
    """Print the informational disclaimer."""
    console.print("[dim]ℹ Informational only; SCC does not enforce plugin internals.[/dim]")
    console.print()


def render_json_output(output: AuditOutput) -> None:
    """Render audit output as JSON."""
    data = output.to_dict()
    console.print(json.dumps(data, indent=2))


@audit_app.command(name="plugins")
def audit_plugins_cmd(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON with schemaVersion for CI integration.",
    ),
) -> None:
    """Audit installed Claude Code plugins.

    Shows manifest status, MCP servers, and hooks for all installed plugins.

    Exit codes:
    - 0: All plugins parsed successfully (or no plugins installed)
    - 1: One or more plugins have malformed or unreadable manifests
    """
    claude_dir = get_claude_dir()
    output = audit_all_plugins(claude_dir)

    if as_json:
        render_json_output(output)
    else:
        render_human_output(output)

    # Exit with appropriate code for CI
    raise typer.Exit(code=output.exit_code)
