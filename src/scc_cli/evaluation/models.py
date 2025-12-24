"""Define data models for the evaluation layer.

Represent the results of evaluating configs and applying exceptions.
All models are immutable and support the pure functional evaluation approach.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from scc_cli.models.exceptions import BlockReason


@dataclass(frozen=True)
class BlockedItem:
    """Represents an item blocked by security policy.

    Security blocks can only be overridden by policy exceptions.
    Local overrides have no effect on these.
    """

    target: str  # The blocked item (plugin name, MCP server, image ref)
    target_type: Literal["plugin", "mcp_server", "base_image"]
    reason: BlockReason  # Always SECURITY for blocked items
    message: str  # Human-readable explanation


@dataclass(frozen=True)
class DeniedAddition:
    """Represents an addition denied by delegation policy.

    Delegation denials can be overridden by either policy exceptions
    or local overrides (from repo or user stores).
    """

    target: str  # The denied item
    target_type: Literal["plugin", "mcp_server", "base_image"]
    reason: BlockReason  # Always DELEGATION for denied additions
    message: str  # Human-readable explanation


@dataclass(frozen=True)
class Decision:
    """Records a decision made when applying an exception.

    Captures the full context of why an item was allowed or blocked,
    including the exception that allowed it and when it expires.
    """

    item: str  # The item being decided on
    item_type: Literal["plugin", "mcp_server", "base_image"]
    result: Literal["allowed", "blocked", "denied"]
    reason: str  # Human-readable explanation
    source: Literal["policy", "org", "team", "project", "repo", "user"] | None
    exception_id: str | None  # ID of the exception that allowed it
    expires_in: str | None  # Relative time like "7h45m"


@dataclass
class EvaluationResult:
    """The complete result of evaluating a config with exceptions applied.

    Maintains lists of blocked items, denied additions, and decisions.
    This is the primary data structure passed through the evaluation pipeline.
    """

    blocked_items: list[BlockedItem] = field(default_factory=list)
    denied_additions: list[DeniedAddition] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def copy(self) -> EvaluationResult:
        """Create a shallow copy for immutable-style updates."""
        return EvaluationResult(
            blocked_items=list(self.blocked_items),
            denied_additions=list(self.denied_additions),
            decisions=list(self.decisions),
            warnings=list(self.warnings),
        )
