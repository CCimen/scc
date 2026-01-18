"""Finalize launch use case for start flows."""

from __future__ import annotations

from scc_cli.application.start_session import (
    StartSessionDependencies,
    StartSessionPlan,
    start_session,
)
from scc_cli.ports.models import SandboxHandle

FinalizeLaunchDependencies = StartSessionDependencies
FinalizeLaunchPlan = StartSessionPlan
FinalizeLaunchResult = SandboxHandle


def finalize_launch(
    plan: FinalizeLaunchPlan,
    *,
    dependencies: FinalizeLaunchDependencies,
) -> FinalizeLaunchResult:
    """Finalize a prepared launch plan by starting the sandbox runtime.

    Invariants:
        - Delegates to the existing start session execution to preserve behavior.
        - Does not perform any CLI output or prompting.

    Args:
        plan: Prepared launch plan ready to execute.
        dependencies: Ports and collaborators required to run the sandbox.

    Returns:
        SandboxHandle for the launched session.

    Raises:
        SCCError: Propagated from sandbox runtime execution failures.
        ValueError: Raised if the plan is missing a sandbox specification.
    """
    return start_session(plan, dependencies=dependencies)
