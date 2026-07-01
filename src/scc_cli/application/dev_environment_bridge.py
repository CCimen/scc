"""Approved host-owned dev-environment command bridge."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from scc_cli.application.effective_config_models import DevEnvironmentCommand, EffectiveConfig
from scc_cli.core.contracts import AuditEvent
from scc_cli.core.enums import SeverityLevel
from scc_cli.core.errors import (
    DevEnvironmentAuditWriteError,
    DevEnvironmentCommandDeniedError,
)
from scc_cli.ports.audit_event_sink import AuditEventSink

DEFAULT_OUTPUT_LIMIT_BYTES = 8192


@dataclass(frozen=True)
class CapturedStream:
    """Bounded command stream result."""

    tail: str
    total_bytes: int
    truncated: bool


@dataclass(frozen=True)
class CommandExecutionSpec:
    """Concrete subprocess invocation after policy validation."""

    argv: tuple[str, ...]
    cwd: Path
    timeout_seconds: int
    output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES


@dataclass(frozen=True)
class CommandExecutionResult:
    """Result returned by the bounded command runner."""

    exit_code: int | None
    timed_out: bool
    stdout: CapturedStream
    stderr: CapturedStream
    duration_ms: int


CommandRunner = Callable[[CommandExecutionSpec], CommandExecutionResult]


def _missing_command_runner(spec: CommandExecutionSpec) -> CommandExecutionResult:
    raise RuntimeError("Dev environment command runner is not configured")


@dataclass(frozen=True)
class RunDevEnvironmentCommandRequest:
    """Inputs for one approved dev-environment command execution."""

    command_name: str
    workspace_path: Path
    effective_config: EffectiveConfig
    team_name: str | None
    team_source: str
    provider_id: str | None = None
    provider_source: str = ""
    output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES


@dataclass(frozen=True)
class RunDevEnvironmentCommandDependencies:
    """Injected edges for audit persistence and command execution."""

    audit_sink: AuditEventSink
    command_runner: CommandRunner = _missing_command_runner


@dataclass(frozen=True)
class RunDevEnvironmentCommandResult:
    """User-facing result for a named dev-environment command."""

    command_name: str
    argv: tuple[str, ...]
    cwd: Path
    status: str
    exit_code: int | None
    timed_out: bool
    duration_ms: int
    stdout: CapturedStream
    stderr: CapturedStream
    team_name: str | None
    team_source: str
    provider_id: str | None
    provider_source: str


class _CommandCwdDeniedError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def run_dev_environment_command(
    request: RunDevEnvironmentCommandRequest,
    *,
    dependencies: RunDevEnvironmentCommandDependencies,
) -> RunDevEnvironmentCommandResult:
    """Run one approved named dev-environment command."""
    workspace = request.workspace_path.expanduser().resolve(strict=False)
    command = _find_command(request.effective_config, request.command_name)
    if command is None:
        _append_audit_event(
            dependencies.audit_sink,
            _denied_event(request, workspace=workspace, reason="Command is not configured"),
        )
        raise DevEnvironmentCommandDeniedError(
            command_name=request.command_name,
            reason="Command is not configured in effective dev_environment.commands.",
        )

    try:
        cwd = _resolve_command_cwd(workspace, command)
    except _CommandCwdDeniedError as error:
        _append_audit_event(
            dependencies.audit_sink,
            _denied_event(request, workspace=workspace, reason=error.reason),
        )
        raise DevEnvironmentCommandDeniedError(
            command_name=command.name,
            reason=error.reason,
        ) from error
    _append_audit_event(
        dependencies.audit_sink,
        _started_event(request, workspace=workspace, command=command, cwd=cwd),
    )

    execution = dependencies.command_runner(
        CommandExecutionSpec(
            argv=command.argv,
            cwd=cwd,
            timeout_seconds=command.timeout_seconds,
            output_limit_bytes=request.output_limit_bytes,
        )
    )
    status = _status_for_execution(execution)
    _append_audit_event(
        dependencies.audit_sink,
        _result_event(
            request,
            workspace=workspace,
            command=command,
            cwd=cwd,
            execution=execution,
            status=status,
        ),
    )

    return RunDevEnvironmentCommandResult(
        command_name=command.name,
        argv=command.argv,
        cwd=cwd,
        status=status,
        exit_code=execution.exit_code,
        timed_out=execution.timed_out,
        duration_ms=execution.duration_ms,
        stdout=execution.stdout,
        stderr=execution.stderr,
        team_name=request.team_name,
        team_source=request.team_source,
        provider_id=request.provider_id,
        provider_source=request.provider_source,
    )


def _find_command(
    effective_config: EffectiveConfig,
    command_name: str,
) -> DevEnvironmentCommand | None:
    for command in effective_config.dev_environment_commands:
        if command.name == command_name:
            return command
    return None


def _resolve_command_cwd(
    workspace: Path,
    command: DevEnvironmentCommand,
) -> Path:
    raw_cwd = Path(command.working_directory)
    if raw_cwd.is_absolute():
        raise _CommandCwdDeniedError("working_directory must be relative")
    resolved = (workspace / raw_cwd).resolve(strict=False)
    if not _is_within_workspace(resolved, workspace):
        raise _CommandCwdDeniedError("working_directory escapes the workspace")
    return resolved


def _is_within_workspace(path: Path, workspace: Path) -> bool:
    return path == workspace or workspace in path.parents


def _status_for_execution(execution: CommandExecutionResult) -> str:
    if execution.timed_out:
        return "timed_out"
    if execution.exit_code == 0:
        return "succeeded"
    return "failed"


def _append_audit_event(sink: AuditEventSink, event: AuditEvent) -> None:
    try:
        sink.append(event)
    except Exception as exc:
        raise DevEnvironmentAuditWriteError(
            event_type=event.event_type,
            audit_destination=sink.describe_destination(),
            reason=str(exc),
        ) from exc


def _base_metadata(
    request: RunDevEnvironmentCommandRequest,
    *,
    workspace: Path,
) -> dict[str, str]:
    return {
        "command_name": request.command_name,
        "workspace_path": str(workspace),
        "team": request.team_name or "",
        "team_source": request.team_source,
        "provider_id": request.provider_id or "",
        "provider_source": request.provider_source,
    }


def _denied_event(
    request: RunDevEnvironmentCommandRequest,
    *,
    workspace: Path,
    reason: str,
) -> AuditEvent:
    metadata = _base_metadata(request, workspace=workspace)
    metadata["failure_reason"] = reason
    return AuditEvent(
        event_type="dev_environment.command.denied",
        message=f"Dev environment command '{request.command_name}' was denied.",
        severity=SeverityLevel.ERROR,
        subject=request.command_name,
        metadata=metadata,
    )


def _started_event(
    request: RunDevEnvironmentCommandRequest,
    *,
    workspace: Path,
    command: DevEnvironmentCommand,
    cwd: Path,
) -> AuditEvent:
    metadata = _base_metadata(request, workspace=workspace)
    metadata.update(
        {
            "cwd": str(cwd),
            "timeout_seconds": str(command.timeout_seconds),
        }
    )
    return AuditEvent(
        event_type="dev_environment.command.started",
        message=f"Dev environment command '{command.name}' started.",
        severity=SeverityLevel.INFO,
        subject=command.name,
        metadata=metadata,
    )


def _result_event(
    request: RunDevEnvironmentCommandRequest,
    *,
    workspace: Path,
    command: DevEnvironmentCommand,
    cwd: Path,
    execution: CommandExecutionResult,
    status: str,
) -> AuditEvent:
    metadata = _base_metadata(request, workspace=workspace)
    metadata.update(
        {
            "cwd": str(cwd),
            "status": status,
            "exit_code": "" if execution.exit_code is None else str(execution.exit_code),
            "timed_out": str(execution.timed_out).lower(),
            "duration_ms": str(execution.duration_ms),
            "stdout_total_bytes": str(execution.stdout.total_bytes),
            "stderr_total_bytes": str(execution.stderr.total_bytes),
            "stdout_truncated": str(execution.stdout.truncated).lower(),
            "stderr_truncated": str(execution.stderr.truncated).lower(),
        }
    )
    severity = SeverityLevel.INFO if status == "succeeded" else SeverityLevel.ERROR
    return AuditEvent(
        event_type=f"dev_environment.command.{status}",
        message=f"Dev environment command '{command.name}' {status.replace('_', ' ')}.",
        severity=severity,
        subject=command.name,
        metadata=metadata,
    )
