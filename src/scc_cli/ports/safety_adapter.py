"""SafetyAdapter protocol — provider-specific UX/audit wrapper over SafetyEngine."""

from __future__ import annotations

from typing import Protocol

from scc_cli.core.contracts import SafetyCheckResult, SafetyPolicy


class SafetyAdapter(Protocol):
    """Port for provider-specific safety check formatting and audit emission.

    Implementations delegate verdict logic to a SafetyEngine, then format
    the result for provider UX and emit an audit event.
    """

    def check_command(self, command: str, policy: SafetyPolicy) -> SafetyCheckResult:
        """Evaluate a command through the safety engine, emit audit, and format result.

        Args:
            command: Shell command string to evaluate.
            policy: Safety policy containing rules and baseline action.

        Returns:
            A provider-formatted safety check result.
        """
        ...
