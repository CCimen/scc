"""Local append-only JSONL audit sink."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from scc_cli import config
from scc_cli.core.contracts import AuditEvent
from scc_cli.utils.locks import DEFAULT_TIMEOUT, file_lock


@dataclass(frozen=True)
class LocalAuditEventSink:
    """Persist audit events as append-only JSONL records on local disk."""

    audit_path: Path = config.LAUNCH_AUDIT_FILE
    lock_path: Path = config.LAUNCH_AUDIT_LOCK_FILE
    lock_timeout: float = DEFAULT_TIMEOUT

    def append(self, event: AuditEvent) -> None:
        """Append one structured event to the local JSONL sink."""
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        line = serialize_audit_event(event)
        with file_lock(self.lock_path, timeout=self.lock_timeout):
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())

    def describe_destination(self) -> str:
        """Return the on-disk audit file path."""
        return str(self.audit_path)


def serialize_audit_event(event: AuditEvent) -> str:
    """Return a compact JSON line for one audit event."""
    payload = asdict(event)
    payload["severity"] = event.severity.value
    payload["occurred_at"] = event.occurred_at.isoformat()
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)
