"""Fake SafetyEngine for tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from scc_cli.core.contracts import SafetyPolicy, SafetyVerdict


@dataclass
class FakeSafetyEngine:
    """Configurable SafetyEngine stub for unit tests.

    By default returns an allow-all verdict. Set ``verdict`` to
    override the return value for all calls. Calls are recorded
    in ``calls`` for downstream assertion.
    """

    verdict: SafetyVerdict = field(
        default_factory=lambda: SafetyVerdict(allowed=True, reason="fake: allow-all"),
    )
    calls: list[tuple[str, SafetyPolicy]] = field(default_factory=list)

    def evaluate(self, command: str, policy: SafetyPolicy) -> SafetyVerdict:
        """Record the call and return the configured verdict."""
        self.calls.append((command, policy))
        return self.verdict
