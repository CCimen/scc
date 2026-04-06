"""Claude-specific safety adapter — UX formatting and audit emission."""

from __future__ import annotations

from scc_cli.core.contracts import AuditEvent, SafetyCheckResult, SafetyPolicy
from scc_cli.core.enums import SeverityLevel
from scc_cli.ports.audit_event_sink import AuditEventSink
from scc_cli.ports.safety_engine import SafetyEngine


class ClaudeSafetyAdapter:
    """Wraps SafetyEngine with Claude-specific user messages and audit events."""

    def __init__(self, engine: SafetyEngine, audit_sink: AuditEventSink) -> None:
        self._engine = engine
        self._audit_sink = audit_sink

    def check_command(self, command: str, policy: SafetyPolicy) -> SafetyCheckResult:
        """Evaluate *command* against *policy*, emit audit, return formatted result."""
        verdict = self._engine.evaluate(command, policy)

        severity = SeverityLevel.WARNING if not verdict.allowed else SeverityLevel.INFO
        if verdict.allowed:
            user_message = "[Claude] Command allowed"
        else:
            user_message = f"[Claude] Command blocked: {verdict.reason}"

        event = AuditEvent(
            event_type="safety.check",
            message=user_message,
            severity=severity,
            subject="claude",
            metadata={
                "provider_id": "claude",
                "command": command,
                "verdict_allowed": str(verdict.allowed).lower(),
                "matched_rule": verdict.matched_rule or "",
                "command_family": verdict.command_family or "",
            },
        )
        self._audit_sink.append(event)

        return SafetyCheckResult(
            verdict=verdict,
            user_message=user_message,
            audit_emitted=True,
        )
