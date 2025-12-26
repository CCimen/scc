"""Provide CLI commands for exception management.

Manage time-bounded exceptions that allow developers to unblock themselves
from delegation failures while respecting security boundaries.

Commands:
    scc exceptions list: View active/expired exceptions
    scc exceptions create: Create new exceptions
    scc exceptions delete: Remove exceptions by ID
    scc exceptions cleanup: Prune expired exceptions
    scc exceptions reset: Clear exception stores
    scc unblock: Quick command to unblock a denied target
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.console import Console
from rich.table import Table

from . import config, profiles
from .cli_common import handle_errors
from .cli_helpers import create_audit_record, require_reason_for_governance
from .evaluation import EvaluationResult, evaluate
from .models.exceptions import AllowTargets
from .models.exceptions import Exception as SccException
from .stores.exception_store import RepoStore, UserStore
from .utils.fuzzy import find_similar
from .utils.ttl import calculate_expiration, format_expiration, format_relative

console = Console()


def _get_repo_root() -> Path:
    """Get current git repo root or current directory."""
    cwd = Path.cwd()
    # Walk up to find .git
    current = cwd
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    # Not in git repo, use cwd
    return cwd


def _get_user_store() -> UserStore:
    """Get user exception store."""
    return UserStore()


def _get_repo_store() -> RepoStore:
    """Get repo exception store."""
    return RepoStore(_get_repo_root())


def _is_git_ignored(file_path: str) -> bool:
    """Check if a file path is ignored by git.

    Uses git check-ignore to determine if the file would be ignored.
    Returns False if git is not available or not in a git repo (fail-open).
    """
    import subprocess

    repo_root = _get_repo_root()
    # Only check if we're actually in a git repo
    if not (repo_root / ".git").exists():
        return False

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", file_path],
            capture_output=True,
            cwd=repo_root,
            timeout=5,
        )
        # Exit code 0 means file is ignored
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # git not available or other error - fail silently
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions sub-app
# ─────────────────────────────────────────────────────────────────────────────

exceptions_app = typer.Typer(
    name="exceptions",
    help="Manage time-bounded exceptions for blocked or denied items.",
    no_args_is_help=True,
)


def _generate_local_id() -> str:
    """Generate a unique local exception ID."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_part = secrets.token_hex(2)
    return f"local-{date_part}-{random_part}"


def _is_expired(exc: SccException) -> bool:
    """Check if an exception has expired."""
    try:
        expires = datetime.fromisoformat(exc.expires_at.replace("Z", "+00:00"))
        return expires <= datetime.now(timezone.utc)
    except (ValueError, AttributeError):
        return True


def _format_targets(exc: SccException) -> str:
    """Format exception targets for display."""
    parts = []
    if exc.allow.plugins:
        parts.append(f"plugins: {', '.join(exc.allow.plugins)}")
    if exc.allow.mcp_servers:
        parts.append(f"mcp: {', '.join(exc.allow.mcp_servers)}")
    if exc.allow.base_images:
        parts.append(f"images: {', '.join(exc.allow.base_images)}")
    return "; ".join(parts) if parts else "(none)"


def _format_expires_in(exc: SccException) -> str:
    """Format relative expiration time."""
    try:
        expires = datetime.fromisoformat(exc.expires_at.replace("Z", "+00:00"))
        return format_relative(expires)
    except (ValueError, AttributeError):
        return "unknown"


# ─────────────────────────────────────────────────────────────────────────────
# exceptions list command
# ─────────────────────────────────────────────────────────────────────────────


