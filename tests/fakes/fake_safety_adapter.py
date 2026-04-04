"""Fake SafetyAdapter for tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from scc_cli.core.contracts import SafetyCheckResult, SafetyPolicy, SafetyVerdict


@dataclass
class FakeSafetyAdapter:
    """Configurable SafetyAdapter stub for downstream tests.

    By default returns an allowed verdict with empty message and
    audit_emitted=False. Set ``result`` to override. Calls are
    recorded in ``calls`` for assertion.
    """

    result: SafetyCheckResult = field(
        default_factory=lambda: SafetyCheckResult(
            verdict=SafetyVerdict(allowed=True, reason="fake: allow-all"),
            user_message="",
            audit_emitted=False,
        ),
    )
    calls: list[tuple[str, SafetyPolicy]] = field(default_factory=list)

    def check_command(self, command: str, policy: SafetyPolicy) -> SafetyCheckResult:
        """Record the call and return the configured result."""
        self.calls.append((command, policy))
        return self.result
