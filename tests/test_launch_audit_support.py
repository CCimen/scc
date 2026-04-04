from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from scc_cli.adapters.local_audit_event_sink import serialize_audit_event
from scc_cli.cli import app
from scc_cli.core.contracts import AuditEvent
from scc_cli.core.enums import SeverityLevel

runner = CliRunner()


def _write_audit_lines(path: Path, lines: list[str | bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        for line in lines:
            payload = line if isinstance(line, bytes) else line.encode("utf-8")
            handle.write(payload)
            handle.write(b"\n")


def _event(
    *,
    event_type: str,
    severity: SeverityLevel = SeverityLevel.INFO,
    provider_id: str,
    message: str,
    metadata: dict[str, str] | None = None,
) -> str:
    return serialize_audit_event(
        AuditEvent(
            event_type=event_type,
            message=message,
            severity=severity,
            subject=provider_id,
            metadata={"provider_id": provider_id, **(metadata or {})},
        )
    )


def test_read_launch_audit_diagnostics_handles_missing_file(tmp_path: Path) -> None:
    from scc_cli.application.launch.audit_log import read_launch_audit_diagnostics

    diagnostics = read_launch_audit_diagnostics(audit_path=tmp_path / "missing.jsonl", limit=5)

    assert diagnostics.state == "unavailable"
    assert diagnostics.recent_events == ()
    assert diagnostics.last_failure is None
    assert diagnostics.malformed_line_count == 0


def test_read_launch_audit_diagnostics_handles_empty_file(tmp_path: Path) -> None:
    from scc_cli.application.launch.audit_log import read_launch_audit_diagnostics

    audit_path = tmp_path / "launch-events.jsonl"
    audit_path.write_text("", encoding="utf-8")

    diagnostics = read_launch_audit_diagnostics(audit_path=audit_path, limit=5)

    assert diagnostics.state == "empty"
    assert diagnostics.scanned_line_count == 0
    assert diagnostics.recent_events == ()


def test_read_launch_audit_diagnostics_skips_malformed_lines_and_redacts_paths(
    tmp_path: Path,
) -> None:
    from scc_cli.application.launch.audit_log import read_launch_audit_diagnostics

    home = str(Path.home())
    audit_path = tmp_path / "launch-events.jsonl"
    _write_audit_lines(
        audit_path,
        [
            _event(
                event_type="launch.preflight.passed",
                provider_id="claude",
                message="Launch preflight passed.",
                metadata={"workspace_path": f"{home}/projects/demo"},
            ),
            "{not-json",
            _event(
                event_type="launch.preflight.failed",
                provider_id="claude",
                severity=SeverityLevel.ERROR,
                message="Launch preflight failed.",
                metadata={
                    "workspace_path": f"{home}/projects/demo",
                    "failure_reason": f"Blocked for {home}/projects/demo",
                },
            ),
            _event(
                event_type="launch.started",
                provider_id="codex",
                message="Launch started.",
                metadata={"workspace_path": f"{home}/projects/other"},
            ),
        ],
    )

    diagnostics = read_launch_audit_diagnostics(audit_path=audit_path, limit=2)

    assert diagnostics.state == "available"
    assert diagnostics.malformed_line_count == 1
    assert diagnostics.last_malformed_line == 2
    assert [event.event_type for event in diagnostics.recent_events] == [
        "launch.started",
        "launch.preflight.failed",
    ]
    assert diagnostics.last_failure is not None
    assert diagnostics.last_failure.event_type == "launch.preflight.failed"
    assert diagnostics.last_failure.failure_reason == "Blocked for ~/projects/demo"
    assert diagnostics.recent_events[0].metadata["workspace_path"] == "~/projects/other"
    assert diagnostics.sink_path.startswith("~") or str(Path.home()) not in diagnostics.sink_path


def test_read_launch_audit_diagnostics_replaces_invalid_utf8_bytes(tmp_path: Path) -> None:
    from scc_cli.application.launch.audit_log import read_launch_audit_diagnostics

    audit_path = tmp_path / "launch-events.jsonl"
    _write_audit_lines(
        audit_path,
        [
            b'{"event_type":"launch.started","message":"bad\xffvalue","severity":"info",'
            b'"occurred_at":"2026-04-03T18:00:00+00:00","subject":"claude",'
            b'"metadata":{"provider_id":"claude"}}'
        ],
    )

    diagnostics = read_launch_audit_diagnostics(audit_path=audit_path, limit=1)

    assert diagnostics.state == "available"
    assert diagnostics.malformed_line_count == 0
    assert diagnostics.recent_events[0].message == "bad�value"


def test_read_launch_audit_diagnostics_handles_unreadable_path(tmp_path: Path) -> None:
    from scc_cli.application.launch.audit_log import read_launch_audit_diagnostics

    audit_path = tmp_path / "launch-events.jsonl"
    audit_path.mkdir()

    diagnostics = read_launch_audit_diagnostics(audit_path=audit_path, limit=3)

    assert diagnostics.state == "unavailable"
    assert diagnostics.error is not None


def test_read_launch_audit_diagnostics_respects_zero_limit(tmp_path: Path) -> None:
    from scc_cli.application.launch.audit_log import read_launch_audit_diagnostics

    audit_path = tmp_path / "launch-events.jsonl"
    _write_audit_lines(
        audit_path,
        [
            _event(
                event_type="launch.started",
                provider_id="claude",
                message="Launch started.",
            )
        ],
    )

    diagnostics = read_launch_audit_diagnostics(audit_path=audit_path, limit=0)

    assert diagnostics.state == "available"
    assert diagnostics.recent_events == ()
    assert diagnostics.scanned_line_count == 0


def test_support_launch_audit_json_outputs_stable_envelope(tmp_path: Path, monkeypatch) -> None:
    audit_path = tmp_path / "launch-events.jsonl"
    _write_audit_lines(
        audit_path,
        [
            _event(
                event_type="launch.preflight.failed",
                provider_id="claude",
                severity=SeverityLevel.ERROR,
                message="Launch preflight failed.",
                metadata={
                    "workspace_path": f"{Path.home()}/projects/demo",
                    "failure_reason": "Policy blocked provider-core access",
                },
            )
        ],
    )
    monkeypatch.setattr("scc_cli.commands.support.config.LAUNCH_AUDIT_FILE", audit_path)

    result = runner.invoke(app, ["support", "launch-audit", "--json", "--limit", "1"])

    assert result.exit_code == 0
    envelope = json.loads(result.stdout)
    assert envelope["kind"] == "LaunchAudit"
    assert envelope["status"]["ok"] is True
    assert envelope["data"]["state"] == "available"
    assert envelope["data"]["recent_events"][0]["event_type"] == "launch.preflight.failed"
    assert envelope["data"]["recent_events"][0]["metadata"]["workspace_path"] == "~/projects/demo"


def test_support_launch_audit_human_output_mentions_last_failure(
    tmp_path: Path, monkeypatch
) -> None:
    audit_path = tmp_path / "launch-events.jsonl"
    _write_audit_lines(
        audit_path,
        [
            _event(
                event_type="launch.preflight.failed",
                provider_id="claude",
                severity=SeverityLevel.ERROR,
                message="Launch preflight failed.",
                metadata={"failure_reason": "Destination set blocked"},
            )
        ],
    )
    monkeypatch.setattr("scc_cli.commands.support.config.LAUNCH_AUDIT_FILE", audit_path)

    result = runner.invoke(app, ["support", "launch-audit", "--limit", "1"])

    assert result.exit_code == 0
    assert "Launch audit" in result.stdout
    assert "Last failure" in result.stdout
    assert "Destination set blocked" in result.stdout
