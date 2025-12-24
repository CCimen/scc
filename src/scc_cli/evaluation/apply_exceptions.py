"""Apply exceptions to evaluation results.

Contain the core exception application logic. All functions are pure (no IO)
and operate on immutable data structures.

Key rules:
- apply_policy_exceptions() can override ANY block (security or delegation)
- apply_local_overrides() can ONLY override DELEGATION blocks
- Expired exceptions have no effect
- Wildcard patterns (e.g., "jira-*") are supported
"""

from __future__ import annotations

import fnmatch
from datetime import datetime, timezone
from typing import Literal

from scc_cli.evaluation.models import (
    Decision,
    EvaluationResult,
)
from scc_cli.models.exceptions import AllowTargets, BlockReason
from scc_cli.models.exceptions import Exception as SccException
from scc_cli.utils.ttl import format_relative


def _is_expired(exception: SccException) -> bool:
    """Check if an exception has expired."""
    try:
        expires = datetime.fromisoformat(exception.expires_at.replace("Z", "+00:00"))
        return expires <= datetime.now(timezone.utc)
    except (ValueError, AttributeError):
        return True  # Invalid expiration = expired


def _matches_target(pattern: str, target: str) -> bool:
    """Check if a pattern matches a target, supporting wildcards."""
    # Exact match first
    if pattern == target:
        return True
    # Wildcard match (fnmatch supports * and ?)
    return fnmatch.fnmatch(target, pattern)


def _get_allowed_targets(
    allow: AllowTargets, target_type: Literal["plugin", "mcp_server", "base_image"]
) -> list[str]:
    """Get the list of allowed targets for a specific type."""
    if target_type == "plugin":
        return allow.plugins or []
    elif target_type == "mcp_server":
        return allow.mcp_servers or []
    elif target_type == "base_image":
        return allow.base_images or []
    return []


def _find_matching_exception(
    target: str,
    target_type: Literal["plugin", "mcp_server", "base_image"],
    exceptions: list[SccException],
) -> SccException | None:
    """Find the first non-expired exception that matches the target.

    Prefers exact matches over wildcard matches.
    """
    exact_match = None
    wildcard_match = None

    for exc in exceptions:
        if _is_expired(exc):
            continue

        allowed = _get_allowed_targets(exc.allow, target_type)
        for pattern in allowed:
            if pattern == target:
                exact_match = exc
                break  # Exact match found, use it
            elif _matches_target(pattern, target) and wildcard_match is None:
                wildcard_match = exc

        if exact_match:
            break

    return exact_match or wildcard_match


def _calculate_expires_in(exception: SccException) -> str | None:
    """Calculate the relative time until expiration."""
    try:
        expires = datetime.fromisoformat(exception.expires_at.replace("Z", "+00:00"))
        return format_relative(expires)
    except (ValueError, AttributeError):
        return None


def apply_policy_exceptions(
    result: EvaluationResult,
    exceptions: list[SccException],
) -> EvaluationResult:
    """Apply policy exceptions to an evaluation result.

    Policy exceptions can override ANY block - both security blocks and
    delegation denials. This is the first layer of exception application.

    Args:
        result: The current evaluation result
        exceptions: List of policy exceptions to apply

    Returns:
        New EvaluationResult with matching items removed and decisions added
    """
    new_result = result.copy()

    # Process blocked items (security blocks)
    remaining_blocked = []
    for blocked in result.blocked_items:
        matching_exc = _find_matching_exception(blocked.target, blocked.target_type, exceptions)
        if matching_exc:
            # Create decision record
            decision = Decision(
                item=blocked.target,
                item_type=blocked.target_type,
                result="allowed",
                reason="Policy exception applied",
                source="policy",
                exception_id=matching_exc.id,
                expires_in=_calculate_expires_in(matching_exc),
            )
            new_result.decisions.append(decision)
        else:
            remaining_blocked.append(blocked)

    new_result.blocked_items = remaining_blocked

    # Process denied additions (delegation blocks)
    remaining_denied = []
    for denied in result.denied_additions:
        matching_exc = _find_matching_exception(denied.target, denied.target_type, exceptions)
        if matching_exc:
            decision = Decision(
                item=denied.target,
                item_type=denied.target_type,
                result="allowed",
                reason="Policy exception applied",
                source="policy",
                exception_id=matching_exc.id,
                expires_in=_calculate_expires_in(matching_exc),
            )
            new_result.decisions.append(decision)
        else:
            remaining_denied.append(denied)

    new_result.denied_additions = remaining_denied

    return new_result


def apply_local_overrides(
    result: EvaluationResult,
    overrides: list[SccException],
    source: Literal["repo", "user"],
) -> EvaluationResult:
    """Apply local overrides to an evaluation result.

    Local overrides can ONLY override DELEGATION blocks (denied additions).
    Security blocks are immutable to local overrides - this is a critical
    security boundary.

    Args:
        result: The current evaluation result
        overrides: List of local overrides to apply
        source: Where the overrides came from ("repo" or "user")

    Returns:
        New EvaluationResult with matching denied additions removed and decisions added
    """
    new_result = result.copy()

    # ONLY process denied additions (delegation blocks)
    # Security blocks (blocked_items) are NEVER affected by local overrides
    remaining_denied = []
    for denied in result.denied_additions:
        # Only delegation blocks can be overridden locally
        if denied.reason != BlockReason.DELEGATION:
            remaining_denied.append(denied)
            continue

        matching_exc = _find_matching_exception(denied.target, denied.target_type, overrides)
        if matching_exc:
            decision = Decision(
                item=denied.target,
                item_type=denied.target_type,
                result="allowed",
                reason="Local override applied",
                source=source,
                exception_id=matching_exc.id,
                expires_in=_calculate_expires_in(matching_exc),
            )
            new_result.decisions.append(decision)
        else:
            remaining_denied.append(denied)

    new_result.denied_additions = remaining_denied

    return new_result
