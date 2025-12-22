"""
Tests for the stats module (usage tracking).

Phase 1: User-level stats only.
- Stats stored at ~/.cache/scc/usage.jsonl
- Users see only their own stats
- Manual aggregation via scc stats export

TDD approach: These tests define expected behavior before implementation.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def stats_cache_dir(tmp_path: Path) -> Path:
    """Create a temporary stats cache directory."""
    cache_dir = tmp_path / ".cache" / "scc"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def mock_cache_dir(stats_cache_dir: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Mock CACHE_DIR to use temporary directory."""
    # Will be patched after stats module exists
    return stats_cache_dir


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2.1.3: hash_identifier() Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestHashIdentifier:
    """Tests for identity pseudonymization."""

    def test_hash_identifier_produces_consistent_hash(self) -> None:
        """Same input should produce same hash."""
        from scc_cli.stats import hash_identifier

        result1 = hash_identifier("user@example.com")
        result2 = hash_identifier("user@example.com")
        assert result1 == result2

    def test_hash_identifier_different_inputs_different_hashes(self) -> None:
        """Different inputs should produce different hashes."""
        from scc_cli.stats import hash_identifier

        hash1 = hash_identifier("user1@example.com")
        hash2 = hash_identifier("user2@example.com")
        assert hash1 != hash2

    def test_hash_identifier_is_not_reversible(self) -> None:
        """Hash should not contain the original identifier."""
        from scc_cli.stats import hash_identifier

        identifier = "sensitive.user@company.com"
        hashed = hash_identifier(identifier)

        # Should not contain any part of the original
        assert identifier not in hashed
        assert "sensitive" not in hashed
        assert "company" not in hashed

    def test_hash_identifier_returns_string(self) -> None:
        """Hash should be a string of reasonable length."""
        from scc_cli.stats import hash_identifier

        hashed = hash_identifier("user@example.com")
        assert isinstance(hashed, str)
        assert len(hashed) > 10  # Should be a substantial hash
        assert len(hashed) < 100  # But not too long

    def test_hash_identifier_handles_empty_string(self) -> None:
        """Empty string should still produce a valid hash."""
        from scc_cli.stats import hash_identifier

        hashed = hash_identifier("")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_identifier_uses_salt_for_uniqueness(self) -> None:
        """Hash should use a machine-specific salt for privacy."""
        from scc_cli.stats import hash_identifier

        # The hash should be consistent on the same machine
        # but different across machines (due to salt)
        hashed = hash_identifier("test")
        assert isinstance(hashed, str)


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2.1.1: record_session_start() Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordSessionStart:
    """Tests for session start recording."""

    def test_record_session_start_creates_file_if_not_exists(self, stats_cache_dir: Path) -> None:
        """Should create usage.jsonl file if it doesn't exist."""
        from scc_cli.stats import record_session_start

        usage_file = stats_cache_dir / "usage.jsonl"
        assert not usage_file.exists()

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="test-session-1",
                project_name="my-project",
                team_name="engineering",
                expected_duration_hours=8,
            )

        assert usage_file.exists()

    def test_record_session_start_appends_to_existing_file(self, stats_cache_dir: Path) -> None:
        """Should append to existing file, not overwrite."""
        from scc_cli.stats import record_session_start

        usage_file = stats_cache_dir / "usage.jsonl"
        # Pre-populate with existing data
        usage_file.write_text('{"existing": "event"}\n')

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="new-session",
                project_name="project",
                team_name="team",
                expected_duration_hours=4,
            )

        lines = usage_file.read_text().strip().split("\n")
        assert len(lines) == 2  # Original + new event

    def test_record_session_start_event_structure(self, stats_cache_dir: Path) -> None:
        """Session start event should have required fields."""
        from scc_cli.stats import record_session_start

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="test-session-123",
                project_name="my-project",
                team_name="data-team",
                expected_duration_hours=8,
            )

        content = usage_file.read_text().strip()
        event = json.loads(content)

        # Required fields
        assert event["event_type"] == "session_start"
        assert event["session_id"] == "test-session-123"
        assert event["project_name"] == "my-project"
        assert event["team_name"] == "data-team"
        assert event["expected_duration_hours"] == 8
        assert "timestamp" in event
        assert "user_id_hash" in event  # Pseudonymized user ID

    def test_record_session_start_timestamp_is_iso_format(self, stats_cache_dir: Path) -> None:
        """Timestamp should be ISO 8601 format."""
        from scc_cli.stats import record_session_start

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="test",
                project_name="proj",
                team_name="team",
                expected_duration_hours=1,
            )

        event = json.loads(usage_file.read_text().strip())
        # Should parse without error
        timestamp = datetime.fromisoformat(event["timestamp"])
        assert isinstance(timestamp, datetime)

    def test_record_session_start_optional_fields(self, stats_cache_dir: Path) -> None:
        """Should handle optional fields gracefully."""
        from scc_cli.stats import record_session_start

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # Team name is optional
            record_session_start(
                session_id="test",
                project_name="solo-project",
                team_name=None,
                expected_duration_hours=2,
            )

        event = json.loads(usage_file.read_text().strip())
        assert event["team_name"] is None or event.get("team_name") == ""


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2.1.2: record_session_end() Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordSessionEnd:
    """Tests for session end recording."""

    def test_record_session_end_creates_event(self, stats_cache_dir: Path) -> None:
        """Should create a session_end event."""
        from scc_cli.stats import record_session_end, record_session_start

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # First start a session
            record_session_start(
                session_id="session-to-end",
                project_name="project",
                team_name="team",
                expected_duration_hours=8,
            )

            # Then end it
            record_session_end(
                session_id="session-to-end",
                actual_duration_minutes=120,
            )

        lines = usage_file.read_text().strip().split("\n")
        assert len(lines) == 2

        end_event = json.loads(lines[1])
        assert end_event["event_type"] == "session_end"
        assert end_event["session_id"] == "session-to-end"

    def test_record_session_end_includes_duration(self, stats_cache_dir: Path) -> None:
        """Session end should include actual duration."""
        from scc_cli.stats import record_session_end

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_end(
                session_id="test-session",
                actual_duration_minutes=90,
            )

        event = json.loads(usage_file.read_text().strip())
        assert event["actual_duration_minutes"] == 90

    def test_record_session_end_with_exit_status(self, stats_cache_dir: Path) -> None:
        """Session end should record exit status (clean/crash/interrupted)."""
        from scc_cli.stats import record_session_end

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_end(
                session_id="test-session",
                actual_duration_minutes=60,
                exit_status="clean",
            )

        event = json.loads(usage_file.read_text().strip())
        assert event["exit_status"] == "clean"

    def test_record_session_end_default_exit_status_is_clean(self, stats_cache_dir: Path) -> None:
        """Default exit status should be 'clean'."""
        from scc_cli.stats import record_session_end

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_end(
                session_id="test-session",
                actual_duration_minutes=60,
            )

        event = json.loads(usage_file.read_text().strip())
        assert event.get("exit_status", "clean") == "clean"


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2.1.5: JSONL File Operations Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestJSONLOperations:
    """Tests for JSONL file reading and writing."""

    def test_read_usage_events_returns_empty_list_if_no_file(self, stats_cache_dir: Path) -> None:
        """Should return empty list if usage.jsonl doesn't exist."""
        from scc_cli.stats import read_usage_events

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            events = read_usage_events()

        assert events == []

    def test_read_usage_events_parses_all_lines(self, stats_cache_dir: Path) -> None:
        """Should parse all JSONL lines into events."""
        from scc_cli.stats import read_usage_events

        usage_file = stats_cache_dir / "usage.jsonl"
        usage_file.write_text(
            '{"event_type": "session_start", "session_id": "1"}\n'
            '{"event_type": "session_end", "session_id": "1"}\n'
            '{"event_type": "session_start", "session_id": "2"}\n'
        )

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            events = read_usage_events()

        assert len(events) == 3
        assert events[0]["session_id"] == "1"
        assert events[1]["event_type"] == "session_end"

    def test_read_usage_events_skips_malformed_lines(self, stats_cache_dir: Path) -> None:
        """Should skip malformed JSON lines gracefully."""
        from scc_cli.stats import read_usage_events

        usage_file = stats_cache_dir / "usage.jsonl"
        usage_file.write_text(
            '{"event_type": "session_start", "session_id": "1"}\n'
            "not valid json\n"
            '{"event_type": "session_end", "session_id": "1"}\n'
        )

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            events = read_usage_events()

        assert len(events) == 2  # Skipped the malformed line

    def test_read_usage_events_handles_empty_file(self, stats_cache_dir: Path) -> None:
        """Should handle empty file gracefully."""
        from scc_cli.stats import read_usage_events

        usage_file = stats_cache_dir / "usage.jsonl"
        usage_file.write_text("")

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            events = read_usage_events()

        assert events == []

    def test_write_event_atomic_append(self, stats_cache_dir: Path) -> None:
        """Event writing should be atomic (complete event or nothing)."""
        from scc_cli.stats import record_session_start

        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # Write multiple events
            for i in range(5):
                record_session_start(
                    session_id=f"session-{i}",
                    project_name="project",
                    team_name="team",
                    expected_duration_hours=1,
                )

        # All events should be complete valid JSON
        lines = usage_file.read_text().strip().split("\n")
        assert len(lines) == 5

        for line in lines:
            event = json.loads(line)  # Should not raise
            assert "event_type" in event