@exceptions_app.command("list")
@handle_errors
def exceptions_list(
    active: Annotated[
        bool,
        typer.Option("--active", help="Show only active (non-expired) exceptions."),
    ] = False,
    expired: Annotated[
        bool,
        typer.Option("--expired", help="Show only expired exceptions."),
    ] = False,
    all_exceptions: Annotated[
        bool,
        typer.Option("--all", help="Show all exceptions (active and expired)."),
    ] = False,
    as_json: Annotated[
        bool,
        typer.Option("--json", help="Output as JSON."),
    ] = False,
) -> None:
    """List exceptions from local stores."""
    user_store = _get_user_store()
    repo_store = _get_repo_store()

    user_exceptions = user_store.read().exceptions
    repo_exceptions = repo_store.read().exceptions

    all_exc = user_exceptions + repo_exceptions

    # Filter based on flags
    if expired:
        filtered = [e for e in all_exc if _is_expired(e)]
    elif active or (not all_exceptions and not expired):
        # Default to active
        filtered = [e for e in all_exc if not _is_expired(e)]
    else:
        filtered = all_exc

    if as_json:
        output = [
            {
                "id": e.id,
                "scope": e.scope,
                "reason": e.reason,
                "expires_at": e.expires_at,
                "expired": _is_expired(e),
                "targets": {
                    "plugins": e.allow.plugins or [],
                    "mcp_servers": e.allow.mcp_servers or [],
                    "base_images": e.allow.base_images or [],
                },
            }
            for e in filtered
        ]
        console.print(json.dumps(output, indent=2))
        return

    if not filtered:
        console.print("[dim]No exceptions found.[/dim]")
        return

    table = Table(
        title="[bold cyan]Exceptions[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
    )
    table.add_column("ID", style="cyan")
    table.add_column("Scope", style="dim")
    table.add_column("Targets", style="green")
    table.add_column("Expires In", style="yellow")
    table.add_column("Reason", style="dim")

    for exc in filtered:
        expires_in = _format_expires_in(exc)
        if _is_expired(exc):
            expires_in = "[red]expired[/red]"
        table.add_row(
            exc.id,
            exc.scope,
            _format_targets(exc),
            expires_in,
            exc.reason[:30] + "..." if len(exc.reason) > 30 else exc.reason,
        )

    console.print()
    console.print(table)
    console.print()

    # Show note about expired if viewing active
    if not expired and not all_exceptions:
        expired_count = sum(1 for e in all_exc if _is_expired(e))
        if expired_count > 0:
            console.print(
                f"[dim]Note: {expired_count} expired (run `scc exceptions cleanup`)[/dim]"
            )


# ─────────────────────────────────────────────────────────────────────────────
# exceptions create command
# ─────────────────────────────────────────────────────────────────────────────


