"""Dev-environment bridge commands."""

from __future__ import annotations

from pathlib import Path

import typer

from scc_cli import config, workspace_local_config
from scc_cli.application.compute_effective_config import compute_effective_config
from scc_cli.application.dev_environment_bridge import (
    DEFAULT_OUTPUT_LIMIT_BYTES,
    RunDevEnvironmentCommandDependencies,
    RunDevEnvironmentCommandRequest,
    RunDevEnvironmentCommandResult,
    run_dev_environment_command,
)
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
)
from scc_cli.services.config_normalizer import normalize_org_config
from scc_cli.services.dev_environment_command_runner import run_subprocess_bounded

from .launch.workspace import resolve_workspace_team

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
) -> RunDevEnvironmentCommandResult:
    workspace_path = _resolve_workspace_path(workspace)
    user_config = config.load_user_config()
    org_config = config.load_cached_org_config()
    if not org_config:
        raise ConfigError(
            user_message="No organization config found for dev environment commands.",
            suggested_action="Run 'scc setup --org <source>' before using 'scc dev run'.",
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
            suggested_action="Run 'scc team switch <team>' or pass 'scc dev run --team <team>'.",
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

    return run_dev_environment_command(
        RunDevEnvironmentCommandRequest(
            command_name=command_name,
            workspace_path=workspace_path,
            effective_config=effective,
            team_name=resolved_team,
            team_source=team_source,
            provider_id=provider_id,
            provider_source=provider_source,
            output_limit_bytes=output_limit_bytes,
        ),
        dependencies=RunDevEnvironmentCommandDependencies(
            audit_sink=_require_audit_sink(),
            command_runner=run_subprocess_bounded,
        ),
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
    console.print(f"[bold cyan]Dev environment command[/bold cyan] {result.command_name}")
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
