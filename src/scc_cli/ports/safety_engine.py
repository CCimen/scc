"""SafetyEngine protocol — provider-neutral command evaluation port."""

from __future__ import annotations

from typing import Protocol

from scc_cli.core.contracts import SafetyPolicy, SafetyVerdict


class SafetyEngine(Protocol):
    """Port for evaluating commands against a safety policy.

    Implementations match commands against rule modules (git rules,
    network tool rules, etc.) and return a typed verdict. The engine
    is provider-neutral: both Claude and Codex adapters consume it.
    """

    def evaluate(self, command: str, policy: SafetyPolicy) -> SafetyVerdict:
        """Evaluate a command string against the given safety policy.

        Args:
            command: Shell command string to evaluate.
            policy: Safety policy containing rules and baseline action.

        Returns:
            A typed verdict indicating whether the command is allowed.
        """
        ...
