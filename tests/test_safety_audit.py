"""Tests for safety audit reader, CLI command, and support-bundle integration."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from scc_cli.adapters.local_audit_event_sink import serialize_audit_event
from scc_cli.application.safety_audit import read_safety_audit_diagnostics
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


def _safety_event(
    *,
    command: str = "rm -rf /",
    verdict_allowed: str = "true",
    matched_rule: str | None = None,
    provider_id: str = "claude",
    severity: SeverityLevel = SeverityLevel.INFO,
    message: str = "safety check",
) -> str:
    meta: dict[str, str] = {
        "command": command,
        "verdict_allowed": verdict_allowed,
        "provider_id": provider_id,
    }
    if matched_rule is not None:
        meta["matched_rule"] = matched_rule
    return serialize_audit_event(
        AuditEvent(
            event_type="safety.check",
            message=message,
            severity=severity,
            subject=provider_id,
            metadata=meta,
        )
    )


def _launch_event(*, provider_id: str = "claude", message: str = "preflight passed") -> str:
    return serialize_audit_event(
        AuditEvent(
            event_type="launch.preflight.passed",
            message=message,
            severity=SeverityLevel.INFO,
            subject=provider_id,
            metadata={"provider_id": provider_id},
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Reader unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSafetyAuditReader:
    def test_empty_sink_returns_empty_state(self, tmp_path: Path) -> None:
        """No file exists → state 'unavailable'."""
        diag = read_safety_audit_diagnostics(audit_path=tmp_path / "missing.jsonl", limit=5)
        assert diag.state == "unavailable"
        assert diag.recent_events == ()
        assert diag.last_blocked is None
        assert diag.blocked_count == 0
        assert diag.allowed_count == 0

    def test_filters_to_safety_check_events(self, tmp_path: Path) -> None:
        """Mixed JSONL with launch and safety.check events → only safety.check returned."""
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [
                _launch_event(provider_id="claude"),
                _safety_event(command="ls", verdict_allowed="true"),
                _launch_event(provider_id="codex"),
                _safety_event(command="rm -rf /", verdict_allowed="false"),
            ],
        )

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=10)

        assert diag.state == "available"
        assert len(diag.recent_events) == 2
        for event in diag.recent_events:
            assert event.event_type == "safety.check"

    def test_blocked_allowed_counts(self, tmp_path: Path) -> None:
        """Verify blocked_count and allowed_count."""
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [
                _safety_event(command="ls", verdict_allowed="true"),
                _safety_event(command="cat file", verdict_allowed="true"),
                _safety_event(command="rm -rf /", verdict_allowed="false"),
            ],
        )

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=10)

        assert diag.allowed_count == 2
        assert diag.blocked_count == 1

    def test_last_blocked_populated(self, tmp_path: Path) -> None:
        """Verify last_blocked is the most recent blocked event."""
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [
                _safety_event(command="rm file1", verdict_allowed="false", message="block 1"),
                _safety_event(command="rm file2", verdict_allowed="false", message="block 2"),
                _safety_event(command="ls", verdict_allowed="true"),
            ],
        )

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=10)

        assert diag.last_blocked is not None
        assert diag.last_blocked.message == "block 2"
        assert diag.last_blocked.command == "rm file2"

    def test_bounded_scan(self, tmp_path: Path) -> None:
        """Verify limit parameter works — only last N safety events returned."""
        audit_path = tmp_path / "events.jsonl"
        events = [
            _safety_event(command=f"cmd-{i}", verdict_allowed="true", message=f"event {i}")
            for i in range(10)
        ]
        _write_audit_lines(audit_path, events)

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=3)

        assert len(diag.recent_events) == 3
        # Most recent first (reversed)
        assert diag.recent_events[0].message == "event 9"
        assert diag.recent_events[1].message == "event 8"
        assert diag.recent_events[2].message == "event 7"

    def test_malformed_lines_skipped(self, tmp_path: Path) -> None:
        """Malformed JSON lines don't crash, increment malformed count."""
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [
                _safety_event(command="ls", verdict_allowed="true"),
                b"this is not json{{{",
                _safety_event(command="cat", verdict_allowed="true"),
            ],
        )

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=10)

        assert diag.malformed_line_count == 1
        assert len(diag.recent_events) == 2

    def test_redact_paths(self, tmp_path: Path) -> None:
        """Home directory replaced with ~."""
        home = str(Path.home())
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [
                _safety_event(
                    command=f"{home}/scripts/danger.sh",
                    verdict_allowed="false",
                ),
            ],
        )

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=10, redact_paths=True)

        assert diag.recent_events[0].command is not None
        assert home not in diag.recent_events[0].command
        assert "~" in diag.recent_events[0].command

    def test_redact_paths_disabled(self, tmp_path: Path) -> None:
        """When redact_paths=False, home dir stays in output."""
        home = str(Path.home())
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [
                _safety_event(
                    command=f"{home}/scripts/danger.sh",
                    verdict_allowed="false",
                ),
            ],
        )

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=10, redact_paths=False)

        assert diag.recent_events[0].command is not None
        assert home in diag.recent_events[0].command

    def test_to_dict_returns_serializable(self, tmp_path: Path) -> None:
        """to_dict() returns JSON-serializable dict."""
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [_safety_event(command="ls", verdict_allowed="true")],
        )

        diag = read_safety_audit_diagnostics(audit_path=audit_path, limit=5)
        d = diag.to_dict()

        assert isinstance(d, dict)
        json.dumps(d)  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# CLI command tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSafetyAuditCLI:
    def test_safety_audit_json_mode(self, tmp_path: Path) -> None:
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [_safety_event(command="rm /", verdict_allowed="false")],
        )

        with patch("scc_cli.commands.support.config.LAUNCH_AUDIT_FILE", audit_path):
            result = runner.invoke(app, ["support", "safety-audit", "--json"])

        assert result.exit_code == 0
        envelope = json.loads(result.output)
        assert envelope["kind"] == "SafetyAudit"
        assert envelope["data"]["state"] == "available"

    def test_safety_audit_human_mode(self, tmp_path: Path) -> None:
        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [_safety_event(command="rm /", verdict_allowed="false")],
        )

        with patch("scc_cli.commands.support.config.LAUNCH_AUDIT_FILE", audit_path):
            result = runner.invoke(app, ["support", "safety-audit"])

        assert result.exit_code == 0
        assert "Safety audit" in result.output
        assert "Blocked:" in result.output

    def test_safety_audit_unavailable_sink(self, tmp_path: Path) -> None:
        with patch(
            "scc_cli.commands.support.config.LAUNCH_AUDIT_FILE",
            tmp_path / "missing.jsonl",
        ):
            result = runner.invoke(app, ["support", "safety-audit"])

        assert result.exit_code == 0
        assert "unavailable" in result.output