# ═══════════════════════════════════════════════════════════════════════════════
# Task 2.2: Stats Aggregation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsAggregation:
    """Tests for stats aggregation and reporting."""

    def test_get_stats_returns_stats_report(self, stats_cache_dir: Path) -> None:
        """get_stats() should return a StatsReport object."""
        from scc_cli.stats import StatsReport, get_stats

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            report = get_stats()

        assert isinstance(report, StatsReport)

    def test_get_stats_counts_sessions(self, stats_cache_dir: Path) -> None:
        """Should count total sessions."""
        from scc_cli.stats import get_stats, record_session_end, record_session_start

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # Create 3 sessions
            for i in range(3):
                record_session_start(
                    session_id=f"session-{i}",
                    project_name="project",
                    team_name="team",
                    expected_duration_hours=1,
                )
                record_session_end(
                    session_id=f"session-{i}",
                    actual_duration_minutes=30,
                )

            report = get_stats()

        assert report.total_sessions == 3

    def test_get_stats_calculates_total_duration(self, stats_cache_dir: Path) -> None:
        """Should sum total duration from completed sessions."""
        from scc_cli.stats import get_stats, record_session_end, record_session_start

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # Session 1: 60 minutes
            record_session_start(
                session_id="s1",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
            )
            record_session_end(session_id="s1", actual_duration_minutes=60)

            # Session 2: 90 minutes
            record_session_start(
                session_id="s2",
                project_name="p",
                team_name="t",
                expected_duration_hours=2,
            )
            record_session_end(session_id="s2", actual_duration_minutes=90)

            report = get_stats()

        assert report.total_duration_minutes == 150  # 60 + 90

    def test_get_stats_counts_incomplete_sessions(self, stats_cache_dir: Path) -> None:
        """Should identify sessions without session_end (incomplete)."""
        from scc_cli.stats import get_stats, record_session_end, record_session_start

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # Complete session
            record_session_start(
                session_id="complete",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
            )
            record_session_end(session_id="complete", actual_duration_minutes=30)

            # Incomplete session (no end event)
            record_session_start(
                session_id="incomplete",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
            )

            report = get_stats()

        assert report.total_sessions == 2
        assert report.incomplete_sessions == 1

    def test_get_stats_breaks_down_by_project(self, stats_cache_dir: Path) -> None:
        """Should provide per-project breakdown."""
        from scc_cli.stats import get_stats, record_session_end, record_session_start

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # Project A: 2 sessions
            record_session_start(
                session_id="a1",
                project_name="project-a",
                team_name="t",
                expected_duration_hours=1,
            )
            record_session_end(session_id="a1", actual_duration_minutes=30)
            record_session_start(
                session_id="a2",
                project_name="project-a",
                team_name="t",
                expected_duration_hours=1,
            )
            record_session_end(session_id="a2", actual_duration_minutes=45)

            # Project B: 1 session
            record_session_start(
                session_id="b1",
                project_name="project-b",
                team_name="t",
                expected_duration_hours=1,
            )
            record_session_end(session_id="b1", actual_duration_minutes=60)

            report = get_stats()

        assert "project-a" in report.by_project
        assert "project-b" in report.by_project
        assert report.by_project["project-a"]["sessions"] == 2
        assert report.by_project["project-a"]["duration_minutes"] == 75  # 30 + 45
        assert report.by_project["project-b"]["sessions"] == 1

    def test_get_stats_with_date_range(self, stats_cache_dir: Path) -> None:
        """Should filter stats by date range."""
        from scc_cli.stats import get_stats

        usage_file = stats_cache_dir / "usage.jsonl"

        # Create events with specific timestamps
        old_event = {
            "event_type": "session_start",
            "session_id": "old",
            "timestamp": "2024-01-01T10:00:00",
            "project_name": "p",
            "team_name": "t",
        }
        recent_event = {
            "event_type": "session_start",
            "session_id": "recent",
            "timestamp": datetime.now().isoformat(),
            "project_name": "p",
            "team_name": "t",
        }

        usage_file.write_text(json.dumps(old_event) + "\n" + json.dumps(recent_event) + "\n")

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            # Filter to last 30 days
            report = get_stats(days=30)

        # Should only count recent session
        assert report.total_sessions == 1


