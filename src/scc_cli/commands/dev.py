"""Dev-environment bridge commands."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import typer

from scc_cli import config, workspace_local_config
from scc_cli.application.compute_effective_config import compute_effective_config
from scc_cli.application.dev_environment_bridge import (
    DEFAULT_OUTPUT_LIMIT_BYTES,
    DEV_ENVIRONMENT_COMMAND_ACTION,
    DEV_ENVIRONMENT_HEALTH_CHECK_ACTION,
    DEV_ENVIRONMENT_LOG_ACTION,
    DevEnvironmentActionKind,
    RunDevEnvironmentCommandDependencies,
    RunDevEnvironmentCommandRequest,
    RunDevEnvironmentCommandResult,
    run_dev_environment_command,
)
from scc_cli.application.effective_config_models import DevEnvironmentCommand, EffectiveConfig
from scc_cli.bootstrap import get_default_adapters
from scc_cli.cli_common import console, handle_errors
from scc_cli.core.errors import (
    ConfigError,
    DevEnvironmentAuditWriteError,
    WorkspaceError,
    WorkspaceNotFoundError,
)
from scc_cli.core.exit_codes import EXIT_TOOL
from scc_cli.output_mode import json_command_mode, json_output_mode, print_json, set_pretty_mode
from scc_cli.ports.audit_event_sink import AuditEventSink
from scc_cli.presentation.json.dev_environment_json import (
    build_dev_environment_command_envelope,
    build_dev_environment_status_data,
    build_dev_environment_status_envelope,
)
from scc_cli.services.config_normalizer import normalize_org_config
from scc_cli.services.dev_environment_command_runner import run_subprocess_bounded

from .launch.workspace import resolve_workspace_team


@dataclass(frozen=True)
class _DevEnvironmentContext:
    workspace_path: Path
    effective_config: EffectiveConfig
    team_name: str
    team_source: str
    provider_id: str | None
    provider_source: str


dev_app = typer.Typer(
    name="dev",
    help="Host-owned dev environment bridge commands.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@dev_app.command("run")
@handle_errors
def dev_run_cmd(
    command_name: str = typer.Argument(..., help="Named dev_environment command to run."),
    workspace: str = typer.Argument(".", help="Workspace path. Defaults to current directory."),
    team: str | None = typer.Option(None, "--team", "-t", help="Team profile to use."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Provider identity to include in audit metadata.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON."),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
    output_limit_bytes: int = typer.Option(
        DEFAULT_OUTPUT_LIMIT_BYTES,
        "--output-limit-bytes",
        min=0,
        help="Maximum stdout/stderr tail bytes to keep in memory per stream.",
    ),
) -> None:
    """Run one approved named dev-environment command from effective config."""
    _run_and_render_dev_action(
        command_name=command_name,
        workspace=workspace,
        team=team,
        provider=provider,
        output_limit_bytes=output_limit_bytes,
        json_output=json_output,
        pretty=pretty,
        action_type=DEV_ENVIRONMENT_COMMAND_ACTION,
    )


@dev_app.command("logs")
@handle_errors
def dev_logs_cmd(
    log_name: str = typer.Argument(..., help="Named dev_environment log action to run."),
    workspace: str = typer.Argument(".", help="Workspace path. Defaults to current directory."),
    team: str | None = typer.Option(None, "--team", "-t", help="Team profile to use."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Provider identity to include in audit metadata.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON."),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
    output_limit_bytes: int = typer.Option(
        DEFAULT_OUTPUT_LIMIT_BYTES,
        "--output-limit-bytes",
        min=0,
        help="Maximum stdout/stderr tail bytes to keep in memory per stream.",
    ),
) -> None:
    """Run one approved named dev-environment log action."""
    _run_and_render_dev_action(
        command_name=log_name,
        workspace=workspace,
        team=team,
        provider=provider,
        output_limit_bytes=output_limit_bytes,
        json_output=json_output,
        pretty=pretty,
        action_type=DEV_ENVIRONMENT_LOG_ACTION,
    )


@dev_app.command("health")
@handle_errors
def dev_health_cmd(
    health_check_name: str = typer.Argument(..., help="Named dev_environment health check to run."),
    workspace: str = typer.Argument(".", help="Workspace path. Defaults to current directory."),
    team: str | None = typer.Option(None, "--team", "-t", help="Team profile to use."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Provider identity to include in audit metadata.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output result as JSON."),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
    output_limit_bytes: int = typer.Option(
        DEFAULT_OUTPUT_LIMIT_BYTES,
        "--output-limit-bytes",
        min=0,
        help="Maximum stdout/stderr tail bytes to keep in memory per stream.",
    ),
) -> None:
    """Run one approved named dev-environment health check."""
    _run_and_render_dev_action(
        command_name=health_check_name,
        workspace=workspace,
        team=team,
        provider=provider,
        output_limit_bytes=output_limit_bytes,
        json_output=json_output,
        pretty=pretty,
        action_type=DEV_ENVIRONMENT_HEALTH_CHECK_ACTION,
    )


@dev_app.command("status")
@handle_errors
def dev_status_cmd(
    workspace: str = typer.Argument(".", help="Workspace path. Defaults to current directory."),
    team: str | None = typer.Option(None, "--team", "-t", help="Team profile to use."),
    provider: str | None = typer.Option(
        None,
        "--provider",
        help="Provider identity to include in status metadata.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output status as JSON."),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON output."),
) -> None:
    """Show effective dev-environment bridge status for this workspace."""
    if pretty:
        json_output = True
        set_pretty_mode(True)

    context = _resolve_dev_context(
        workspace=workspace,
        team=team,
        provider=provider,
        json_mode=json_output,
    )
    if json_output:
        with json_output_mode(), json_command_mode():
            data = build_dev_environment_status_data(
                effective=context.effective_config,
                workspace_path=str(context.workspace_path),
                team_name=context.team_name,
                team_source=context.team_source,
                provider_id=context.provider_id,
                provider_source=context.provider_source,
            )
            print_json(build_dev_environment_status_envelope(data))
            raise typer.Exit(0)

    _render_dev_status(context)
    raise typer.Exit(0)


def _run_and_render_dev_action(
    *,
    command_name: str,
    workspace: str,
    team: str | None,
    provider: str | None,
    output_limit_bytes: int,
    json_output: bool,
    pretty: bool,
    action_type: DevEnvironmentActionKind,
) -> None:
    if pretty:
        json_output = True
        set_pretty_mode(True)

    if json_output:
        with json_output_mode(), json_command_mode():
            result = _run_dev_command(
                command_name=command_name,
                workspace=workspace,
                team=team,
                provider=provider,
                output_limit_bytes=output_limit_bytes,
                json_mode=True,
                action_type=action_type,
            )
            print_json(build_dev_environment_command_envelope(result))
            raise typer.Exit(0 if result.status == "succeeded" else EXIT_TOOL)

    result = _run_dev_command(
        command_name=command_name,
        workspace=workspace,
        team=team,
        provider=provider,
        output_limit_bytes=output_limit_bytes,
        json_mode=False,
        action_type=action_type,
    )
    _render_dev_command_result(result)
    raise typer.Exit(0 if result.status == "succeeded" else EXIT_TOOL)


def _run_dev_command(
    *,
    command_name: str,
    workspace: str,
    team: str | None,
    provider: str | None,
    output_limit_bytes: int,
    json_mode: bool,
    action_type: DevEnvironmentActionKind = DEV_ENVIRONMENT_COMMAND_ACTION,
) -> RunDevEnvironmentCommandResult:
    context = _resolve_dev_context(
        workspace=workspace,
        team=team,
        provider=provider,
        json_mode=json_mode,
    )

    return run_dev_environment_command(
        RunDevEnvironmentCommandRequest(
            command_name=command_name,
            workspace_path=context.workspace_path,
            effective_config=context.effective_config,
            team_name=context.team_name,
            team_source=context.team_source,
            provider_id=context.provider_id,
            provider_source=context.provider_source,
            output_limit_bytes=output_limit_bytes,
            action_type=action_type,
        ),
        dependencies=RunDevEnvironmentCommandDependencies(
            audit_sink=_require_audit_sink(),
            command_runner=run_subprocess_bounded,
        ),
    )


def _resolve_dev_context(
    *,
    workspace: str,
    team: str | None,
    provider: str | None,
    json_mode: bool,
) -> _DevEnvironmentContext:
    workspace_path = _resolve_workspace_path(workspace)
    user_config = config.load_user_config()
    org_config = config.load_cached_org_config()
    if not org_config:
        raise ConfigError(
            user_message="No organization config found for dev environment commands.",
            suggested_action="Run 'scc setup --org <source>' before using 'scc dev'.",
        )

    resolved_team = resolve_workspace_team(
        workspace_path,
        team,
        user_config,
        json_mode=json_mode,
        no_interactive=json_mode,
    )
    team_source = _team_source(team, user_config, workspace_path, resolved_team)
    if not resolved_team:
        raise ConfigError(
            user_message="No team selected for dev environment commands.",
            suggested_action="Run 'scc team switch <team>' or pass 'scc dev --team <team>'.",
        )

    provider_id, provider_source = _resolve_provider_for_audit(
        workspace_path,
        provider,
        user_config,
    )
    normalized = normalize_org_config(org_config)
    effective = compute_effective_config(
        org_config=normalized,
        team_name=resolved_team,
        workspace_path=workspace_path,
    )
    return _DevEnvironmentContext(
        workspace_path=workspace_path,
        effective_config=effective,
        team_name=resolved_team,
        team_source=team_source,
        provider_id=provider_id,
        provider_source=provider_source,
    )


def _resolve_workspace_path(workspace: str) -> Path:
    path = Path(workspace).expanduser()
    if not path.exists():
        raise WorkspaceNotFoundError(path=str(path))
    if not path.is_dir():
        raise WorkspaceError(
            user_message=f"Workspace is not a directory: {path}",
            suggested_action="Pass a workspace directory to 'scc dev run'.",
        )
    return path.resolve(strict=False)


def _require_audit_sink() -> AuditEventSink:
    sink = get_default_adapters().audit_event_sink
    if sink is None:
        raise DevEnvironmentAuditWriteError(
            event_type="dev_environment.command.started",
            audit_destination="unconfigured audit sink",
            reason="Audit sink is not configured.",
        )
    return sink


def _team_source(
    explicit_team: str | None,
    user_config: dict[str, object],
    workspace_path: Path,
    resolved_team: str | None,
) -> str:
    if explicit_team:
        return "cli"
    selected = user_config.get("selected_profile")
    if isinstance(selected, str) and selected == resolved_team:
        return "selected_profile"
    pinned = config.get_workspace_team_from_config(user_config, workspace_path)
    if pinned and pinned == resolved_team:
        return "workspace"
    return ""


def _resolve_provider_for_audit(
    workspace_path: Path,
    explicit_provider: str | None,
    user_config: dict[str, object],
) -> tuple[str | None, str]:
    if explicit_provider:
        return explicit_provider, "cli"
    workspace_provider = workspace_local_config.get_workspace_last_used_provider(workspace_path)
    if workspace_provider:
        return workspace_provider, "workspace"
    selected_provider = user_config.get("selected_provider")
    if isinstance(selected_provider, str) and selected_provider != "ask":
        return selected_provider, "selected_provider"
    return None, ""


def _render_dev_command_result(result: RunDevEnvironmentCommandResult) -> None:
    color = "green" if result.status == "succeeded" else "red"
    console.print(
        f"[bold cyan]Dev environment {_action_label(result.action_type)}[/bold cyan] "
        f"{result.command_name}"
    )
    console.print(f"Status: [{color}]{result.status}[/{color}]")
    if result.exit_code is not None:
        console.print(f"Exit code: {result.exit_code}")
    if result.timed_out:
        console.print("Timed out: true")
    console.print(f"Working directory: {result.cwd}")
    console.print(f"Duration: {result.duration_ms} ms")
    console.print(f"Team: {result.team_name or '-'} ({result.team_source or 'unknown'})")
    if result.provider_id:
        console.print(f"Provider: {result.provider_id} ({result.provider_source})")

    if result.stdout.tail:
        console.print()
        console.print("[bold]stdout[/bold]")
        console.print(result.stdout.tail, highlight=False)
        if result.stdout.truncated:
            console.print(f"[dim]stdout truncated to last {len(result.stdout.tail)} bytes[/dim]")
    if result.stderr.tail:
        console.print()
        console.print("[bold]stderr[/bold]")
        console.print(result.stderr.tail, highlight=False)
        if result.stderr.truncated:
            console.print(f"[dim]stderr truncated to last {len(result.stderr.tail)} bytes[/dim]")


def _render_dev_status(context: _DevEnvironmentContext) -> None:
    console.print("[bold cyan]Dev environment bridge[/bold cyan]")
    console.print(f"Workspace: {context.workspace_path}")
    console.print(f"Team: {context.team_name} ({context.team_source or 'unknown'})")
    if context.provider_id:
        console.print(f"Provider: {context.provider_id} ({context.provider_source})")
    console.print()
    _render_action_list("Commands", context.effective_config.dev_environment_commands)
    _render_action_list("Logs", context.effective_config.dev_environment_logs)
    _render_action_list("Health checks", context.effective_config.dev_environment_health_checks)


def _render_action_list(title: str, actions: list[DevEnvironmentCommand]) -> None:
    console.print(f"[bold]{title}[/bold]")
    if not actions:
        console.print("  [dim]None configured[/dim]")
        return
    for action in actions:
        console.print(f"  [green]✓[/green] {action.name}")
        if action.description:
            console.print(f"      [dim]{action.description}[/dim]")
        console.print(f"      argv: {' '.join(action.argv)}")
        console.print(f"      working_directory: {action.working_directory}")
        console.print(f"      timeout_seconds: {action.timeout_seconds}")


def _action_label(action_type: DevEnvironmentActionKind) -> str:
    if action_type == DEV_ENVIRONMENT_LOG_ACTION:
        return "log"
    if action_type == DEV_ENVIRONMENT_HEALTH_CHECK_ACTION:
        return "health check"
    return "command"
