"""JSON mapping helpers for dev-environment bridge command output."""

from __future__ import annotations

from typing import Any

from scc_cli.application.dev_environment_bridge import (
    CapturedStream,
    RunDevEnvironmentCommandResult,
)
from scc_cli.json_output import build_envelope
from scc_cli.kinds import Kind


def build_dev_environment_command_data(
    result: RunDevEnvironmentCommandResult,
) -> dict[str, Any]:
    """Build JSON-ready data for one dev-environment command result."""
    return {
        "command_name": result.command_name,
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
    return build_envelope(Kind.DEV_ENVIRONMENT_COMMAND, data=data, ok=ok, errors=errors)


def _stream_to_dict(stream: CapturedStream) -> dict[str, Any]:
    return {
        "tail": stream.tail,
        "total_bytes": stream.total_bytes,
        "truncated": stream.truncated,
    }
