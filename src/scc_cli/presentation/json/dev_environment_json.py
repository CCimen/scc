"""JSON mapping helpers for dev-environment bridge command output."""

from __future__ import annotations

from typing import Any

from scc_cli.application.dev_environment_bridge import (
    DEV_ENVIRONMENT_HEALTH_CHECK_ACTION,
    DEV_ENVIRONMENT_LOG_ACTION,
    CapturedStream,
    DevEnvironmentActionKind,
    RunDevEnvironmentCommandResult,
)
from scc_cli.application.effective_config_models import DevEnvironmentCommand, EffectiveConfig
from scc_cli.json_output import build_envelope
from scc_cli.kinds import Kind


def build_dev_environment_command_data(
    result: RunDevEnvironmentCommandResult,
) -> dict[str, Any]:
    """Build JSON-ready data for one dev-environment command result."""
    return {
        "command_name": result.command_name,
        "action_type": result.action_type.value,
        "status": result.status,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
        "duration_ms": result.duration_ms,
        "argv": list(result.argv),
        "cwd": str(result.cwd),
        "team": {
            "name": result.team_name,
            "source": result.team_source,
        },
        "provider": {
            "id": result.provider_id,
            "source": result.provider_source,
        },
        "stdout": _stream_to_dict(result.stdout),
        "stderr": _stream_to_dict(result.stderr),
    }


def build_dev_environment_command_envelope(
    result: RunDevEnvironmentCommandResult,
) -> dict[str, Any]:
    """Build the JSON envelope for one dev-environment command result."""
    data = build_dev_environment_command_data(result)
    ok = result.status == "succeeded"
    errors = [] if ok else [f"Command {result.status.replace('_', ' ')}"]
    return build_envelope(
        _kind_for_action_type(result.action_type),
        data=data,
        ok=ok,
        errors=errors,
    )


def build_dev_environment_status_data(
    *,
    effective: EffectiveConfig,
    workspace_path: str,
    team_name: str | None,
    team_source: str,
    provider_id: str | None,
    provider_source: str,
) -> dict[str, Any]:
    """Build JSON-ready data for effective dev-environment bridge status."""
    return {
        "workspace_path": workspace_path,
        "team": {"name": team_name, "source": team_source},
        "provider": {"id": provider_id, "source": provider_source},
        "commands": [_action_to_dict(action) for action in effective.dev_environment_commands],
        "logs": [_action_to_dict(action) for action in effective.dev_environment_logs],
        "health_checks": [
            _action_to_dict(action) for action in effective.dev_environment_health_checks
        ],
    }


def build_dev_environment_status_envelope(data: dict[str, Any]) -> dict[str, Any]:
    """Build JSON envelope for effective dev-environment bridge status."""
    return build_envelope(Kind.DEV_ENVIRONMENT_STATUS, data=data, ok=True)


def _stream_to_dict(stream: CapturedStream) -> dict[str, Any]:
    return {
        "tail": stream.tail,
        "total_bytes": stream.total_bytes,
        "truncated": stream.truncated,
    }


def _action_to_dict(action: DevEnvironmentCommand) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": action.name,
        "argv": list(action.argv),
        "working_directory": action.working_directory,
        "timeout_seconds": action.timeout_seconds,
    }
    if action.description:
        payload["description"] = action.description
    return payload


def _kind_for_action_type(action_type: DevEnvironmentActionKind) -> Kind:
    if action_type == DEV_ENVIRONMENT_LOG_ACTION:
        return Kind.DEV_ENVIRONMENT_LOG
    if action_type == DEV_ENVIRONMENT_HEALTH_CHECK_ACTION:
        return Kind.DEV_ENVIRONMENT_HEALTH_CHECK
    if action_type == DevEnvironmentActionKind.COMMAND:
        return Kind.DEV_ENVIRONMENT_COMMAND
    raise AssertionError(f"Unhandled dev environment action kind: {action_type}")