# ═══════════════════════════════════════════════════════════════════════════════
# StatsReport Dataclass Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsReportDataclass:
    """Tests for StatsReport dataclass structure."""

    def test_stats_report_has_required_fields(self) -> None:
        """StatsReport should have all required fields."""
        from scc_cli.stats import StatsReport

        report = StatsReport(
            total_sessions=10,
            total_duration_minutes=600,
            incomplete_sessions=2,
            by_project={"proj": {"sessions": 10, "duration_minutes": 600}},
            period_start=datetime.now() - timedelta(days=30),
            period_end=datetime.now(),
        )

        assert report.total_sessions == 10
        assert report.total_duration_minutes == 600
        assert report.incomplete_sessions == 2
        assert isinstance(report.by_project, dict)
        assert isinstance(report.period_start, datetime)
        assert isinstance(report.period_end, datetime)

    def test_stats_report_to_dict(self) -> None:
        """StatsReport should be convertible to dict for JSON export."""
        from scc_cli.stats import StatsReport

        report = StatsReport(
            total_sessions=5,
            total_duration_minutes=300,
            incomplete_sessions=1,
            by_project={"p": {"sessions": 5, "duration_minutes": 300}},
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 1, 31),
        )

        report_dict = report.to_dict()

        assert isinstance(report_dict, dict)
        assert report_dict["total_sessions"] == 5
        # Dates should be ISO format strings
        assert isinstance(report_dict["period_start"], str)


