from __future__ import annotations

import sys
from pathlib import Path

import pytest

from scc_cli.application.dev_environment_bridge import (
    CapturedStream,
    CommandExecutionResult,
    CommandExecutionSpec,
    RunDevEnvironmentCommandDependencies,
    RunDevEnvironmentCommandRequest,
    run_dev_environment_command,
)
from scc_cli.application.effective_config_models import DevEnvironmentCommand, EffectiveConfig
from scc_cli.core.errors import DevEnvironmentAuditWriteError, DevEnvironmentCommandDeniedError
from scc_cli.services.dev_environment_command_runner import run_subprocess_bounded
from tests.fakes import FakeAuditEventSink


def _effective(*commands: DevEnvironmentCommand) -> EffectiveConfig:
    return EffectiveConfig(dev_environment_commands=list(commands))


def _request(
    workspace: Path,
    *,
    command_name: str = "test",
    command: DevEnvironmentCommand | None = None,
) -> RunDevEnvironmentCommandRequest:
    commands = [command] if command else []
    return RunDevEnvironmentCommandRequest(
        command_name=command_name,
        workspace_path=workspace,
        effective_config=_effective(*commands),
        team_name="platform",
        team_source="selected_profile",
        provider_id="codex",
        provider_source="workspace",
    )


def _success_result() -> CommandExecutionResult:
    return CommandExecutionResult(
        exit_code=0,
        timed_out=False,
        stdout=CapturedStream(tail="ok\n", total_bytes=3, truncated=False),
        stderr=CapturedStream(tail="", total_bytes=0, truncated=False),
        duration_ms=7,
    )


def test_runs_configured_command_and_audits_without_output_payload(tmp_path: Path) -> None:
    sink = FakeAuditEventSink()
    seen_specs: list[CommandExecutionSpec] = []

    def runner(spec: CommandExecutionSpec) -> CommandExecutionResult:
        seen_specs.append(spec)
        return _success_result()

    command = DevEnvironmentCommand(
        name="test",
        argv=("uv", "run", "pytest", "-q"),
        working_directory=".",
        timeout_seconds=120,
    )

    result = run_dev_environment_command(
        _request(tmp_path, command=command),
        dependencies=RunDevEnvironmentCommandDependencies(
            audit_sink=sink,
            command_runner=runner,
        ),
    )

    assert result.status == "succeeded"
    assert result.stdout.tail == "ok\n"
    assert seen_specs == [
        CommandExecutionSpec(
            argv=("uv", "run", "pytest", "-q"),
            cwd=tmp_path.resolve(strict=False),
            timeout_seconds=120,
        )
    ]
    assert [event.event_type for event in sink.events] == [
        "dev_environment.command.started",
        "dev_environment.command.succeeded",
    ]
    result_metadata = sink.events[1].metadata
    assert result_metadata["stdout_total_bytes"] == "3"
    assert "stdout" not in result_metadata
    assert "ok" not in str(result_metadata)


def test_unknown_command_is_denied_and_audited(tmp_path: Path) -> None:
    sink = FakeAuditEventSink()

    with pytest.raises(DevEnvironmentCommandDeniedError):
        run_dev_environment_command(
            _request(tmp_path, command_name="missing"),
            dependencies=RunDevEnvironmentCommandDependencies(audit_sink=sink),
        )

    assert [event.event_type for event in sink.events] == ["dev_environment.command.denied"]
    assert sink.events[0].metadata["failure_reason"] == "Command is not configured"


def test_audit_write_failure_prevents_command_execution(tmp_path: Path) -> None:
    class FailingSink:
        def append(self, event: object) -> None:
            raise OSError("readonly")

        def describe_destination(self) -> str:
            return "memory://failing"

    called = False

    def runner(spec: CommandExecutionSpec) -> CommandExecutionResult:
        nonlocal called
        called = True
        return _success_result()

    command = DevEnvironmentCommand(name="test", argv=("echo", "ok"))

    with pytest.raises(DevEnvironmentAuditWriteError):
        run_dev_environment_command(
            _request(tmp_path, command=command),
            dependencies=RunDevEnvironmentCommandDependencies(
                audit_sink=FailingSink(),
                command_runner=runner,
            ),
        )

    assert called is False


