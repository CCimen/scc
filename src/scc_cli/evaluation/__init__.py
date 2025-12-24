"""Evaluation layer for SCC exception system.

Provide pure functions for evaluating configs and applying exceptions.
All IO is isolated to the stores layer.
"""

from scc_cli.evaluation.apply_exceptions import (
    apply_local_overrides,
    apply_policy_exceptions,
)
from scc_cli.evaluation.evaluate import evaluate
from scc_cli.evaluation.models import (
    BlockedItem,
    Decision,
    DeniedAddition,
    EvaluationResult,
)

__all__ = [
    "BlockedItem",
    "Decision",
    "DeniedAddition",
    "EvaluationResult",
    "apply_local_overrides",
    "apply_policy_exceptions",
    "evaluate",
]
