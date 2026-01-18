"""Prepare launch plan use case for start flows."""

from __future__ import annotations

from scc_cli.application.start_session import (
    StartSessionDependencies,
    StartSessionPlan,
    StartSessionRequest,
    prepare_start_session,
)

PrepareLaunchPlanDependencies = StartSessionDependencies
PrepareLaunchPlanRequest = StartSessionRequest
PrepareLaunchPlanResult = StartSessionPlan


def prepare_launch_plan(
    request: PrepareLaunchPlanRequest,
    *,
    dependencies: PrepareLaunchPlanDependencies,
) -> PrepareLaunchPlanResult:
    """Prepare the launch plan for a start session.

    Invariants:
        - Delegates to the existing start session preparation to preserve behavior.
        - Maintains deterministic output for the same request inputs.

    Args:
        request: Input data needed to compute launch settings and sandbox specs.
        dependencies: Ports and collaborators required to build the plan.

    Returns:
        Prepared launch plan describing the computed settings and sandbox spec.

    Raises:
        SCCError: Propagated from underlying plan preparation when a failure occurs.
        ValueError: Propagated if the request is invalid for plan construction.
    """
    return prepare_start_session(request, dependencies=dependencies)
