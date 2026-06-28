"""Launch an already-selected workspace through the shared launch pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path

from rich.console import Console
from rich.status import Status

from scc_cli import bootstrap, config
from scc_cli.application.start_session import StartSessionRequest
from scc_cli.commands.launch import (
    dependencies,
    preflight,
    render,
    team_settings,
)
from scc_cli.commands.launch import workspace as launch_workspace
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.ports.config_models import NormalizedOrgConfig
from scc_cli.theme import Spinners

from .completion import (
    PreparedLaunchCompletionDecision,
    PreparedLaunchCompletionRequest,
    complete_prepared_launch,
)


class ResolvedWorkspaceLaunchDecision(Enum):
    """Outcomes for launching a workspace that has already been selected."""

    LAUNCHED = auto()
    CANCELLED = auto()
    KEPT_EXISTING = auto()


@dataclass(frozen=True)
class ResolvedWorkspaceLaunchRequest:
    """Inputs needed to launch a selected workspace."""

    workspace_path: Path
    team: str | None
    session_name: str | None
    resume: bool
    resume_provider: str | None = None
    branch_override: str | None = None


@dataclass(frozen=True)
class ResolvedWorkspaceLaunchResult:
    """Result from the selected-workspace launch pipeline."""

    decision: ResolvedWorkspaceLaunchDecision
    message: str | None = None


def launch_resolved_workspace(
    request: ResolvedWorkspaceLaunchRequest,
    *,
    console: Console,
) -> ResolvedWorkspaceLaunchResult:
    """Run the standard live launch sequence for a selected workspace.

    Dashboard callers own local validation and return-type mapping. This helper
    centralizes their shared launch sequence until the remaining S04 launch paths
    converge.
    """
    try:
        adapters = bootstrap.get_default_adapters()

        with Status("[cyan]Checking Docker...[/cyan]", console=console, spinner=Spinners.DOCKER):
            adapters.sandbox_runtime.ensure_available()

        workspace_path = launch_workspace.validate_and_resolve_workspace(
            str(request.workspace_path)
        )
        if workspace_path is None:
            console.print("[red]Workspace validation failed[/red]")
            return ResolvedWorkspaceLaunchResult(
                decision=ResolvedWorkspaceLaunchDecision.CANCELLED,
                message="Start cancelled",
            )

        cfg = config.load_user_config()
        team_settings._configure_team_settings(request.team, cfg)
        raw_org_config = config.load_cached_org_config()
        normalized_org = (
            NormalizedOrgConfig.from_dict(raw_org_config) if raw_org_config is not None else None
        )

        resolved_provider, resolution_source = preflight.resolve_launch_provider(
            cli_flag=None,
            resume_provider=request.resume_provider,
            workspace_path=workspace_path,
            config_provider=config.get_selected_provider(),
            normalized_org=normalized_org,
            team=request.team,
            adapters=adapters,
            non_interactive=False,
        )
        if resolved_provider is None:
            return ResolvedWorkspaceLaunchResult(
                decision=ResolvedWorkspaceLaunchDecision.CANCELLED,
                message="Start cancelled",
            )

        readiness = preflight.collect_launch_readiness(
            resolved_provider,
            resolution_source,
            adapters,
        )
        if not readiness.launch_ready:
            preflight.ensure_launch_ready(
                readiness,
                adapters=adapters,
                console=console,
                non_interactive=False,
                show_notice=render.show_auth_bootstrap_panel,
            )

        start_request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=request.team,
            session_name=request.session_name,
            resume=request.resume,
            fresh=False,
            offline=False,
            standalone=request.team is None,
            dry_run=False,
            allow_suspicious=False,
            org_config=normalized_org,
            raw_org_config=raw_org_config,
            org_config_url=None,
            provider_id=resolved_provider,
        )
        start_dependencies, start_plan = dependencies.prepare_live_start_plan(
            start_request,
            adapters=adapters,
            console=console,
            provider_id=resolved_provider,
        )
        if start_dependencies.agent_provider is None:
            console.print("[red]Provider wiring is unavailable for this start request[/red]")
            return ResolvedWorkspaceLaunchResult(
                decision=ResolvedWorkspaceLaunchDecision.CANCELLED,
                message="Start cancelled",
            )

        current_branch = request.branch_override or start_plan.current_branch
        if request.team:
            console.print(f"[dim]Team: {request.team}[/dim]")
        if current_branch:
            console.print(f"[dim]Branch: {current_branch}[/dim]")
        console.print()

        completion_result = complete_prepared_launch(
            PreparedLaunchCompletionRequest(
                workspace_path=workspace_path,
                team=request.team,
                session_name=request.session_name,
                current_branch=current_branch,
                provider_id=resolved_provider,
                start_plan=start_plan,
                dependencies=start_dependencies,
                is_resume=request.resume,
                json_mode=False,
                non_interactive=False,
                record_session=False,
            ),
            console=console,
        )
        if completion_result.decision is PreparedLaunchCompletionDecision.KEPT_EXISTING:
            return ResolvedWorkspaceLaunchResult(
                decision=ResolvedWorkspaceLaunchDecision.KEPT_EXISTING,
                message=completion_result.message,
            )
        if completion_result.decision is PreparedLaunchCompletionDecision.CANCELLED:
            return ResolvedWorkspaceLaunchResult(
                decision=ResolvedWorkspaceLaunchDecision.CANCELLED,
                message=completion_result.message,
            )
        return ResolvedWorkspaceLaunchResult(
            decision=ResolvedWorkspaceLaunchDecision.LAUNCHED,
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        return ResolvedWorkspaceLaunchResult(
            decision=ResolvedWorkspaceLaunchDecision.CANCELLED,
            message="Start cancelled",
        )
    except ProviderNotReadyError as exc:
        console.print(f"[red]{exc.user_message}[/red]")
        if exc.suggested_action:
            console.print(f"[dim]{exc.suggested_action}[/dim]")
        return ResolvedWorkspaceLaunchResult(
            decision=ResolvedWorkspaceLaunchDecision.CANCELLED,
            message="Start cancelled",
        )
    except Exception as exc:
        console.print(f"[red]Error starting session: {exc}[/red]")
        return ResolvedWorkspaceLaunchResult(
            decision=ResolvedWorkspaceLaunchDecision.CANCELLED,
            message="Start cancelled",
        )
