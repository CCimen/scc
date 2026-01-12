"""Provide CLI commands for maintenance and reset operations.

Unified maintenance hub for clearing caches, resetting configurations,
and performing factory resets.

Commands:
    scc reset: Interactive maintenance picker (TTY mode)
    scc reset --cache: Clear regenerable cache files
    scc reset --contexts: Clear recent work contexts
    scc reset --sessions: Safe prune sessions (30d, keep 20)
    scc reset --all: Factory reset (everything)
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Annotated

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from ..cli_common import handle_errors
from ..core.exit_codes import (
    EXIT_CANCELLED,
    EXIT_SUCCESS,
    EXIT_USAGE,
)
from ..core.maintenance import (
    MaintenanceLock,
    MaintenanceLockError,
    MaintenancePreview,
    ResetResult,
    RiskTier,
    cleanup_expired_exceptions,
    clear_cache,
    clear_contexts,
    delete_all_sessions,
    factory_reset,
    get_paths,
    preview_operation,
    prune_containers,
    prune_sessions,
    reset_config,
    reset_exceptions,
)

console = Console()


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Tier Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _risk_badge(tier: RiskTier) -> str:
    """Get risk tier badge for display."""
    badges = {
        RiskTier.SAFE: "[green]SAFE ✓[/green]",
        RiskTier.CHANGES_STATE: "[yellow]CHANGES STATE ![/yellow]",
        RiskTier.DESTRUCTIVE: "[red]DESTRUCTIVE !![/red]",
        RiskTier.FACTORY_RESET: "[bold red]VERY DESTRUCTIVE ☠[/bold red]",
    }
    return badges.get(tier, "")


def _max_risk(tiers: list[RiskTier]) -> RiskTier:
    """Get maximum risk tier from a list."""
    if not tiers:
        return RiskTier.SAFE
    return max(tiers, key=lambda t: t.value)


# ═══════════════════════════════════════════════════════════════════════════════
# Output Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _print_result(result: ResetResult, as_json: bool = False) -> None:
    """Print operation result."""
    if as_json:
        return  # JSON mode collects all results at end

    if result.success:
        console.print(f"[green]✓[/green] {result.message}")
        if result.bytes_freed > 0:
            console.print(f"  Freed: {result.bytes_freed_human}")
        if result.backup_path:
            console.print(f"  Backup: {result.backup_path}")
        for step in result.next_steps:
            console.print(f"  [dim]Next: {step}[/dim]")
    else:
        console.print(f"[red]✗[/red] {result.message}")
        if result.error:
            console.print(f"  Error: {result.error}")


def _print_preview(preview: MaintenancePreview) -> None:
    """Print operation preview."""
    console.print(f"\n[bold]{preview.description}[/bold] {_risk_badge(preview.risk_tier)}")
    for path in preview.paths:
        console.print(f"  Path: {path}")
    if preview.item_count > 0:
        console.print(f"  Items: {preview.item_count}")
    if preview.bytes_estimate > 0:
        size: float = preview.bytes_estimate
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                console.print(f"  Size: {size:.1f} {unit}")
                break
            size = size / 1024
    if preview.backup_will_be_created:
        console.print("  [dim]Backup will be created (may contain sensitive tokens)[/dim]")


def _print_json_results(results: list[ResetResult]) -> None:
    """Print results as JSON."""
    output = {
        "ok": all(r.success for r in results),
        "actions": [
            {
                "id": r.action_id,
                "risk_tier": r.risk_tier.value,
                "status": "success" if r.success else "error",
                "paths": [str(p) for p in r.paths],
                "removed_count": r.removed_count,
                "bytes_freed": r.bytes_freed,
                "backup_path": str(r.backup_path) if r.backup_path else None,
                "message": r.message,
                "error": r.error,
            }
            for r in results
        ],
        "total_bytes_freed": sum(r.bytes_freed for r in results),
        "warnings": [],
        "next_steps": list({step for r in results for step in r.next_steps}),
    }
    console.print(json.dumps(output, indent=2))


# ═══════════════════════════════════════════════════════════════════════════════
# Confirmation Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _confirm_tier_1(action: str, yes: bool, non_interactive: bool) -> bool:
    """Confirm Tier 1 (Changes State) operation."""
    if yes:
        return True
    if non_interactive:
        console.print(f"[red]Error: {action} requires confirmation. Use --yes to skip.[/red]")
        raise typer.Exit(EXIT_CANCELLED)
    return Confirm.ask(f"Proceed with {action}?")


def _confirm_tier_2(
    action: str,
    preview: MaintenancePreview,
    yes: bool,
    non_interactive: bool,
) -> bool:
    """Confirm Tier 2 (Destructive) operation with impact list."""
    if yes:
        return True
    if non_interactive:
        console.print(f"[red]Error: {action} requires confirmation. Use --yes to skip.[/red]")
        raise typer.Exit(EXIT_CANCELLED)

    _print_preview(preview)
    return Confirm.ask(f"\n[bold]Proceed with {action}?[/bold]")


def _confirm_factory_reset(yes: bool, force: bool, non_interactive: bool) -> bool:
    """Confirm Tier 3 (Factory Reset) - requires typing RESET or --yes --force."""
    if yes and force:
        return True

    if non_interactive:
        console.print(
            "[red]Error: Factory reset requires --yes --force in non-interactive mode.[/red]"
        )
        raise typer.Exit(EXIT_CANCELLED)

    if yes and not force:
        console.print("[red]Error: Factory reset requires --force when using --yes.[/red]")
        raise typer.Exit(EXIT_USAGE)

    console.print("\n[bold red]⚠️  FACTORY RESET[/bold red]")
    console.print("This will remove ALL SCC data:\n")

    # Show what will be affected
    paths = get_paths()
    for path in paths:
        if path.exists:
            console.print(f"  • {path.name}: {path.path}")

    console.print("\n[bold]Type RESET to confirm:[/bold]")
    response = Prompt.ask("")
    return response == "RESET"


# ═══════════════════════════════════════════════════════════════════════════════
# Interactive Mode
# ═══════════════════════════════════════════════════════════════════════════════


def _run_interactive_mode() -> None:
    """Run interactive maintenance picker."""
    console.print("\n[bold cyan]SCC Maintenance[/bold cyan]\n")

    # Define available actions
    actions = [
        ("clear_cache", "Clear cache", RiskTier.SAFE),
        ("cleanup_expired_exceptions", "Cleanup expired exceptions", RiskTier.SAFE),
        ("clear_contexts", "Clear contexts", RiskTier.CHANGES_STATE),
        ("prune_containers", "Prune containers", RiskTier.CHANGES_STATE),
        ("prune_sessions", "Prune sessions (30d, keep 20)", RiskTier.CHANGES_STATE),
        ("reset_exceptions", "Reset all exceptions", RiskTier.DESTRUCTIVE),
        ("delete_all_sessions", "Delete all sessions", RiskTier.DESTRUCTIVE),
        ("reset_config", "Reset configuration", RiskTier.DESTRUCTIVE),
        ("factory_reset", "Factory reset (everything)", RiskTier.FACTORY_RESET),
    ]

    # Display numbered list
    for i, (action_id, name, tier) in enumerate(actions, 1):
        console.print(f"  {i}. {name} {_risk_badge(tier)}")

    console.print("\n  0. Cancel")
    console.print()

    # Get selection
    choice = Prompt.ask("Select action", default="0")
    try:
        idx = int(choice)
    except ValueError:
        console.print("[red]Invalid selection.[/red]")
        raise typer.Exit(EXIT_CANCELLED)

    if idx == 0:
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(EXIT_CANCELLED)

    if idx < 1 or idx > len(actions):
        console.print("[red]Invalid selection.[/red]")
        raise typer.Exit(EXIT_CANCELLED)

    action_id, action_name, tier = actions[idx - 1]

    # Get confirmation based on risk tier
    if tier == RiskTier.SAFE:
        pass  # No confirmation needed
    elif tier == RiskTier.CHANGES_STATE:
        if not _confirm_tier_1(action_name, yes=False, non_interactive=False):
            raise typer.Exit(EXIT_CANCELLED)
    elif tier == RiskTier.DESTRUCTIVE:
        preview = preview_operation(action_id)
        if not _confirm_tier_2(action_name, preview, yes=False, non_interactive=False):
            raise typer.Exit(EXIT_CANCELLED)
    elif tier == RiskTier.FACTORY_RESET:
        if not _confirm_factory_reset(yes=False, force=False, non_interactive=False):
            raise typer.Exit(EXIT_CANCELLED)

    # Execute the action
    try:
        with MaintenanceLock():
            if action_id == "clear_cache":
                result = clear_cache()
            elif action_id == "cleanup_expired_exceptions":
                result = cleanup_expired_exceptions()
            elif action_id == "clear_contexts":
                result = clear_contexts()
            elif action_id == "prune_containers":
                result = prune_containers()
            elif action_id == "prune_sessions":
                result = prune_sessions()
            elif action_id == "reset_exceptions":
                result = reset_exceptions()
            elif action_id == "delete_all_sessions":
                result = delete_all_sessions()
            elif action_id == "reset_config":
                result = reset_config()
            elif action_id == "factory_reset":
                results = factory_reset()
                for r in results:
                    _print_result(r)
                return
            else:
                console.print(f"[red]Unknown action: {action_id}[/red]")
                raise typer.Exit(EXIT_USAGE)

            _print_result(result)

    except MaintenanceLockError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


# ═══════════════════════════════════════════════════════════════════════════════
# Main Command
# ═══════════════════════════════════════════════════════════════════════════════


@handle_errors
def reset_cmd(
    # Selection flags
    cache: Annotated[
        bool,
        typer.Option("--cache", help="Clear regenerable cache files."),
    ] = False,
    contexts: Annotated[
        bool,
        typer.Option("--contexts", help="Clear recent work contexts."),
    ] = False,
    exceptions: Annotated[
        bool,
        typer.Option("--exceptions", help="Reset all policy exceptions."),
    ] = False,
    exceptions_expired: Annotated[
        bool,
        typer.Option("--exceptions-expired", help="Remove only expired exceptions."),
    ] = False,
    exceptions_scope: Annotated[
        str | None,
        typer.Option(
            "--exceptions-scope",
            help="Scope for --exceptions (all, user, repo).",
        ),
    ] = None,
    containers: Annotated[
        bool,
        typer.Option("--containers", help="Remove stopped Docker containers."),
    ] = False,
    sessions: Annotated[
        bool,
        typer.Option("--sessions", help="Safe prune sessions (30d, keep 20)."),
    ] = False,
    sessions_all: Annotated[
        bool,
        typer.Option("--sessions-all", help="Delete entire sessions store."),
    ] = False,
    config_flag: Annotated[
        bool,
        typer.Option("--config", help="Reset configuration (requires setup)."),
    ] = False,
    all_flag: Annotated[
        bool,
        typer.Option("--all", help="Factory reset (everything)."),
    ] = False,
    # Execution flags
    plan: Annotated[
        bool,
        typer.Option("--plan", help="Fast preview: show what would be affected."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            "-n",
            "--what-if",
            help="Execute codepaths without writes.",
        ),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation for Tier 0-2."),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", help="Required with --yes for --all."),
    ] = False,
    no_backup: Annotated[
        bool,
        typer.Option("--no-backup", help="Skip backup creation for Tier 2 actions."),
    ] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option("--continue-on-error", help="Don't stop on first failure."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable output."),
    ] = False,
    non_interactive: Annotated[
        bool,
        typer.Option("--non-interactive", help="Fail if prompt needed."),
    ] = False,
) -> None:
    """Maintenance and reset operations.

    Run without flags for interactive mode.

    \b
    Examples:
      # TUI feels weird? Clear cache and contexts
      scc reset --cache --contexts

      # Policy stuck? Cleanup expired exceptions
      scc reset --exceptions-expired

      # Fresh start for this project
      scc reset --contexts --sessions

      # Preview what factory reset would do
      scc reset --all --plan

      # Hard reset (interactive confirmation)
      scc reset --all

      # CI/scripting: factory reset without prompts
      scc reset --all --yes --force
    """
    # Check if any selection flag is provided
    any_selection = any(
        [
            cache,
            contexts,
            exceptions,
            exceptions_expired,
            containers,
            sessions,
            sessions_all,
            config_flag,
            all_flag,
        ]
    )

    # If no selection and TTY, run interactive mode
    if not any_selection:
        if sys.stdin.isatty() and not non_interactive:
            _run_interactive_mode()
            return
        else:
            console.print("[red]Error: No action specified. Use --cache, --contexts, etc.[/red]")
            raise typer.Exit(EXIT_USAGE)

    # Validate flag combinations
    if exceptions_scope and not exceptions:
        console.print("[red]Error: --exceptions-scope requires --exceptions.[/red]")
        raise typer.Exit(EXIT_USAGE)

    if exceptions_scope and exceptions_scope not in ("all", "user", "repo"):
        console.print("[red]Error: --exceptions-scope must be all, user, or repo.[/red]")
        raise typer.Exit(EXIT_USAGE)

    # --all overrides individual flags
    if all_flag:
        if plan:
            # Show factory reset preview
            console.print("\n[bold cyan]Factory Reset Preview[/bold cyan]\n")
            paths = get_paths()
            total_size = 0
            for path in paths:
                if path.exists:
                    console.print(f"  • {path.name}: {path.path} ({path.size_human})")
                    total_size += path.size_bytes
            console.print(f"\n  Total: {total_size / 1024:.1f} KB")
            console.print("\n  [dim]This would remove all SCC data.[/dim]")
            return

        if not _confirm_factory_reset(yes, force, non_interactive):
            raise typer.Exit(EXIT_CANCELLED)

        try:
            with MaintenanceLock():
                factory_results = factory_reset(
                    dry_run=dry_run,
                    create_backup=not no_backup,
                    continue_on_error=continue_on_error,
                )

                if json_output:
                    _print_json_results(factory_results)
                else:
                    console.print()
                    for result in factory_results:
                        _print_result(result)
                    console.print()
                    total_bytes = sum(r.bytes_freed for r in factory_results)
                    console.print(f"[bold]Total freed: {total_bytes / 1024:.1f} KB[/bold]")

                if not all(r.success for r in factory_results):
                    raise typer.Exit(1)

        except MaintenanceLockError as e:
            console.print(f"[red]Error: {e}[/red]")
            raise typer.Exit(1)

        return

    # Build list of operations to perform
    operations: list[tuple[str, Callable[..., ResetResult], RiskTier, dict]] = []

    if cache:
        operations.append(("clear_cache", clear_cache, RiskTier.SAFE, {}))

    if exceptions_expired:
        operations.append(
            ("cleanup_expired_exceptions", cleanup_expired_exceptions, RiskTier.SAFE, {})
        )

    if contexts:
        operations.append(("clear_contexts", clear_contexts, RiskTier.CHANGES_STATE, {}))

    if containers:
        operations.append(("prune_containers", prune_containers, RiskTier.CHANGES_STATE, {}))

    if sessions:
        operations.append(("prune_sessions", prune_sessions, RiskTier.CHANGES_STATE, {}))

    if exceptions:
        scope = exceptions_scope or "all"
        operations.append(
            ("reset_exceptions", reset_exceptions, RiskTier.DESTRUCTIVE, {"scope": scope})
        )

    if sessions_all:
        operations.append(("delete_all_sessions", delete_all_sessions, RiskTier.DESTRUCTIVE, {}))

    if config_flag:
        operations.append(("reset_config", reset_config, RiskTier.DESTRUCTIVE, {}))

    # Handle --plan mode
    if plan:
        console.print("\n[bold cyan]Reset Preview[/bold cyan]\n")
        for action_id, _, tier, kwargs in operations:
            preview = preview_operation(action_id, **kwargs)
            _print_preview(preview)
        return

    # Get confirmation based on max risk tier
    max_tier = _max_risk([tier for _, _, tier, _ in operations])

    if max_tier == RiskTier.CHANGES_STATE and not yes:
        action_names = ", ".join(aid for aid, _, _, _ in operations)
        if not _confirm_tier_1(action_names, yes, non_interactive):
            raise typer.Exit(EXIT_CANCELLED)
    elif max_tier == RiskTier.DESTRUCTIVE and not yes:
        # Show previews for destructive operations
        for action_id, _, tier, kwargs in operations:
            if tier == RiskTier.DESTRUCTIVE:
                preview = preview_operation(action_id, **kwargs)
                _print_preview(preview)

        if not Confirm.ask("\n[bold]Proceed with destructive operations?[/bold]"):
            raise typer.Exit(EXIT_CANCELLED)

    # Execute operations
    results: list[ResetResult] = []

    try:
        with MaintenanceLock():
            for action_id, func, tier, kwargs in operations:
                # Add common kwargs
                kwargs["dry_run"] = dry_run
                if tier == RiskTier.DESTRUCTIVE:
                    kwargs["create_backup"] = not no_backup

                try:
                    result = func(**kwargs)
                    results.append(result)

                    if not json_output:
                        _print_result(result)

                    if not result.success and not continue_on_error:
                        break

                except Exception as e:
                    result = ResetResult(
                        success=False,
                        action_id=action_id,
                        risk_tier=tier,
                        error=str(e),
                        message=f"Failed: {e}",
                    )
                    results.append(result)

                    if not json_output:
                        _print_result(result)

                    if not continue_on_error:
                        break

    except MaintenanceLockError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)

    if json_output:
        _print_json_results(results)

    # Exit with error if any failed
    if not all(r.success for r in results):
        raise typer.Exit(1)

    raise typer.Exit(EXIT_SUCCESS)
