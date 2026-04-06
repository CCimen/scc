from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from scc_cli.adapters.local_audit_event_sink import LocalAuditEventSink, serialize_audit_event
from scc_cli.core.contracts import AuditEvent
from scc_cli.core.enums import SeverityLevel


def test_serialize_audit_event_emits_canonical_json() -> None:
    occurred_at = datetime(2026, 4, 3, tzinfo=timezone.utc)
    event = AuditEvent(
        event_type="launch.preflight.passed",
        message="Launch preflight passed.",
        severity=SeverityLevel.INFO,
        occurred_at=occurred_at,
        subject="claude",
        metadata={"network_policy": "open", "required_destination_sets": "anthropic-core"},
    )

    payload = json.loads(serialize_audit_event(event))

    assert payload == {
        "event_type": "launch.preflight.passed",
        "message": "Launch preflight passed.",
        "metadata": {
            "network_policy": "open",
            "required_destination_sets": "anthropic-core",
        },
        "occurred_at": occurred_at.isoformat(),
        "severity": "info",
        "subject": "claude",
    }


def test_local_audit_event_sink_appends_jsonl_records(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit" / "launch-events.jsonl"
    sink = LocalAuditEventSink(
        audit_path=audit_path,
        lock_path=tmp_path / "audit" / "launch-events.lock",
    )

    sink.append(
        AuditEvent(
            event_type="launch.preflight.passed",
            message="Launch preflight passed.",
            severity=SeverityLevel.INFO,
            subject="claude",
            metadata={"network_policy": "open"},
        )
    )
    sink.append(
        AuditEvent(
            event_type="launch.started",
            message="Launch started.",
            severity=SeverityLevel.INFO,
            subject="claude",
            metadata={"sandbox_id": "sandbox-1"},
        )
    )

    lines = audit_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])
    assert first["event_type"] == "launch.preflight.passed"
    assert first["metadata"]["network_policy"] == "open"
    assert second["event_type"] == "launch.started"
    assert second["metadata"]["sandbox_id"] == "sandbox-1"


def test_local_audit_event_sink_describes_file_destination(tmp_path: Path) -> None:
    audit_path = tmp_path / "launch-events.jsonl"
    sink = LocalAuditEventSink(
        audit_path=audit_path,
        lock_path=tmp_path / "launch-events.lock",
    )

    assert sink.describe_destination() == str(audit_path)
