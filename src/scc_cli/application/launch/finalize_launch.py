"""Finalize launch use case for start flows."""

from __future__ import annotations

from scc_cli.application.launch.preflight import (
    build_launch_started_event,
    build_preflight_failure_event,
    evaluate_launch_preflight,
)
from scc_cli.application.start_session import (
    StartSessionDependencies,
    StartSessionPlan,
    start_session,
)
from scc_cli.core.contracts import AuditEvent
from scc_cli.core.errors import (
    LaunchAuditUnavailableError,
    LaunchAuditWriteError,
    LaunchPreflightError,
)
from scc_cli.ports.audit_event_sink import AuditEventSink
from scc_cli.ports.models import SandboxHandle

FinalizeLaunchDependencies = StartSessionDependencies
FinalizeLaunchPlan = StartSessionPlan
FinalizeLaunchResult = SandboxHandle


def finalize_launch(
    plan: FinalizeLaunchPlan,
    *,
    dependencies: FinalizeLaunchDependencies,
) -> FinalizeLaunchResult:
    """Finalize a prepared launch plan by validating then starting the sandbox."""
    if _uses_preflight_seam(plan, dependencies):
        sink = dependencies.audit_event_sink
        if sink is None:
            raise LaunchAuditUnavailableError()
        try:
            decision = evaluate_launch_preflight(plan)
        except LaunchPreflightError as error:
            _append_audit_event(sink, build_preflight_failure_event(plan, error))
            raise
        _append_audit_event(sink, decision.audit_event)
        handle = start_session(plan, dependencies=dependencies)
        _append_audit_event(sink, build_launch_started_event(plan, decision, handle))
        return handle
    return start_session(plan, dependencies=dependencies)


def _uses_preflight_seam(
    plan: FinalizeLaunchPlan,
    dependencies: FinalizeLaunchDependencies,
) -> bool:
    return plan.agent_launch_spec is not None or dependencies.audit_event_sink is not None


def _append_audit_event(sink: AuditEventSink, event: AuditEvent) -> None:
    try:
        sink.append(event)
    except Exception as exc:  # pragma: no cover - defensive wrapper over sink adapters
        raise LaunchAuditWriteError(
            audit_destination=sink.describe_destination(),
            event_type=event.event_type,
            reason=str(exc),
        ) from exc