@exceptions_app.command("create")
@handle_errors
def exceptions_create(
    policy: Annotated[
        bool,
        typer.Option("--policy", help="Generate YAML snippet for policy PR."),
    ] = False,
    exception_id: Annotated[
        str | None,
        typer.Option("--id", help="Exception ID (required for --policy)."),
    ] = None,
    ttl: Annotated[
        str | None,
        typer.Option("--ttl", help="Time-to-live (e.g., 8h, 30m, 1d)."),
    ] = None,
    expires_at: Annotated[
        str | None,
        typer.Option("--expires-at", help="Expiration time (RFC3339 format)."),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Expire at time of day (HH:MM format)."),
    ] = None,
    reason: Annotated[
        str | None,
        typer.Option("--reason", help="Reason for exception (required)."),
    ] = None,
    allow_mcp: Annotated[
        list[str] | None,
        typer.Option("--allow-mcp", help="Allow MCP server (repeatable)."),
    ] = None,
    allow_plugin: Annotated[
        list[str] | None,
        typer.Option("--allow-plugin", help="Allow plugin (repeatable)."),
    ] = None,
    allow_image: Annotated[
        list[str] | None,
        typer.Option("--allow-image", help="Allow base image (repeatable)."),
    ] = None,
    shared: Annotated[
        bool,
        typer.Option("--shared", help="Save to repo store instead of user store."),
    ] = False,
) -> None:
    """Create a new exception."""
    # Validate required fields
    if not reason:
        console.print("[red]Error: --reason is required.[/red]")
        raise typer.Exit(1)

    if not any([allow_mcp, allow_plugin, allow_image]):
        console.print(
            "[red]Error: At least one target required "
            "(--allow-mcp, --allow-plugin, or --allow-image).[/red]"
        )
        raise typer.Exit(1)

    if policy and not exception_id:
        console.print("[red]Error: --id is required when using --policy.[/red]")
        raise typer.Exit(1)

    # Calculate expiration
    try:
        expiration = calculate_expiration(ttl=ttl, expires_at=expires_at, until=until)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Create exception
    now = datetime.now(timezone.utc)
    # Type assertion: exception_id is validated above when policy=True
    exc_id = exception_id if policy and exception_id else _generate_local_id()

    exception = SccException(
        id=exc_id,
        created_at=format_expiration(now),
        expires_at=format_expiration(expiration),
        reason=reason,
        scope="policy" if policy else "local",
        allow=AllowTargets(
            plugins=allow_plugin or [],
            mcp_servers=allow_mcp or [],
            base_images=allow_image or [],
        ),
    )

    # For policy exceptions, generate YAML snippet instead of saving
    if policy:
        console.print("\n[bold cyan]Add this to your org config exceptions:[/bold cyan]\n")
        console.print(f"  - id: {exception.id}")
        console.print(f'    reason: "{exception.reason}"')
        console.print(f'    expires_at: "{exception.expires_at}"')
        console.print("    allow:")
        if exception.allow.plugins:
            console.print(f"      plugins: {exception.allow.plugins}")
        if exception.allow.mcp_servers:
            console.print(f"      mcp_servers: {exception.allow.mcp_servers}")
        if exception.allow.base_images:
            console.print(f"      base_images: {exception.allow.base_images}")
        console.print()
        return

    # Save to appropriate store
    store: UserStore | RepoStore
    if shared:
        store = _get_repo_store()
        store_path = ".scc/exceptions.json"
    else:
        store = _get_user_store()
        store_path = "~/.config/scc/exceptions.json"

    exc_file = store.read()
    exc_file.exceptions.append(exception)

    # Prune expired during write (hybrid cleanup)
    pruned = store.prune_expired()
    store.write(exc_file)

    targets = _format_targets(exception)
    expires_in = format_relative(expiration)

    console.print(f"\n[green]✓[/green] Created local override for {targets}")
    console.print(f"  Expires: {exception.expires_at} (in {expires_in})")
    console.print(f"  Saved to {store_path}")
    if pruned > 0:
        console.print(f"  [dim]Note: Pruned {pruned} expired entries.[/dim]")
    if shared and _is_git_ignored(store_path):
        console.print("\n[yellow]⚠️  Warning:[/yellow] .scc/exceptions.json is ignored by git.")
        console.print("    Your team won't see this shared exception.")
    console.print()


# ─────────────────────────────────────────────────────────────────────────────
# exceptions delete command
# ─────────────────────────────────────────────────────────────────────────────


@exceptions_app.command("delete")
@handle_errors
def exceptions_delete(
    exception_id: Annotated[
        str,
        typer.Argument(help="Exception ID or unambiguous prefix."),
    ],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation."),
    ] = False,
) -> None:
    """Delete an exception by ID."""
    user_store = _get_user_store()
    repo_store = _get_repo_store()

    # Search in both stores
    user_file = user_store.read()
    repo_file = repo_store.read()

    # Find matching exceptions
    user_matches = [e for e in user_file.exceptions if e.id.startswith(exception_id)]
    repo_matches = [e for e in repo_file.exceptions if e.id.startswith(exception_id)]

    all_matches = user_matches + repo_matches

    if not all_matches:
        console.print(f"[red]Error: No exception found matching '{exception_id}'.[/red]")
        raise typer.Exit(1)

    if len(all_matches) > 1:
        console.print(f"[red]Error: Ambiguous prefix '{exception_id}'. Matches:[/red]")
        for m in all_matches:
            console.print(f"  - {m.id}")
        raise typer.Exit(1)

    match = all_matches[0]

    # Determine which store contains the match
    store: UserStore | RepoStore
    if match in user_matches:
        store = user_store
        exc_file = user_file
        store_name = "user"
    else:
        store = repo_store
        exc_file = repo_file
        store_name = "repo"

    # Remove and save
    exc_file.exceptions = [e for e in exc_file.exceptions if e.id != match.id]
    store.write(exc_file)

    console.print(f"[green]✓[/green] Deleted exception '{match.id}' from {store_name} store.")


