"""Port for durable audit-event persistence."""

from __future__ import annotations

from typing import Protocol

from scc_cli.core.contracts import AuditEvent


class AuditEventSink(Protocol):
    """Persist canonical audit events to a durable sink."""

    def append(self, event: AuditEvent) -> None:
        """Append one audit event to the sink."""

    def describe_destination(self) -> str:
        """Return a human-readable destination description for error messages."""
