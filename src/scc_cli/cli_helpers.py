"""Provide centralized CLI helpers for confirmation and safety patterns.

Provide standardized helpers for:
- Destructive operation confirmation (prune, worktree remove, etc.)
- Governance command validation (unblock, exceptions)
- Non-interactive mode detection (CI environments)
- JSON mode compatibility
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

import typer
from rich.console import Console

from .exit_codes import EXIT_USAGE
from .output_mode import is_json_mode

console = Console()
stderr_console = Console(stderr=True)


@dataclass(frozen=True)
class ConfirmItems:
    """Hold items to display before a confirmation prompt.

    Attributes:
        title: Header text shown above the item list.
        items: List of item descriptions to display.
        max_display: Maximum items to show before truncating with count.
    """

    title: str
    items: list[str]
    max_display: int = 10


def is_interactive() -> bool:
    """Check if running in interactive mode.

    Return False if:
    - stdin is not a TTY (piped input, redirected)
    - CI environment variable is set to truthy value
    - JSON output mode is active

    Returns:
        True if interactive prompts are safe to use.
    """
    if is_json_mode():
        return False

    is_tty = sys.stdin.isatty()
    is_ci = os.getenv("CI", "").lower() in ("1", "true", "yes")

    return is_tty and not is_ci


def confirm_action(
    *,
    yes: bool,
    prompt: str,
    dry_run: bool = False,
    items: ConfirmItems | None = None,
    non_interactive_requires_yes: bool = True,
) -> bool:
    """Standard confirmation behavior for destructive operations.

    Args:
        yes: If True, skip confirmation prompt.
        prompt: The confirmation question to ask.
        dry_run: If True, return False (caller should not mutate state).
        items: Optional list of affected items to display before prompting.
        non_interactive_requires_yes: If True, exit with EXIT_USAGE when
            running non-interactively without --yes.

    Returns:
        True if action should proceed, False if dry-run mode.

    Raises:
        typer.Exit(EXIT_USAGE): If non-interactive and would prompt without --yes.
        typer.Abort: If user declines confirmation.

    Behavior:
        - If dry_run: return False (caller should not mutate state)
        - If yes: return True (skip prompt)
        - If JSON mode: exit EXIT_USAGE (never prompt in JSON mode)
        - If non-interactive and would prompt: exit EXIT_USAGE
        - Otherwise: print affected resources (if provided) and prompt
    """
    if dry_run:
        return False

    if yes:
        return True

    # JSON mode must never prompt
    if is_json_mode():
        stderr_console.print(
            "[red]Error:[/red] Cannot prompt in JSON mode. Use --yes to confirm.",
            style="bold",
        )
        raise typer.Exit(EXIT_USAGE)

    # Non-interactive mode detection
    if not is_interactive() and non_interactive_requires_yes:
        console.print(
            "[red]Error:[/red] This operation requires confirmation. "
            "Use --yes to skip in non-interactive mode.",
            style="bold",
        )
        raise typer.Exit(EXIT_USAGE)

    # Display affected items
    if items:
        console.print(f"\n[bold]{items.title}[/bold]")
        shown = items.items[: items.max_display]
        for item in shown:
            console.print(f"  [dim]•[/dim] {item}")
        if len(items.items) > items.max_display:
            remaining = len(items.items) - items.max_display
            console.print(f"  [dim](+ {remaining} more)[/dim]")
        console.print()

    # Prompt for confirmation
    return typer.confirm(prompt, abort=True)


def require_reason_for_governance(
    *,
    yes: bool,
    reason: str | None,
    command_name: str = "unblock",
) -> str:
    """Require --reason when --yes is used for governance commands.

    Args:
        yes: Whether --yes flag was provided.
        reason: The reason string if provided via --reason.
        command_name: Name of the command for error messages.

    Returns:
        The reason string (either provided or collected interactively).

    Raises:
        typer.Exit(EXIT_USAGE): If --yes used without --reason.
    """
    if yes and not reason:
        console.print(
            f"[red]Error:[/red] --reason is required when using --yes with {command_name}.",
            style="bold",
        )
        raise typer.Exit(EXIT_USAGE)

    if reason:
        return reason

    # Interactive mode: prompt for reason
    if is_json_mode():
        stderr_console.print(
            "[red]Error:[/red] Cannot prompt for reason in JSON mode. Use --reason.",
            style="bold",
        )
        raise typer.Exit(EXIT_USAGE)

    if not is_interactive():
        console.print(
            "[red]Error:[/red] Cannot prompt for reason in non-interactive mode. Use --reason.",
            style="bold",
        )
        raise typer.Exit(EXIT_USAGE)

    prompted_reason: str = typer.prompt("Reason for this exception")
    return prompted_reason


@dataclass(frozen=True)
class AuditRecord:
    """Audit record for governance operations."""

    timestamp: datetime
    command: str
    actor: str
    target: str
    reason: str
    ticket: str | None = None
    expires_in: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, str | None] = {
            "timestamp": self.timestamp.isoformat(),
            "command": self.command,
            "actor": self.actor,
            "target": self.target,
            "reason": self.reason,
        }
        if self.ticket:
            result["ticket"] = self.ticket
        if self.expires_in:
            result["expires_in"] = self.expires_in
        return result


def get_current_user() -> str:
    """Get the current user for audit purposes."""
    return os.getenv("USER", os.getenv("USERNAME", "unknown"))


def create_audit_record(
    *,
    command: str,
    target: str,
    reason: str,
    ticket: str | None = None,
    expires_in: str | None = None,
) -> AuditRecord:
    """Create an audit record for governance operations.

    This is mandatory for governance commands (unblock, exception creation).
    For other destructive operations, use only if SCC_AUDIT_LOG is enabled.

    Args:
        command: The governance command being executed.
        target: The resource being affected (e.g., plugin name, policy).
        reason: Justification for the operation.
        ticket: Optional issue/ticket reference for traceability.
        expires_in: Optional duration string for temporary exceptions.

    Returns:
        A timestamped audit record with actor information.
    """
    return AuditRecord(
        timestamp=datetime.now(timezone.utc),
        command=command,
        actor=get_current_user(),
        target=target,
        reason=reason,
        ticket=ticket,
        expires_in=expires_in,
    )
