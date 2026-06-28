"""Bounded reader for the durable launch-audit JSONL sink."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scc_cli import config
from scc_cli.application.audit_jsonl import (
    redact_string,
    redact_value,
    scan_line_limit,
    tail_lines,
)
from scc_cli.core.enums import SeverityLevel

DEFAULT_LAUNCH_AUDIT_LIMIT = 10


@dataclass(frozen=True)
class LaunchAuditEventRecord:
    """One parsed launch-audit event from the recent scan window."""

    line_number: int
    event_type: str
    message: str
    severity: str
    occurred_at: str
    subject: str | None
    provider_id: str | None
    failure_reason: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class LaunchAuditDiagnostics:
    """Redaction-safe summary of the recent launch-audit sink state."""

    sink_path: str
    state: str
    requested_limit: int
    scanned_line_count: int
    malformed_line_count: int
    last_malformed_line: int | None
    recent_events: tuple[LaunchAuditEventRecord, ...]
    last_failure: LaunchAuditEventRecord | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable payload."""
        return asdict(self)


def read_launch_audit_diagnostics(
    *,
    audit_path: Path | None = None,
    limit: int = DEFAULT_LAUNCH_AUDIT_LIMIT,
    redact_paths: bool = True,
) -> LaunchAuditDiagnostics:
    """Read a bounded, redaction-safe summary of recent launch-audit events."""
    resolved_path = audit_path or config.LAUNCH_AUDIT_FILE
    requested_limit = max(limit, 0)
    sink_path = redact_string(str(resolved_path), redact_paths=redact_paths)

    if not resolved_path.exists():
        return LaunchAuditDiagnostics(
            sink_path=sink_path,
            state="unavailable",
            requested_limit=requested_limit,
            scanned_line_count=0,
            malformed_line_count=0,
            last_malformed_line=None,
            recent_events=(),
            last_failure=None,
        )

    try:
        if not resolved_path.is_file():
            raise OSError(f"{resolved_path} is not a file")
        raw_lines = tail_lines(resolved_path, max_lines=scan_line_limit(requested_limit))
    except OSError as exc:
        return LaunchAuditDiagnostics(
            sink_path=sink_path,
            state="unavailable",
            requested_limit=requested_limit,
            scanned_line_count=0,
            malformed_line_count=0,
            last_malformed_line=None,
            recent_events=(),
            last_failure=None,
            error=str(exc),
        )

    if len(raw_lines) == 0:
        state = (
            "available" if requested_limit == 0 and resolved_path.stat().st_size > 0 else "empty"
        )
        return LaunchAuditDiagnostics(
            sink_path=sink_path,
            state=state,
            requested_limit=requested_limit,
            scanned_line_count=0,
            malformed_line_count=0,
            last_malformed_line=None,
            recent_events=(),
            last_failure=None,
        )

    recent_events: list[LaunchAuditEventRecord] = []
    last_failure: LaunchAuditEventRecord | None = None
    malformed_line_count = 0
    last_malformed_line: int | None = None

    for line_number, raw_line in enumerate(raw_lines, start=1):
        record = _parse_record(
            raw_line,
            line_number=line_number,
            redact_paths=redact_paths,
        )
        if record is None:
            malformed_line_count += 1
            last_malformed_line = line_number
            continue
        recent_events.append(record)
        if _is_failure_record(record):
            last_failure = record

    limited_events = (
        tuple(reversed(recent_events[-requested_limit:])) if requested_limit > 0 else ()
    )

    return LaunchAuditDiagnostics(
        sink_path=sink_path,
        state="available",
        requested_limit=requested_limit,
        scanned_line_count=len(raw_lines),
        malformed_line_count=malformed_line_count,
        last_malformed_line=last_malformed_line,
        recent_events=limited_events,
        last_failure=last_failure,
    )


def _parse_record(
    raw_line: str,
    *,
    line_number: int,
    redact_paths: bool,
) -> LaunchAuditEventRecord | None:
    if raw_line.strip() == "":
        return None

    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    sanitized_payload = redact_value(payload, redact_paths=redact_paths)
    if not isinstance(sanitized_payload, dict):
        return None

    event_type = sanitized_payload.get("event_type")
    message = sanitized_payload.get("message")
    severity = sanitized_payload.get("severity")
    occurred_at = sanitized_payload.get("occurred_at")
    metadata = sanitized_payload.get("metadata")
    subject = sanitized_payload.get("subject")

    if not isinstance(event_type, str):
        return None
    if not isinstance(message, str):
        return None
    if not isinstance(severity, str):
        return None
    if not isinstance(occurred_at, str):
        return None
    if not isinstance(metadata, dict):
        return None
    if subject is not None and not isinstance(subject, str):
        return None

    provider_id = metadata.get("provider_id")
    if provider_id is not None and not isinstance(provider_id, str):
        provider_id = None

    failure_reason = metadata.get("failure_reason")
    if failure_reason is not None and not isinstance(failure_reason, str):
        failure_reason = None

    return LaunchAuditEventRecord(
        line_number=line_number,
        event_type=event_type,
        message=message,
        severity=severity,
        occurred_at=occurred_at,
        subject=subject,
        provider_id=provider_id or subject,
        failure_reason=failure_reason,
        metadata=metadata,
    )


def _is_failure_record(record: LaunchAuditEventRecord) -> bool:
    return record.severity == SeverityLevel.ERROR.value or record.event_type.endswith(".failed")