# ─────────────────────────────────────────────────────────────────────────────
# Support bundle integration test
# ─────────────────────────────────────────────────────────────────────────────


class TestSupportBundleSafetySection:
    def test_support_bundle_has_safety_section(self, tmp_path: Path) -> None:
        """Mock dependencies, verify manifest['safety'] key exists."""
        from scc_cli.application.support_bundle import (
            SupportBundleDependencies,
            SupportBundleRequest,
            build_support_bundle_manifest,
        )
        from scc_cli.doctor import CheckResult, DoctorResult

        class _FakeFilesystem:
            def exists(self, path: Path) -> bool:
                return False

            def read_text(self, path: Path) -> str:
                return "{}"

        class _FixedClock:
            def now(self) -> datetime:
                return datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        class _PassingDoctor:
            def run(self, workspace: str | None = None) -> DoctorResult:
                return DoctorResult(checks=[CheckResult(name="Docker", passed=True, message="OK")])

        class _FakeArchive:
            def write_manifest(self, path: str, content: str) -> None:
                pass

        audit_path = tmp_path / "events.jsonl"
        _write_audit_lines(
            audit_path,
            [_safety_event(command="ls", verdict_allowed="true")],
        )

        deps = SupportBundleDependencies(
            filesystem=_FakeFilesystem(),  # type: ignore[arg-type]
            clock=_FixedClock(),  # type: ignore[arg-type]
            doctor_runner=_PassingDoctor(),  # type: ignore[arg-type]
            archive_writer=_FakeArchive(),  # type: ignore[arg-type]
            launch_audit_path=audit_path,
        )

        request = SupportBundleRequest(
            output_path=tmp_path / "bundle.zip",
            redact_paths=True,
        )

        with patch(
            "scc_cli.application.support_bundle._load_raw_org_config_for_bundle",
            return_value=None,
        ):
            manifest = build_support_bundle_manifest(request, dependencies=deps)

        assert "safety" in manifest
        safety = manifest["safety"]
        assert "effective_policy" in safety
        assert "recent_audit" in safety
        assert safety["effective_policy"]["action"] == "block"