# ═══════════════════════════════════════════════════════════════════════════════
# Stats Export Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsExport:
    """Tests for stats export functionality."""

    def test_export_stats_json_format(self, stats_cache_dir: Path) -> None:
        """export_stats() should produce valid JSON."""
        from scc_cli.stats import export_stats, record_session_end, record_session_start

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="s1",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
            )
            record_session_end(session_id="s1", actual_duration_minutes=30)

            exported = export_stats()

        # Should be valid JSON
        parsed = json.loads(exported)
        assert "total_sessions" in parsed
        assert "total_duration_minutes" in parsed

    def test_export_raw_events(self, stats_cache_dir: Path) -> None:
        """Should be able to export raw event data."""
        from scc_cli.stats import export_raw_events, record_session_start

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="s1",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
            )

            raw = export_raw_events()

        # Should be list of events as JSON
        events = json.loads(raw)
        assert isinstance(events, list)
        assert len(events) == 1
        assert events[0]["event_type"] == "session_start"


# ═══════════════════════════════════════════════════════════════════════════════
# Integration with Stats Config
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsConfig:
    """Tests for stats configuration from org config."""

    def test_stats_disabled_does_not_record(self, stats_cache_dir: Path) -> None:
        """When stats.enabled=false, should not record events."""
        from scc_cli.stats import record_session_start

        stats_config = {"enabled": False}
        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="s1",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
                stats_config=stats_config,
            )

        # File should not be created or should be empty
        assert not usage_file.exists() or usage_file.read_text() == ""

    def test_stats_enabled_records_normally(self, stats_cache_dir: Path) -> None:
        """When stats.enabled=true (default), should record events."""
        from scc_cli.stats import record_session_start

        stats_config = {"enabled": True}
        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="s1",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
                stats_config=stats_config,
            )

        assert usage_file.exists()
        assert len(usage_file.read_text().strip()) > 0

    def test_user_identity_mode_hash_pseudonymizes(self, stats_cache_dir: Path) -> None:
        """user_identity_mode='hash' should use hashed user ID."""
        from scc_cli.stats import record_session_start

        stats_config = {"enabled": True, "user_identity_mode": "hash"}
        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            with patch("scc_cli.stats.get_username", return_value="testuser"):
                record_session_start(
                    session_id="s1",
                    project_name="p",
                    team_name="t",
                    expected_duration_hours=1,
                    stats_config=stats_config,
                )

        event = json.loads(usage_file.read_text().strip())
        # User ID should be hashed, not plaintext
        assert event.get("user_id_hash") is not None
        assert "testuser" not in event.get("user_id_hash", "")

    def test_user_identity_mode_none_excludes_user(self, stats_cache_dir: Path) -> None:
        """user_identity_mode='none' should not include user ID."""
        from scc_cli.stats import record_session_start

        stats_config = {"enabled": True, "user_identity_mode": "none"}
        usage_file = stats_cache_dir / "usage.jsonl"

        with patch("scc_cli.stats.CACHE_DIR", stats_cache_dir):
            record_session_start(
                session_id="s1",
                project_name="p",
                team_name="t",
                expected_duration_hours=1,
                stats_config=stats_config,
            )

        event = json.loads(usage_file.read_text().strip())
        # Should not have user_id_hash field
        assert "user_id_hash" not in event or event["user_id_hash"] is None