# ─────────────────────────────────────────────────────────────────────────────
# exceptions cleanup command
# ─────────────────────────────────────────────────────────────────────────────


@exceptions_app.command("cleanup")
@handle_errors
def exceptions_cleanup() -> None:
    """Remove expired exceptions from local stores."""
    user_store = _get_user_store()
    repo_store = _get_repo_store()

    user_pruned = user_store.prune_expired()
    repo_pruned = repo_store.prune_expired()

    total = user_pruned + repo_pruned

    if total == 0:
        console.print("[dim]No expired exceptions to clean up.[/dim]")
    else:
        console.print(f"[green]✓[/green] Removed {total} expired exceptions.")
        if user_pruned > 0:
            console.print(f"  - {user_pruned} from user store")
        if repo_pruned > 0:
            console.print(f"  - {repo_pruned} from repo store")


# ─────────────────────────────────────────────────────────────────────────────
# exceptions reset command
# ─────────────────────────────────────────────────────────────────────────────


@exceptions_app.command("reset")
@handle_errors
def exceptions_reset(
    user: Annotated[
        bool,
        typer.Option("--user", help="Reset user store (~/.config/scc/exceptions.json)."),
    ] = False,
    repo: Annotated[
        bool,
        typer.Option("--repo", help="Reset repo store (.scc/exceptions.json)."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation (required)."),
    ] = False,
) -> None:
    """Reset (clear) exception stores. Destructive operation."""
    if not yes:
        console.print("[red]Error: --yes is required for destructive reset operation.[/red]")
        raise typer.Exit(1)

    if not user and not repo:
        console.print("[red]Error: Specify --user or --repo (or both).[/red]")
        raise typer.Exit(1)

    if user:
        user_store = _get_user_store()
        user_store.reset()
        console.print("[green]✓[/green] Reset user exception store.")

    if repo:
        repo_store = _get_repo_store()
        repo_store.reset()
        console.print("[green]✓[/green] Reset repo exception store.")


# ─────────────────────────────────────────────────────────────────────────────
# unblock command (top-level, not under exceptions)
# ─────────────────────────────────────────────────────────────────────────────


def get_current_denials() -> EvaluationResult:
    """Get current evaluation result with denied items.

    Connects to the config evaluation pipeline to get currently
    blocked/denied items based on the user's team profile and workspace.

    Returns:
        EvaluationResult with blocked_items and denied_additions populated
        from the effective config evaluation. Returns empty result if
        in standalone mode or no team is selected.
    """
    org_config = config.load_cached_org_config()
    if not org_config:
        # Standalone mode - nothing is denied
        return EvaluationResult()

    team = config.get_selected_profile()
    if not team:
        # No team selected - nothing is denied
        return EvaluationResult()

    # Compute effective config for current workspace
    effective = profiles.compute_effective_config(
        org_config=org_config,
        team_name=team,
        workspace_path=Path.cwd(),
    )

    # Convert to evaluation result with proper types
    return evaluate(effective)


@handle_errors
def unblock_cmd(
    target: Annotated[
        str,
        typer.Argument(help="Target to unblock (MCP server, plugin, or image name)."),
    ],
    ttl: Annotated[
        str | None,
        typer.Option("--ttl", help="Time-to-live (e.g., 8h, 30m, 1d)."),
    ] = None,
    expires_at: Annotated[
        str | None,
        typer.Option("--expires-at", help="Expiration time (RFC3339 format)."),
    ] = None,
    until: Annotated[
        str | None,
        typer.Option("--until", help="Expire at time of day (HH:MM format)."),
    ] = None,
    reason: Annotated[
        str | None,
        typer.Option("--reason", help="Reason for unblocking (required with --yes)."),
    ] = None,
    ticket: Annotated[
        str | None,
        typer.Option("--ticket", help="Related ticket ID (e.g., JIRA-123) for audit trail."),
    ] = None,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation prompt (requires --reason)."),
    ] = False,
    shared: Annotated[
        bool,
        typer.Option("--shared", help="Save to repo store instead of user store."),
    ] = False,
) -> None:
    """Unblock a currently denied target.

    Creates a local override to allow a target that is currently denied by
    delegation policy. This command only works for delegation denials, not
    security blocks.

    Governance audit: All unblock operations are logged with actor, reason,
    and timestamp for compliance tracking.

    Example:
        scc unblock jira-api --ttl 8h --reason "Need for sprint planning"
        scc unblock my-plugin --yes --reason "Emergency fix" --ticket INC-123
    """
    # Governance commands require --reason when using --yes (or prompt interactively)
    validated_reason = require_reason_for_governance(yes=yes, reason=reason, command_name="unblock")

    # Get current evaluation state
    eval_result = get_current_denials()

    # Check if target is security-blocked (cannot unblock locally)
    for blocked in eval_result.blocked_items:
        if blocked.target == target:
            console.print(
                f"\n[red]✗[/red] Cannot unblock '{target}': blocked by security policy.\n"
            )
            console.print("  To request policy exception (requires PR approval):")
            console.print(
                f"    scc exceptions create --policy --id INC-... --allow-mcp {target} "
                f'--ttl 8h --reason "..."'
            )
            console.print()
            raise typer.Exit(1)

    # Check if target is actually denied
    denied_match = None
    for denied in eval_result.denied_additions:
        if denied.target == target:
            denied_match = denied
            break

    if not denied_match:
        # Try fuzzy matching to suggest similar targets
        denied_names = [d.target for d in eval_result.denied_additions]
        suggestions = find_similar(target, denied_names)

        console.print(f"\n[red]✗[/red] Nothing to unblock: '{target}' is not currently denied.\n")

        if suggestions:
            console.print("[yellow]Did you mean one of these?[/yellow]")
            for suggestion in suggestions:
                console.print(f"  - {suggestion}")
            console.print("\n[dim]Re-run with the exact name.[/dim]")
        else:
            console.print("  To create a preemptive exception, use:")
            console.print(f'    scc exceptions create --allow-mcp {target} --ttl 8h --reason "..."')
        console.print()
        raise typer.Exit(1)

    # Calculate expiration
    try:
        expiration = calculate_expiration(ttl=ttl, expires_at=expires_at, until=until)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    # Create exception
    now = datetime.now(timezone.utc)
    exc_id = _generate_local_id()

    # Determine target type and create appropriate allow targets
    target_type = denied_match.target_type
    allow = AllowTargets(
        plugins=[target] if target_type == "plugin" else [],
        mcp_servers=[target] if target_type == "mcp_server" else [],
        base_images=[target] if target_type == "base_image" else [],
    )

    exception = SccException(
        id=exc_id,
        created_at=format_expiration(now),
        expires_at=format_expiration(expiration),
        reason=validated_reason,
        scope="local",
        allow=allow,
    )

    # Save to appropriate store
    store: UserStore | RepoStore
    if shared:
        store = _get_repo_store()
        store_path = ".scc/exceptions.json"
        store_type = "shared"
    else:
        store = _get_user_store()
        store_path = "~/.config/scc/exceptions.json"
        store_type = "local"

    exc_file = store.read()
    exc_file.exceptions.append(exception)

    # Prune expired during write
    pruned = store.prune_expired()
    store.write(exc_file)

    expires_in = format_relative(expiration)

    # Create audit record for governance tracking
    _audit = create_audit_record(
        command="unblock",
        target=target,
        reason=validated_reason,
        ticket=ticket,
        expires_in=expires_in,
    )
    # Note: audit record is created for tracking; actual logging depends on audit sink configuration

    console.print(
        f"\n[green]✓[/green] Created {store_type} override for "
        f'{target_type} "{target}" (expires in {expires_in})'
    )
    console.print(f"  Saved to {store_path}")
    if pruned > 0:
        console.print(f"  [dim]Note: Pruned {pruned} expired entries.[/dim]")
    if shared and _is_git_ignored(store_path):
        console.print("\n[yellow]⚠️  Warning:[/yellow] .scc/exceptions.json is ignored by git.")
        console.print("    Your team won't see this shared exception.")
    console.print()
