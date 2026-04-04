"""Provider-neutral launch preflight validation and audit-event builders."""

from __future__ import annotations

from dataclasses import dataclass

from scc_cli.application.start_session import StartSessionPlan
from scc_cli.core.contracts import AgentLaunchSpec, AuditEvent
from scc_cli.core.enums import NetworkPolicy, SeverityLevel
from scc_cli.core.errors import (
    InvalidLaunchPlanError,
    LaunchPolicyBlockedError,
    LaunchPreflightError,
)
from scc_cli.ports.models import SandboxHandle


@dataclass(frozen=True)
class LaunchPreflightDecision:
    """Validated launch metadata used by the launch boundary."""

    provider_id: str
    network_policy: str
    required_destination_sets: tuple[str, ...]
    audit_event: AuditEvent


def evaluate_launch_preflight(plan: StartSessionPlan) -> LaunchPreflightDecision:
    """Validate that the prepared launch plan can start under the current policy."""
    spec = _validated_launch_spec(plan)
    provider_id = _validated_provider_id(spec.provider_id)
    required_destination_sets = _validated_required_destination_sets(spec.required_destination_sets)
    network_policy = _effective_network_policy(plan)

    if (
        network_policy == NetworkPolicy.LOCKED_DOWN_WEB.value
        and len(required_destination_sets) > 0
    ):
        raise LaunchPolicyBlockedError(
            provider_id=provider_id,
            network_policy=network_policy,
            required_destination_sets=required_destination_sets,
        )

    return LaunchPreflightDecision(
        provider_id=provider_id,
        network_policy=network_policy,
        required_destination_sets=required_destination_sets,
        audit_event=AuditEvent(
            event_type="launch.preflight.passed",
            message=f"Launch preflight passed for provider '{provider_id}'.",
            severity=SeverityLevel.INFO,
            subject=provider_id,
            metadata=_event_metadata(
                plan,
                provider_id=provider_id,
                network_policy=network_policy,
                required_destination_sets=required_destination_sets,
            ),
        ),
    )


def build_preflight_failure_event(
    plan: StartSessionPlan,
    error: LaunchPreflightError,
) -> AuditEvent:
    """Build the canonical audit event for a failed launch preflight."""
    provider_id = _safe_provider_id(plan)
    required_destination_sets = _safe_required_destination_sets(plan)
    network_policy = _effective_network_policy(plan)
    metadata = _event_metadata(
        plan,
        provider_id=provider_id,
        network_policy=network_policy,
        required_destination_sets=required_destination_sets,
    )
    metadata["failure_reason"] = error.user_message
    return AuditEvent(
        event_type="launch.preflight.failed",
        message=(
            f"Launch preflight failed for provider '{provider_id or 'unknown'}'."
        ),
        severity=SeverityLevel.ERROR,
        subject=provider_id or None,
        metadata=metadata,
    )


def build_launch_started_event(
    plan: StartSessionPlan,
    decision: LaunchPreflightDecision,
    handle: SandboxHandle,
) -> AuditEvent:
    """Build the canonical audit event for a successful runtime handoff."""
    metadata = _event_metadata(
        plan,
        provider_id=decision.provider_id,
        network_policy=decision.network_policy,
        required_destination_sets=decision.required_destination_sets,
    )
    metadata["sandbox_id"] = handle.sandbox_id
    if handle.name:
        metadata["sandbox_name"] = handle.name
    return AuditEvent(
        event_type="launch.started",
        message=f"Launch started for provider '{decision.provider_id}'.",
        severity=SeverityLevel.INFO,
        subject=decision.provider_id,
        metadata=metadata,
    )


def _validated_launch_spec(plan: StartSessionPlan) -> AgentLaunchSpec:
    spec = plan.agent_launch_spec
    if spec is None:
        raise InvalidLaunchPlanError(
            reason="Launch plan is missing provider launch metadata.",
        )
    return spec


def _validated_provider_id(provider_id: str) -> str:
    normalized = provider_id.strip()
    if normalized == "":
        raise InvalidLaunchPlanError(
            reason="Launch plan is missing provider identity.",
        )
    return normalized


def _validated_required_destination_sets(required_destination_sets: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for destination_set in required_destination_sets:
        cleaned = destination_set.strip()
        if cleaned == "":
            raise InvalidLaunchPlanError(
                reason="Launch plan contains a blank required destination set name.",
            )
        normalized.append(cleaned)
    return tuple(normalized)


def _effective_network_policy(plan: StartSessionPlan) -> str:
    sandbox_spec = plan.sandbox_spec
    if sandbox_spec is None or sandbox_spec.network_policy is None:
        return NetworkPolicy.OPEN.value
    return sandbox_spec.network_policy


def _safe_provider_id(plan: StartSessionPlan) -> str:
    spec = plan.agent_launch_spec
    if spec is None:
        return ""
    return spec.provider_id.strip()


def _safe_required_destination_sets(plan: StartSessionPlan) -> tuple[str, ...]:
    spec = plan.agent_launch_spec
    if spec is None:
        return ()
    return tuple(destination_set.strip() for destination_set in spec.required_destination_sets)


def _event_metadata(
    plan: StartSessionPlan,
    *,
    provider_id: str,
    network_policy: str,
    required_destination_sets: tuple[str, ...],
) -> dict[str, str]:
    return {
        "provider_id": provider_id,
        "network_policy": network_policy,
        "required_destination_sets": ",".join(required_destination_sets),
        "workspace_path": str(plan.workspace_path),
        "session_name": plan.session_name or "",
        "team": plan.team or "",
    }