def test_symlink_working_directory_escape_is_denied(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    (tmp_path / "escape").symlink_to(outside, target_is_directory=True)
    sink = FakeAuditEventSink()
    command = DevEnvironmentCommand(
        name="test",
        argv=("echo", "ok"),
        working_directory="escape",
    )

    with pytest.raises(DevEnvironmentCommandDeniedError):
        run_dev_environment_command(
            _request(tmp_path, command=command),
            dependencies=RunDevEnvironmentCommandDependencies(audit_sink=sink),
        )

    assert [event.event_type for event in sink.events] == ["dev_environment.command.denied"]
    assert sink.events[0].metadata["failure_reason"] == "working_directory escapes the workspace"


def test_nonzero_command_returns_failed_result_and_audit(tmp_path: Path) -> None:
    sink = FakeAuditEventSink()

    def runner(spec: CommandExecutionSpec) -> CommandExecutionResult:
        return CommandExecutionResult(
            exit_code=2,
            timed_out=False,
            stdout=CapturedStream(tail="", total_bytes=0, truncated=False),
            stderr=CapturedStream(tail="bad\n", total_bytes=4, truncated=False),
            duration_ms=9,
        )

    command = DevEnvironmentCommand(name="test", argv=("false",))
    result = run_dev_environment_command(
        _request(tmp_path, command=command),
        dependencies=RunDevEnvironmentCommandDependencies(
            audit_sink=sink,
            command_runner=runner,
        ),
    )

    assert result.status == "failed"
    assert result.exit_code == 2
    assert [event.event_type for event in sink.events] == [
        "dev_environment.command.started",
        "dev_environment.command.failed",
    ]


def test_timeout_command_returns_timeout_result_and_audit(tmp_path: Path) -> None:
    sink = FakeAuditEventSink()

    def runner(spec: CommandExecutionSpec) -> CommandExecutionResult:
        return CommandExecutionResult(
            exit_code=None,
            timed_out=True,
            stdout=CapturedStream(tail="", total_bytes=0, truncated=False),
            stderr=CapturedStream(tail="", total_bytes=0, truncated=False),
            duration_ms=1000,
        )

    command = DevEnvironmentCommand(name="test", argv=("sleep", "10"), timeout_seconds=1)
    result = run_dev_environment_command(
        _request(tmp_path, command=command),
        dependencies=RunDevEnvironmentCommandDependencies(
            audit_sink=sink,
            command_runner=runner,
        ),
    )

    assert result.status == "timed_out"
    assert result.timed_out is True
    assert [event.event_type for event in sink.events] == [
        "dev_environment.command.started",
        "dev_environment.command.timed_out",
    ]


def test_subprocess_runner_bounds_large_output(tmp_path: Path) -> None:
    result = run_subprocess_bounded(
        CommandExecutionSpec(
            argv=[
                sys.executable,
                "-c",
                "import sys; sys.stdout.write('a' * 10000); sys.stderr.write('b' * 9000)",
            ],
            cwd=tmp_path,
            timeout_seconds=5,
            output_limit_bytes=64,
        )
    )

    assert result.exit_code == 0
    assert result.stdout.total_bytes == 10000
    assert result.stdout.truncated is True
    assert len(result.stdout.tail.encode()) == 64
    assert result.stderr.total_bytes == 9000
    assert result.stderr.truncated is True
    assert len(result.stderr.tail.encode()) == 64


def test_subprocess_runner_kills_timed_out_process(tmp_path: Path) -> None:
    result = run_subprocess_bounded(
        CommandExecutionSpec(
            argv=[sys.executable, "-c", "import time; time.sleep(5)"],
            cwd=tmp_path,
            timeout_seconds=1,
            output_limit_bytes=64,
        )
    )

    assert result.timed_out is True
    assert result.exit_code is None


def test_missing_executable_returns_failed_result_and_result_audit(tmp_path: Path) -> None:
    sink = FakeAuditEventSink()
    command = DevEnvironmentCommand(
        name="test",
        argv=("definitely-not-a-real-scc-test-command",),
        timeout_seconds=5,
    )

    result = run_dev_environment_command(
        _request(tmp_path, command=command),
        dependencies=RunDevEnvironmentCommandDependencies(
            audit_sink=sink,
            command_runner=run_subprocess_bounded,
        ),
    )

    assert result.status == "failed"
    assert result.exit_code is None
    assert "definitely-not-a-real-scc-test-command" in result.stderr.tail
    assert [event.event_type for event in sink.events] == [
        "dev_environment.command.started",
        "dev_environment.command.failed",
    ]
    assert sink.events[1].metadata["stderr_total_bytes"] != "0"
