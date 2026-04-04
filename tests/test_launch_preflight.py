from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scc_cli.application.launch.finalize_launch import finalize_launch
from scc_cli.application.launch.preflight import evaluate_launch_preflight
from scc_cli.application.start_session import StartSessionDependencies, StartSessionPlan
from scc_cli.core.contracts import AgentLaunchSpec, AuditEvent
from scc_cli.core.errors import (
    InvalidLaunchPlanError,
    LaunchAuditUnavailableError,
    LaunchAuditWriteError,
    LaunchPolicyBlockedError,
)
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.models import MountSpec, SandboxHandle, SandboxSpec
from tests.fakes.fake_agent_provider import FakeAgentProvider
from tests.fakes.fake_agent_runner import FakeAgentRunner
from tests.test_application_start_session import FakeGitClient


@dataclass
class RecordingAuditSink:
    events: list[AuditEvent] = field(default_factory=list)

    def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    def describe_destination(self) -> str:
        return "memory://audit"


class FailingAuditSink:
    def append(self, event: AuditEvent) -> None:
        raise OSError("disk full")

    def describe_destination(self) -> str:
        return "/tmp/launch-events.jsonl"


class RecordingSandboxRuntime:
    def __init__(self) -> None:
        self.calls = 0

    def ensure_available(self) -> None:
        return None

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        self.calls += 1
        return SandboxHandle(sandbox_id=f"sandbox-{self.calls}", name="sandbox-name")

    def resume(self, handle: SandboxHandle) -> None:
        return None

    def stop(self, handle: SandboxHandle) -> None:
        return None

    def remove(self, handle: SandboxHandle) -> None:
        return None

    def list_running(self) -> list[SandboxHandle]:
        return []

    def status(self, handle: SandboxHandle):  # pragma: no cover - not used here
        raise NotImplementedError


def _build_plan(
    tmp_path: Path,
    *,
    network_policy: str | None = "open",
    provider_id: str = "claude",
    required_destination_sets: tuple[str, ...] = ("anthropic-core",),
    include_agent_launch_spec: bool = True,
) -> StartSessionPlan:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    resolver_result = ResolverResult(
        workspace_root=workspace_path,
        entry_dir=workspace_path,
        mount_root=workspace_path,
        container_workdir=str(workspace_path),
        is_auto_detected=False,
        is_suspicious=False,
        reason="test",
    )
    sandbox_spec = SandboxSpec(
        image="test-image",
        workspace_mount=MountSpec(source=workspace_path, target=workspace_path),
        workdir=workspace_path,
        network_policy=network_policy,
    )
    agent_launch_spec = None
    if include_agent_launch_spec:
        agent_launch_spec = AgentLaunchSpec(
            provider_id=provider_id,
            argv=("claude",),
            workdir=workspace_path,
            required_destination_sets=required_destination_sets,
        )
    return StartSessionPlan(
        resolver_result=resolver_result,
        workspace_path=workspace_path,
        team=None,
        session_name="session-1",
        resume=False,
        fresh=False,
        current_branch=None,
        effective_config=None,
        sync_result=None,
        sync_error_message=None,
        agent_settings=None,
        sandbox_spec=sandbox_spec,
        agent_launch_spec=agent_launch_spec,
    )


def _build_dependencies(
    *,
    sandbox_runtime: RecordingSandboxRuntime | None = None,
    audit_event_sink: RecordingAuditSink | FailingAuditSink | None = None,
) -> StartSessionDependencies:
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=FakeGitClient(),
        agent_runner=FakeAgentRunner(),
        sandbox_runtime=sandbox_runtime or RecordingSandboxRuntime(),
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
        agent_provider=FakeAgentProvider(),
        audit_event_sink=audit_event_sink,
    )


def test_evaluate_launch_preflight_rejects_missing_agent_launch_spec(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, include_agent_launch_spec=False)

    with pytest.raises(InvalidLaunchPlanError, match="missing provider launch metadata"):
        evaluate_launch_preflight(plan)


def test_evaluate_launch_preflight_rejects_blank_provider_identity(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, provider_id="   ")

    with pytest.raises(InvalidLaunchPlanError, match="missing provider identity"):
        evaluate_launch_preflight(plan)


def test_evaluate_launch_preflight_rejects_blank_required_destination_name(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, required_destination_sets=("anthropic-core", "   "))

    with pytest.raises(InvalidLaunchPlanError, match="blank required destination set"):
        evaluate_launch_preflight(plan)


def test_finalize_launch_emits_preflight_and_launch_started_events_for_allowed_launch(
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path, network_policy="open")
    runtime = RecordingSandboxRuntime()
    sink = RecordingAuditSink()
    dependencies = _build_dependencies(sandbox_runtime=runtime, audit_event_sink=sink)

    handle = finalize_launch(plan, dependencies=dependencies)

    assert handle.sandbox_id == "sandbox-1"
    assert runtime.calls == 1
    assert [event.event_type for event in sink.events] == [
        "launch.preflight.passed",
        "launch.started",
    ]
    assert sink.events[0].metadata["provider_id"] == "claude"
    assert sink.events[0].metadata["required_destination_sets"] == "anthropic-core"
    assert sink.events[1].metadata["sandbox_id"] == "sandbox-1"


def test_finalize_launch_blocks_locked_down_provider_launch_before_runtime_start(
    tmp_path: Path,
) -> None:
    plan = _build_plan(tmp_path, network_policy="locked-down-web")
    runtime = RecordingSandboxRuntime()
    sink = RecordingAuditSink()
    dependencies = _build_dependencies(sandbox_runtime=runtime, audit_event_sink=sink)

    with pytest.raises(LaunchPolicyBlockedError, match="locked-down-web"):
        finalize_launch(plan, dependencies=dependencies)

    assert runtime.calls == 0
    assert [event.event_type for event in sink.events] == ["launch.preflight.failed"]
    assert sink.events[0].metadata["failure_reason"].startswith("Launch blocked before startup")


def test_finalize_launch_allows_standalone_launch_without_required_destination_sets(
    tmp_path: Path,
) -> None:
    plan = _build_plan(
        tmp_path,
        network_policy=None,
        provider_id="codex",
        required_destination_sets=(),
    )
    sink = RecordingAuditSink()
    dependencies = _build_dependencies(audit_event_sink=sink)

    handle = finalize_launch(plan, dependencies=dependencies)

    assert handle.sandbox_id == "sandbox-1"
    assert sink.events[0].metadata["network_policy"] == "open"
    assert sink.events[0].metadata["required_destination_sets"] == ""
    assert sink.events[0].subject == "codex"


def test_finalize_launch_fails_closed_when_audit_write_fails(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, network_policy="open")
    runtime = RecordingSandboxRuntime()
    dependencies = _build_dependencies(
        sandbox_runtime=runtime,
        audit_event_sink=FailingAuditSink(),
    )

    with pytest.raises(LaunchAuditWriteError, match="launch-events.jsonl"):
        finalize_launch(plan, dependencies=dependencies)

    assert runtime.calls == 0


def test_finalize_launch_requires_audit_sink_once_preflight_seam_is_in_use(tmp_path: Path) -> None:
    plan = _build_plan(tmp_path, network_policy="open")
    dependencies = _build_dependencies(audit_event_sink=None)

    with pytest.raises(LaunchAuditUnavailableError):
        finalize_launch(plan, dependencies=dependencies)
