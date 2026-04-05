"""Launch flow helpers for the start command.

This module contains the start() CLI entrypoint. Interactive wizard flows
live in flow_interactive.py; session resolution and personal profile helpers
live in flow_session.py.

Re-exports public names for backward compatibility.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.status import Status

from ... import config, sessions, setup
from ...application.launch import finalize_launch
from ...application.start_session import StartSessionRequest
from ...bootstrap import get_default_adapters
from ...cli_common import console, err_console
from ...core.errors import WorkspaceNotFoundError
from ...core.exit_codes import EXIT_CANCELLED, EXIT_CONFIG, EXIT_ERROR, EXIT_USAGE
from ...core.provider_resolution import get_provider_display_name
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_info_panel
from ...ports.config_models import NormalizedOrgConfig
from ...presentation.json.launch_json import build_start_dry_run_envelope
from ...presentation.launch_presenter import build_sync_output_view_model, render_launch_output
from ...theme import Spinners
from ...ui.chrome import print_with_layout
from .dependencies import prepare_live_start_plan
from .flow_interactive import interactive_start, run_start_wizard_flow
from .flow_session import (
    _apply_personal_profile,
    _record_session_and_context,
    _resolve_session_selection,
)
from .render import build_dry_run_data, show_dry_run_panel, show_launch_panel, warn_if_non_worktree
from .team_settings import _configure_team_settings
from .workspace import prepare_workspace, resolve_workspace_team, validate_and_resolve_workspace

# Re-export public names for backward compatibility
__all__ = [
    "start",
    "interactive_start",
    "run_start_wizard_flow",
    "_resolve_session_selection",
    "_apply_personal_profile",
    "_record_session_and_context",
]


# ─────────────────────────────────────────────────────────────────────────────
# Provider resolution helper
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_provider(
    cli_flag: str | None,
    normalized_org: NormalizedOrgConfig | None,
    team: str | None,
) -> str:
    """Resolve the active provider from CLI flag, user config, and team policy."""
    from scc_cli.core.provider_resolution import resolve_active_provider

    allowed_providers: tuple[str, ...] = ()
    if normalized_org is not None and team:
        team_profile = normalized_org.get_profile(team)
        if team_profile is not None:
            allowed_providers = team_profile.allowed_providers

    return resolve_active_provider(
        cli_flag=cli_flag,
        config_provider=config.get_selected_provider(),
        allowed_providers=allowed_providers,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Start Command Flow
# ─────────────────────────────────────────────────────────────────────────────


def start(
    workspace: str | None = typer.Argument(None, help="Path to workspace (optional)"),
    team: str | None = typer.Option(None, "-t", "--team", help="Team profile to use"),
    session_name: str | None = typer.Option(None, "--session", help="Session name"),
    resume: bool = typer.Option(False, "-r", "--resume", help="Resume most recent session"),
    select: bool = typer.Option(False, "-s", "--select", help="Select from recent sessions"),
    worktree_name: str | None = typer.Option(None, "-w", "--worktree", help="Worktree name"),
    fresh: bool = typer.Option(False, "--fresh", help="Force new container"),
    install_deps: bool = typer.Option(False, "--install-deps", help="Install dependencies"),
    offline: bool = typer.Option(False, "--offline", help="Use cached config only (error if none)"),
    standalone: bool = typer.Option(False, "--standalone", help="Run without organization config"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview config without launching"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        "--no-interactive",
        help="Fail fast if interactive input would be required",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        hidden=True,
    ),
    allow_suspicious_workspace: bool = typer.Option(
        False,
        "--allow-suspicious-workspace",
        help="Allow starting in suspicious directories (e.g., home, /tmp) in non-interactive mode",
    ),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Agent provider override (claude or codex)",
    ),
) -> None:
    """Start agent in a Docker sandbox.

    If no arguments provided, launches interactive mode.
    """
    from pathlib import Path  # noqa: F811

    # Capture original CWD for entry_dir tracking (before any directory changes)
    original_cwd = Path.cwd()

    if isinstance(debug, bool) and debug:
        err_console.print(
            "[red]Error:[/red] --debug is a global flag and must be placed before the command.",
            highlight=False,
        )
        err_console.print(
            "[dim]Use: scc --debug start <workspace>[/dim]",
            highlight=False,
        )
        err_console.print(
            "[dim]With uv: uv run scc --debug start <workspace>[/dim]",
            highlight=False,
        )
        raise typer.Exit(EXIT_USAGE)

    # ── Fast Fail: Validate mode flags before any processing ──────────────────
    from scc_cli.ui.gate import validate_mode_flags

    validate_mode_flags(
        json_mode=(json_output or pretty),
        select=select,
    )

    # ── Step 0: Handle --standalone mode (skip org config entirely) ───────────
    if standalone:
        team = None
        if not json_output and not pretty:
            console.print("[dim]Running in standalone mode (no organization config)[/dim]")

    org_config: dict[str, Any] | None = None

    # ── Step 0.5: Handle --offline mode (cache-only, fail fast) ───────────────
    if offline and not standalone:
        org_config = config.load_cached_org_config()
        if org_config is None:
            err_console.print(
                "[red]Error:[/red] --offline requires cached organization config.\n"
                "[dim]Run 'scc setup' first to cache your org config.[/dim]",
                highlight=False,
            )
            raise typer.Exit(EXIT_CONFIG)
        if not json_output and not pretty:
            console.print("[dim]Using cached organization config (offline mode)[/dim]")

    # ── Step 1: First-run detection ──────────────────────────────────────────
    if not standalone and not offline and setup.is_setup_needed():
        if not setup.maybe_run_setup(console):
            raise typer.Exit(1)

    cfg = config.load_user_config()
    adapters = get_default_adapters()
    session_service = sessions.get_session_service(adapters.filesystem)

    # ── Step 2: Session selection (interactive, --select, --resume) ──────────
    workspace, team, session_name, worktree_name, cancelled, was_auto_detected = (
        _resolve_session_selection(
            workspace=workspace,
            team=team,
            resume=resume,
            select=select,
            cfg=cfg,
            json_mode=(json_output or pretty),
            standalone_override=standalone,
            no_interactive=non_interactive,
            dry_run=dry_run,
            session_service=session_service,
        )
    )
    if workspace is None:
        if cancelled:
            if not json_output and not pretty:
                console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(EXIT_CANCELLED)
        if select or resume:
            raise typer.Exit(EXIT_ERROR)
        raise typer.Exit(EXIT_CANCELLED)

    # ── Step 3: Docker availability check ────────────────────────────────────
    if not dry_run:
        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            adapters.sandbox_runtime.ensure_available()

    # ── Step 4: Workspace validation and platform checks ─────────────────────
    workspace_path = validate_and_resolve_workspace(
        workspace,
        no_interactive=non_interactive,
        allow_suspicious=allow_suspicious_workspace,
        json_mode=(json_output or pretty),
    )
    if workspace_path is None:
        if not json_output and not pretty:
            console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(EXIT_CANCELLED)
    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # ── Step 5: Workspace preparation (worktree, deps, git safety) ───────────
    if not dry_run:
        workspace_path = prepare_workspace(workspace_path, worktree_name, install_deps)
    assert workspace_path is not None

    # ── Step 5.5: Resolve team from workspace pinning ────────────────────────
    team = resolve_workspace_team(
        workspace_path,
        team,
        cfg,
        json_mode=(json_output or pretty),
        standalone=standalone,
        no_interactive=non_interactive,
    )

    # ── Step 6: Team configuration ───────────────────────────────────────────
    if not dry_run and not standalone:
        _configure_team_settings(team, cfg)

    if org_config is None and team and not standalone:
        org_config = config.load_cached_org_config()

    if worktree_name:
        was_auto_detected = False

    workspace_arg = None if was_auto_detected else str(workspace_path)

    # ── Step 6.1: Resolve active provider ────────────────────────────────────
    normalized_org = NormalizedOrgConfig.from_dict(org_config) if org_config is not None else None
    # Normalize typer default: direct calls pass OptionInfo, not None.
    cli_provider = provider if isinstance(provider, str) else None
    resolved_provider = _resolve_provider(cli_provider, normalized_org, team)

    start_request = StartSessionRequest(
        workspace_path=workspace_path,
        workspace_arg=workspace_arg,
        entry_dir=original_cwd,
        team=team,
        session_name=session_name,
        resume=resume,
        fresh=fresh,
        offline=offline,
        standalone=standalone,
        dry_run=dry_run,
        allow_suspicious=allow_suspicious_workspace,
        org_config=normalized_org,
        raw_org_config=org_config,
        provider_id=resolved_provider,
    )
    start_dependencies, start_plan = prepare_live_start_plan(
        start_request,
        adapters=adapters,
        console=console,
        provider_id=resolved_provider,
    )

    output_view_model = build_sync_output_view_model(start_plan)
    render_launch_output(output_view_model, console=console, json_mode=(json_output or pretty))

    # ── Step 6.55: Apply personal profile (local overlay) ─────────────────────
    personal_profile_id = None
    personal_applied = False
    if not dry_run and workspace_path is not None:
        personal_profile_id, personal_applied = _apply_personal_profile(
            workspace_path,
            org_config=org_config,
            json_mode=(json_output or pretty),
            non_interactive=non_interactive,
            profile_service=adapters.personal_profile_service,
        )

    # ── Step 6.6: Active stack summary ───────────────────────────────────────
    if not (json_output or pretty) and workspace_path is not None:
        personal_label = "project" if personal_profile_id else "none"
        if personal_profile_id and not personal_applied:
            personal_label = "skipped"
        workspace_label = (
            "overrides"
            if adapters.personal_profile_service.workspace_has_overrides(workspace_path)
            else "none"
        )
        print_with_layout(
            console,
            "[dim]Active stack:[/dim] "
            f"Team: {team or 'standalone'} | "
            f"Personal: {personal_label} | "
            f"Workspace: {workspace_label}",
        )

    # ── Step 6.7: Resolve mount path for worktrees (needed for dry-run too) ────
    assert workspace_path is not None
    resolver_result = start_plan.resolver_result
    if resolver_result.is_mount_expanded and not (json_output or pretty):
        console.print()
        print_with_layout(
            console,
            create_info_panel(
                "Worktree Detected",
                f"Mounting parent directory for worktree support:\n{resolver_result.mount_root}",
                "Both worktree and main repo will be accessible",
            ),
            constrain=True,
        )
        console.print()
    current_branch = start_plan.current_branch

    # ── Step 6.8: Handle --dry-run (preview without launching) ────────────────
    if dry_run:
        result = start_plan.resolver_result
        org_config_for_dry_run = config.load_cached_org_config()
        dry_run_data = build_dry_run_data(
            workspace_path=workspace_path,
            team=team,
            org_config=org_config_for_dry_run,
            project_config=None,
            entry_dir=result.entry_dir,
            mount_root=result.mount_root,
            container_workdir=result.container_workdir,
            resolution_reason=result.reason,
        )

        if pretty:
            json_output = True

        if json_output:
            with json_output_mode():
                if pretty:
                    set_pretty_mode(True)
                try:
                    envelope = build_start_dry_run_envelope(dry_run_data)
                    print_json(envelope)
                finally:
                    if pretty:
                        set_pretty_mode(False)
        else:
            show_dry_run_panel(dry_run_data)

        raise typer.Exit(0)

    warn_if_non_worktree(workspace_path, json_mode=(json_output or pretty))

    # ── Step 8: Launch sandbox ───────────────────────────────────────────────
    _record_session_and_context(
        workspace_path,
        team,
        session_name,
        current_branch,
    )
    show_launch_panel(
        workspace=workspace_path,
        team=team,
        session_name=session_name,
        branch=current_branch,
        is_resume=False,
        display_name=get_provider_display_name(resolved_provider),
    )
    finalize_launch(start_plan, dependencies=start_dependencies)
