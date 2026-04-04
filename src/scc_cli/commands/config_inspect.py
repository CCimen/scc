"""Config paths and exception inspection.

Extracted from config.py to reduce module size. Contains:
- _config_paths: shows SCC file locations with sizes and permissions
- _render_active_exceptions: renders active exceptions from user/repo stores
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from rich import box
from rich.table import Table

from ..cli_common import console
from ..maintenance import get_paths, get_total_size
from ..stores.exception_store import RepoStore, UserStore
from ..utils.ttl import format_relative


def _config_paths(json_output: bool = False, show_env: bool = False) -> None:
    """Show SCC file locations with sizes and permissions."""
    import os

    paths = get_paths()
    total_size = get_total_size()

    if json_output:
        output: dict[str, object] = {
            "paths": [
                {
                    "name": p.name,
                    "path": str(p.path),
                    "exists": p.exists,
                    "size_bytes": p.size_bytes,
                    "permissions": p.permissions,
                }
                for p in paths
            ],
            "total_bytes": total_size,
        }
        if show_env:
            output["environment"] = {
                "XDG_CONFIG_HOME": os.environ.get("XDG_CONFIG_HOME", ""),
                "XDG_CACHE_HOME": os.environ.get("XDG_CACHE_HOME", ""),
            }
        console.print(json.dumps(output, indent=2))
        return

    console.print("\n[bold cyan]SCC File Locations[/bold cyan]")
    console.print("─" * 70)

    table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Path")
    table.add_column("Size", justify="right")
    table.add_column("Status")
    table.add_column("Perm", justify="center")

    for path_info in paths:
        exists_badge = "[green]✓ exists[/green]" if path_info.exists else "[dim]missing[/dim]"
        perm_badge = path_info.permissions if path_info.permissions != "--" else "[dim]--[/dim]"
        size_str = path_info.size_human if path_info.exists else "-"

        table.add_row(
            path_info.name,
            str(path_info.path),
            size_str,
            exists_badge,
            perm_badge,
        )

    console.print(table)
    console.print("─" * 70)

    # Show total
    total_kb = total_size / 1024
    console.print(f"[bold]Total: {total_kb:.1f} KB[/bold]")

    # Show XDG environment variables if requested
    if show_env:
        console.print()
        console.print("[bold]Environment Variables:[/bold]")
        xdg_config = os.environ.get("XDG_CONFIG_HOME", "")
        xdg_cache = os.environ.get("XDG_CACHE_HOME", "")
        console.print(
            f"  XDG_CONFIG_HOME: {xdg_config if xdg_config else '[dim](not set, using ~/.config)[/dim]'}"
        )
        console.print(
            f"  XDG_CACHE_HOME: {xdg_cache if xdg_cache else '[dim](not set, using ~/.cache)[/dim]'}"
        )

    console.print()


def _render_active_exceptions() -> int:
    """Render active exceptions from user and repo stores.

    Returns the count of expired exceptions found (for user notification).
    """
    from ..models.exceptions import Exception as SccException

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
