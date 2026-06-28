"""Launch a freshly created worktree after `scc worktree create`."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from scc_cli import config
from scc_cli.application.launch import finalize_launch
from scc_cli.application.start_session import StartSessionRequest
from scc_cli.bootstrap import DefaultAdapters
from scc_cli.core.exit_codes import EXIT_CANCELLED
from scc_cli.panels import create_warning_panel
from scc_cli.ports.config_models import NormalizedOrgConfig

from .dependencies import prepare_live_start_plan
from .preflight import collect_launch_readiness, ensure_launch_ready, resolve_launch_provider


@dataclass(frozen=True)
class CreatedWorktreeLaunchRequest:
    """Inputs for auto-starting an agent in a newly created worktree."""

    worktree_path: Path


def launch_created_worktree(
    request: CreatedWorktreeLaunchRequest,
    *,
    adapters: DefaultAdapters,
    console: Console,
) -> None:
    """Start a newly created worktree without changing the legacy auto-start tail."""
    adapters.sandbox_runtime.ensure_available()
    user_config = config.load_user_config()
    standalone_mode = config.is_standalone_mode()
    team = None if standalone_mode else user_config.get("selected_profile")
    raw_org_config = None if standalone_mode else config.load_cached_org_config()
    normalized_org = (
        NormalizedOrgConfig.from_dict(raw_org_config) if raw_org_config is not None else None
    )

    resolved_provider, resolution_source = resolve_launch_provider(
        cli_flag=None,
        resume_provider=None,
        workspace_path=request.worktree_path,
        config_provider=user_config.get("selected_provider"),
        normalized_org=normalized_org,
        team=team,
        adapters=adapters,
        non_interactive=False,
    )
    if resolved_provider is None:
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(EXIT_CANCELLED)

    readiness = collect_launch_readiness(resolved_provider, resolution_source, adapters)
    if not readiness.launch_ready:
        ensure_launch_ready(
            readiness,
            adapters=adapters,
            console=console,
            non_interactive=False,
            show_notice=lambda title, content, subtitle: console.print(
                create_warning_panel(title, content, subtitle)
            ),
        )

    start_request = StartSessionRequest(
        workspace_path=request.worktree_path,
        workspace_arg=str(request.worktree_path),
        entry_dir=request.worktree_path,
        team=team,
        session_name=None,
        resume=False,
        fresh=False,
        offline=False,
        standalone=standalone_mode,
        dry_run=False,
        allow_suspicious=False,
        org_config=normalized_org,
        raw_org_config=raw_org_config,
        provider_id=resolved_provider,
    )
    start_dependencies, start_plan = prepare_live_start_plan(
        start_request,
        adapters=adapters,
        console=console,
        provider_id=resolved_provider,
    )
    finalize_launch(start_plan, dependencies=start_dependencies)
