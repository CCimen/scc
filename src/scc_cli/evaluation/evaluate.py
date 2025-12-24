"""Bridge function to convert EffectiveConfig to EvaluationResult.

Provide the evaluate() function that converts the governance layer models
(profiles.py) to the exception system models (evaluation/models.py) with
proper BlockReason annotations.

This is a pure function with no IO - all input comes from the EffectiveConfig
parameter and output is a new EvaluationResult.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from scc_cli.evaluation.models import (
    BlockedItem,
    DeniedAddition,
    EvaluationResult,
)
from scc_cli.models.exceptions import BlockReason

if TYPE_CHECKING:
    from scc_cli.profiles import EffectiveConfig


def evaluate(config: EffectiveConfig) -> EvaluationResult:
    """Convert EffectiveConfig to EvaluationResult with BlockReason annotations.

    This function bridges the governance layer (profiles.py models) to the
    exception system (evaluation/models.py) by converting:

    - profiles.BlockedItem -> evaluation.BlockedItem with BlockReason.SECURITY
    - profiles.DelegationDenied -> evaluation.DeniedAddition with BlockReason.DELEGATION

    Args:
        config: The EffectiveConfig from the profile merge process

    Returns:
        EvaluationResult with properly annotated blocked items and denied additions
    """
    blocked_items: list[BlockedItem] = []
    denied_additions: list[DeniedAddition] = []

    # Convert blocked items (security blocks)
    for blocked in config.blocked_items:
        target_type = _normalize_target_type(blocked.target_type)
        message = f"Blocked by security pattern '{blocked.blocked_by}'"

        blocked_items.append(
            BlockedItem(
                target=blocked.item,
                target_type=target_type,
                reason=BlockReason.SECURITY,
                message=message,
            )
        )

    # Convert denied additions (delegation denials)
    for denied in config.denied_additions:
        target_type = _normalize_target_type(denied.target_type)
        # Use the original reason which contains useful context
        message = denied.reason

        denied_additions.append(
            DeniedAddition(
                target=denied.item,
                target_type=target_type,
                reason=BlockReason.DELEGATION,
                message=message,
            )
        )

    return EvaluationResult(
        blocked_items=blocked_items,
        denied_additions=denied_additions,
        decisions=[],  # Decisions are populated by apply_*_exceptions functions
        warnings=[],
    )


def _normalize_target_type(
    target_type: str,
) -> Literal["plugin", "mcp_server", "base_image"]:
    """Normalize target_type to valid literal values.

    Args:
        target_type: The target type from profiles.py models

    Returns:
        Normalized target type literal
    """
    if target_type == "mcp_server":
        return "mcp_server"
    elif target_type == "base_image":
        return "base_image"
    else:
        return "plugin"  # Default to plugin for unknown types
