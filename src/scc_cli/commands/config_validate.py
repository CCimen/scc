"""Config validation command.

Extracted from config.py to reduce module size. Contains:
- _config_validate: validates .scc.yaml project configuration
- _render_blocked_items: renders blocked items with fix-it commands
- _render_denied_additions: renders denied additions with reasons
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from .. import config
from ..application.compute_effective_config import (
    BlockedItem,
    DelegationDenied,
    compute_effective_config,
)
from ..cli_common import console
from ..core.enums import RequestSource
from ..panels import create_error_panel, create_success_panel
from ..ports.config_models import NormalizedOrgConfig


def _config_validate(
    *,
    workspace_path: str | None,
    team_override: str | None,
    json_output: bool,
) -> None:
    from ..core.exit_codes import EXIT_CONFIG, EXIT_GOVERNANCE, EXIT_SUCCESS
    from ..json_output import build_envelope
    from ..kinds import Kind
    from ..output_mode import print_json

    errors: list[str] = []
    warnings: list[str] = []

    org_config = config.load_cached_org_config()
    if not org_config:
        errors.append("No organization config found. Run 'scc setup' first.")

    team = team_override or config.get_selected_profile()
    if not team:
        errors.append("No team selected. Run 'scc team switch <name>' first.")

    ws_path = Path(workspace_path) if workspace_path else Path.cwd()
    config_file = ws_path / config.PROJECT_CONFIG_FILE

    project_config: dict[str, Any] | None = None
    if not errors and team and org_config:
        profiles = org_config.get("profiles", {})
        if team not in profiles:
            errors.append(f"Team '{team}' not found in org config.")

    if not errors:
        try:
            project_config = config.read_project_config(ws_path)
        except ValueError as exc:
            errors.append(str(exc))

    if not errors and project_config is None:
        if not config_file.exists():
            errors.append(f"No .scc.yaml found at {config_file}")
        else:
            errors.append(f"{config_file} is empty.")

    blocked_items: list[dict[str, Any]] = []
    denied_additions: list[dict[str, Any]] = []
    unknown_keys: list[str] = []

    if not errors and project_config and org_config:
        allowed_keys = {"additional_plugins", "additional_mcp_servers", "session"}
        unknown_keys = sorted([key for key in project_config if key not in allowed_keys])
        if unknown_keys:
            warnings.append("Unknown keys in .scc.yaml (ignored): " + ", ".join(unknown_keys))

        project_session = project_config.get("session", {})
        if "auto_resume" in project_session:
            warnings.append("session.auto_resume is advisory only and not enforced.")

        effective = compute_effective_config(
            org_config=NormalizedOrgConfig.from_dict(org_config),
            team_name=team,
            project_config=project_config,
        )

        project_plugins = set(project_config.get("additional_plugins", []))
        project_mcp_tokens: set[str] = set()
        for server in project_config.get("additional_mcp_servers", []):
            name = server.get("name")
            url = server.get("url")
            if name:
                project_mcp_tokens.add(name)
            if url:
                project_mcp_tokens.add(url)

        for blocked in effective.blocked_items:
            if blocked.item not in project_plugins and blocked.item not in project_mcp_tokens:
                continue
            blocked_items.append(
                {
                    "item": blocked.item,
                    "blocked_by": blocked.blocked_by,
                    "source": blocked.source,
                    "target_type": blocked.target_type,
                }
            )
            errors.append(f"{blocked.item} blocked by {blocked.blocked_by} ({blocked.source})")

        for denied in effective.denied_additions:
            if denied.requested_by != RequestSource.PROJECT:
                continue
            denied_additions.append(
                {
                    "item": denied.item,
                    "requested_by": denied.requested_by,
                    "reason": denied.reason,
                    "target_type": denied.target_type,
                }
            )
            errors.append(f"{denied.item} denied ({denied.reason})")

    ok = not errors
    exit_code = EXIT_SUCCESS if ok else EXIT_CONFIG
    if denied_additions or blocked_items:
        exit_code = EXIT_GOVERNANCE

    if json_output:
        data = {
            "workspace_path": str(ws_path),
            "team": team,
            "project_config_path": str(config_file),
            "project_config_found": project_config is not None,
            "blocked_items": blocked_items,
            "denied_additions": denied_additions,
            "unknown_keys": unknown_keys,
        }
        envelope = build_envelope(
            Kind.CONFIG_VALIDATE,
            data=data,
            ok=ok,
            errors=errors,
            warnings=warnings,
        )
        print_json(envelope)
        raise typer.Exit(exit_code)

    if ok:
        team_label = team or "unknown"
        console.print(
            create_success_panel(
                "Project Config Valid",
                {
                    "Workspace": str(ws_path),
                    "Config": str(config_file),
                    "Team": team_label,
                },
            )
        )
    else:
        console.print(
            create_error_panel(
                "Project Config Invalid",
                errors[0],
                "Run 'scc config explain --field denied' for details.",
            )
        )

    if blocked_items:
        _render_blocked_items_inline(blocked_items)

    if denied_additions:
        _render_denied_additions_inline(denied_additions)

    if warnings:
        console.print("[bold yellow]Warnings[/bold yellow]")
        for warning in warnings:
            console.print(f"  [yellow]⚠[/yellow] {warning}")
        console.print()

    raise typer.Exit(exit_code)


def _render_blocked_items_inline(blocked_items: list[dict[str, Any]]) -> None:
    """Render blocked items from validation results (dict form)."""
    console.print("[bold red]Blocked Items[/bold red]")
    for item in blocked_items:
        console.print(
            f"  [red]✗[/red] {item['item']} [dim](blocked by {item['blocked_by']})[/dim]"
        )
    console.print()


def _render_denied_additions_inline(denied_additions: list[dict[str, Any]]) -> None:
    """Render denied additions from validation results (dict form)."""
    console.print("[bold yellow]Denied Additions[/bold yellow]")
    for item in denied_additions:
        console.print(f"  [yellow]⚠[/yellow] {item['item']}: {item['reason']}")
    console.print()


def _render_blocked_items(blocked_items: list[BlockedItem]) -> None:
    """Render blocked items with patterns and fix-it commands."""
    from scc_cli.utils.fixit import generate_policy_exception_command

    console.print("[bold red]Blocked Items[/bold red]")
    for item in blocked_items:
        console.print(
            f"  [red]✗[/red] [bold]{item.item}[/bold] "
            f"[dim](blocked by pattern '{item.blocked_by}' from {item.source})[/dim]"
        )
        cmd = generate_policy_exception_command(item.item, item.target_type)
        console.print("      [dim]To request exception (requires PR):[/dim]")
        console.print(f"      [cyan]{cmd}[/cyan]")
    console.print()


def _render_denied_additions(denied_additions: list[DelegationDenied]) -> None:
    """Render denied additions with reasons and fix-it commands."""
    from scc_cli.utils.fixit import generate_unblock_command

    console.print("[bold yellow]Denied Additions[/bold yellow]")
    for denied in denied_additions:
        console.print(
            f"  [yellow]⚠[/yellow] [bold]{denied.item}[/bold] "
            f"[dim](requested by {denied.requested_by}: {denied.reason})[/dim]"
        )
        cmd = generate_unblock_command(denied.item, denied.target_type)
        console.print("      [dim]To unblock locally:[/dim]")
        console.print(f"      [cyan]{cmd}[/cyan]")
    console.print()
