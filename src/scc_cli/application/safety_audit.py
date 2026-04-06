"""Bounded reader for safety-check events in the durable JSONL audit sink."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from scc_cli import config
from scc_cli.application.launch.audit_log import _tail_lines

DEFAULT_SAFETY_AUDIT_LIMIT = 10
DEFAULT_SCAN_LINE_FLOOR = 50


@dataclass(frozen=True)
class SafetyAuditEventRecord:
    """One parsed safety-check event from the recent scan window."""

    line_number: int
    event_type: str
    message: str
    severity: str
    occurred_at: str
    command: str | None
    verdict_allowed: str | None
    matched_rule: str | None
    provider_id: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SafetyAuditDiagnostics:
    """Redaction-safe summary of recent safety-check audit state."""

    sink_path: str
    state: str
    requested_limit: int
    scanned_line_count: int
    malformed_line_count: int
    last_malformed_line: int | None
    recent_events: tuple[SafetyAuditEventRecord, ...]
    last_blocked: SafetyAuditEventRecord | None
    blocked_count: int
    allowed_count: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable payload."""
        return asdict(self)


def read_safety_audit_diagnostics(
    *,
    audit_path: Path | None = None,
    limit: int = DEFAULT_SAFETY_AUDIT_LIMIT,
    redact_paths: bool = True,
) -> SafetyAuditDiagnostics:
    """Read a bounded, redaction-safe summary of recent safety-check events."""
    resolved_path = audit_path or config.LAUNCH_AUDIT_FILE
    requested_limit = max(limit, 0)
    sink_path = _redact_string(str(resolved_path), redact_paths=redact_paths)

    if not resolved_path.exists():
        return SafetyAuditDiagnostics(
            sink_path=sink_path,
            state="unavailable",
            requested_limit=requested_limit,
            scanned_line_count=0,
            malformed_line_count=0,
            last_malformed_line=None,
            recent_events=(),
            last_blocked=None,
            blocked_count=0,
            allowed_count=0,
        )

    try:
        if not resolved_path.is_file():
            raise OSError(f"{resolved_path} is not a file")
        raw_lines = _tail_lines(resolved_path, max_lines=_scan_line_limit(requested_limit))
    except OSError as exc:
        return SafetyAuditDiagnostics(
            sink_path=sink_path,
            state="unavailable",
            requested_limit=requested_limit,
            scanned_line_count=0,
            malformed_line_count=0,
            last_malformed_line=None,
            recent_events=(),
            last_blocked=None,
            blocked_count=0,
            allowed_count=0,
            error=str(exc),
        )

    if len(raw_lines) == 0:
        state = (
            "available" if requested_limit == 0 and resolved_path.stat().st_size > 0 else "empty"
        )
        return SafetyAuditDiagnostics(
            sink_path=sink_path,
            state=state,
            requested_limit=requested_limit,
            scanned_line_count=0,
            malformed_line_count=0,
            last_malformed_line=None,
            recent_events=(),
            last_blocked=None,
            blocked_count=0,
            allowed_count=0,
        )

    safety_events: list[SafetyAuditEventRecord] = []
    last_blocked: SafetyAuditEventRecord | None = None
    blocked_count = 0
    allowed_count = 0
    malformed_line_count = 0
    last_malformed_line: int | None = None

    for line_number, raw_line in enumerate(raw_lines, start=1):
        record = _parse_safety_record(
            raw_line,
            line_number=line_number,
            redact_paths=redact_paths,
        )
        if record is None:
            # Either malformed or not a safety.check event — distinguish.
            if _is_parseable_non_safety(raw_line):
                continue
            malformed_line_count += 1
            last_malformed_line = line_number
            continue

        safety_events.append(record)

        if record.verdict_allowed == "false" or record.verdict_allowed is False:
            blocked_count += 1
            last_blocked = record
        else:
            allowed_count += 1

    limited_events = (
        tuple(reversed(safety_events[-requested_limit:])) if requested_limit > 0 else ()
    )

    return SafetyAuditDiagnostics(
        sink_path=sink_path,
        state="available",
        requested_limit=requested_limit,
        scanned_line_count=len(raw_lines),
        malformed_line_count=malformed_line_count,
        last_malformed_line=last_malformed_line,
        recent_events=limited_events,
        last_blocked=last_blocked,
        blocked_count=blocked_count,
        allowed_count=allowed_count,
    )


def _scan_line_limit(limit: int) -> int:
    if limit <= 0:
        return 0
    return max(limit * 4, DEFAULT_SCAN_LINE_FLOOR)


def _is_parseable_non_safety(raw_line: str) -> bool:
    """Return True when the line is valid JSON but not a safety.check event."""
    if raw_line.strip() == "":
        return True
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    event_type = payload.get("event_type")
    return isinstance(event_type, str) and event_type != "safety.check"


def _parse_safety_record(
    raw_line: str,
    *,
    line_number: int,
    redact_paths: bool,
) -> SafetyAuditEventRecord | None:
    """Parse a raw JSONL line; return a record only for safety.check events."""
    if raw_line.strip() == "":
        return None

    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None

    event_type = payload.get("event_type")
    if not isinstance(event_type, str) or event_type != "safety.check":
        return None

    sanitized = _redact_value(payload, redact_paths=redact_paths)
    if not isinstance(sanitized, dict):
        return None

    message = sanitized.get("message")
    severity = sanitized.get("severity")
    occurred_at = sanitized.get("occurred_at")
    metadata = sanitized.get("metadata")

    if not isinstance(message, str):
        return None
    if not isinstance(severity, str):
        return None
    if not isinstance(occurred_at, str):
        return None
    if not isinstance(metadata, dict):
        metadata = {}

    command = metadata.get("command")
    if command is not None and not isinstance(command, str):
        command = None

    verdict_allowed = metadata.get("verdict_allowed")
    if verdict_allowed is not None:
        verdict_allowed = str(verdict_allowed)

    matched_rule = metadata.get("matched_rule")
    if matched_rule is not None and not isinstance(matched_rule, str):
        matched_rule = None

    provider_id = metadata.get("provider_id")
    if provider_id is not None and not isinstance(provider_id, str):
        provider_id = None

    return SafetyAuditEventRecord(
        line_number=line_number,
        event_type=event_type,
        message=message,
        severity=severity,
        occurred_at=occurred_at,
        command=command,
        verdict_allowed=verdict_allowed,
        matched_rule=matched_rule,
        provider_id=provider_id,
        metadata=metadata,
    )


def _redact_value(value: Any, *, redact_paths: bool) -> Any:
    if isinstance(value, str):
        return _redact_string(value, redact_paths=redact_paths)
    if isinstance(value, dict):
        return {key: _redact_value(item, redact_paths=redact_paths) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_value(item, redact_paths=redact_paths) for item in value]
    return value


def _redact_string(value: str, *, redact_paths: bool) -> str:
    if not redact_paths:
        return value
    home = str(Path.home())
    return value.replace(home, "~") if home in value else value
