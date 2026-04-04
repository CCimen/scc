"""Stripped-down contracts for the standalone safety evaluator.

Contains only SafetyPolicy and SafetyVerdict — the minimal surface
needed for runtime safety evaluation without any host CLI dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SafetyPolicy:
    """Normalized safety policy available to runtime and adapter layers.

    Attributes:
        action: Baseline action when a guarded command is matched.
        rules: Boolean or scalar rule settings keyed by stable rule name.
        source: Where the policy originated, such as org.security.safety_net.
    """

    action: str = "block"
    rules: dict[str, Any] = field(default_factory=dict)
    source: str = "org.security.safety_net"


@dataclass(frozen=True)
class SafetyVerdict:
    """Decision produced by safety evaluation for one attempted action.

    Attributes:
        allowed: Whether the action is permitted.
        reason: User-facing reason for the decision.
        matched_rule: Stable rule identifier, if any.
        command_family: High-level command family, if known.
    """

    allowed: bool
    reason: str
    matched_rule: str | None = None
    command_family: str | None = None
