"""Tests for sessions.py session management module.

These tests verify:
- get_most_recent() returns most recent session
- list_recent() sorting and limiting
- Session recording and retrieval
- Session pruning and cleanup
"""

import json
from datetime import datetime, timedelta

import pytest

from scc_cli import sessions

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sessions_file(tmp_path, monkeypatch):
    """Create a temporary sessions file."""

    # Point to temp directory
    sessions_path = tmp_path / "sessions.json"
    monkeypatch.setattr("scc_cli.sessions.config.SESSIONS_FILE", sessions_path)
    return sessions_path


@pytest.fixture
def sample_sessions():
    """Generate sample session data."""
    now = datetime.now()
    return [
        {
            "workspace": "/tmp/proj1",
            "team": "platform",
            "name": "session1",
            "container_name": "scc-proj1-abc123",
            "branch": "main",
            "last_used": (now - timedelta(hours=1)).isoformat(),
            "created_at": (now - timedelta(days=1)).isoformat(),
        },
        {
            "workspace": "/tmp/proj2",
            "team": "api",
            "name": "session2",
            "container_name": "scc-proj2-def456",
            "branch": "develop",
            "last_used": now.isoformat(),  # Most recent
            "created_at": (now - timedelta(hours=2)).isoformat(),
        },
        {
            "workspace": "/tmp/proj3",
            "team": None,
            "name": "session3",
            "container_name": None,
            "branch": None,
            "last_used": (now - timedelta(days=2)).isoformat(),
            "created_at": (now - timedelta(days=3)).isoformat(),
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_most_recent
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetMostRecent:
    """Tests for get_most_recent() function."""

    def test_returns_most_recent_session(self, sessions_file, sample_sessions):
        """Should return session with most recent last_used timestamp."""
        # Write sample sessions
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.get_most_recent()

        assert result is not None
        # session2 has the most recent last_used
        assert result["workspace"] == "/tmp/proj2"
        assert result["name"] == "session2"

    def test_returns_none_when_no_sessions(self, sessions_file):
        """Should return None when no sessions exist."""
        sessions_file.write_text(json.dumps({"sessions": []}))

        result = sessions.get_most_recent()

        assert result is None

    def test_returns_none_when_file_missing(self, sessions_file):
        """Should return None when sessions file doesn't exist."""
        # Don't create the file
        result = sessions.get_most_recent()

        assert result is None

    def test_handles_single_session(self, sessions_file):
        """Should return the only session when just one exists."""
        single_session = [
            {
                "workspace": "/tmp/only-one",
                "team": "dev",
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": single_session}))

        result = sessions.get_most_recent()

        assert result is not None
        assert result["workspace"] == "/tmp/only-one"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list_recent
# ═══════════════════════════════════════════════════════════════════════════════


class TestListRecent:
    """Tests for list_recent() function."""

    def test_returns_sessions_sorted_by_last_used(self, sessions_file, sample_sessions):
        """Should return sessions sorted by last_used descending."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.list_recent(limit=10)

        assert len(result) == 3
        # Most recent first (session2)
        assert result[0]["workspace"] == "/tmp/proj2"
        assert result[1]["workspace"] == "/tmp/proj1"
        assert result[2]["workspace"] == "/tmp/proj3"

    def test_respects_limit(self, sessions_file, sample_sessions):
        """Should limit number of returned sessions."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.list_recent(limit=2)

        assert len(result) == 2

    def test_returns_empty_list_when_no_sessions(self, sessions_file):
        """Should return empty list when no sessions exist."""
        sessions_file.write_text(json.dumps({"sessions": []}))

        result = sessions.list_recent()

        assert result == []

    def test_formats_relative_time(self, sessions_file):
        """Should format last_used as relative time."""
        now = datetime.now()
        recent_session = [
            {
                "workspace": "/tmp/test",
                "last_used": (now - timedelta(minutes=5)).isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": recent_session}))

        result = sessions.list_recent()

        assert len(result) == 1
        assert "m ago" in result[0]["last_used"]

    def test_generates_name_from_workspace_if_missing(self, sessions_file):
        """Should generate name from workspace path if name is None."""
        session_without_name = [
            {
                "workspace": "/home/user/projects/my-project",
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": session_without_name}))

        result = sessions.list_recent()

        assert result[0]["name"] == "my-project"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for record_session
# ═══════════════════════════════════════════════════════════════════════════════


class TestRecordSession:
    """Tests for record_session() function."""

    def test_creates_new_session(self, sessions_file):
        """Should create new session record."""
        sessions_file.write_text(json.dumps({"sessions": []}))

        result = sessions.record_session(
            workspace="/tmp/new-project",
            team="dev",
            session_name="my-session",
        )

        assert result.workspace == "/tmp/new-project"
        assert result.team == "dev"
        assert result.name == "my-session"

        # Verify saved
        saved = json.loads(sessions_file.read_text())
        assert len(saved["sessions"]) == 1

    def test_updates_existing_session(self, sessions_file):
        """Should update existing session with same workspace+branch."""
        initial = [
            {
                "workspace": "/tmp/proj",
                "branch": "main",
                "team": "old-team",
                "last_used": "2024-01-01T00:00:00",
                "created_at": "2024-01-01T00:00:00",
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": initial}))

        result = sessions.record_session(
            workspace="/tmp/proj",
            team="new-team",
            branch="main",
        )

        assert result.team == "new-team"

        # Should still be just one session
        saved = json.loads(sessions_file.read_text())
        assert len(saved["sessions"]) == 1
        # But created_at preserved
        assert saved["sessions"][0]["created_at"] == "2024-01-01T00:00:00"

    def test_creates_new_session_for_different_branch(self, sessions_file):
        """Should create new session if branch differs."""
        initial = [
            {
                "workspace": "/tmp/proj",
                "branch": "main",
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": initial}))

        sessions.record_session(
            workspace="/tmp/proj",
            branch="feature",  # Different branch
        )

        saved = json.loads(sessions_file.read_text())
        assert len(saved["sessions"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for find_session_by_workspace
# ═══════════════════════════════════════════════════════════════════════════════


class TestFindSessionByWorkspace:
    """Tests for find_session_by_workspace() function."""

    def test_finds_session_by_workspace(self, sessions_file, sample_sessions):
        """Should find session by workspace path."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.find_session_by_workspace("/tmp/proj1")

        assert result is not None
        assert result["workspace"] == "/tmp/proj1"

    def test_returns_none_when_not_found(self, sessions_file, sample_sessions):
        """Should return None when workspace not found."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.find_session_by_workspace("/tmp/nonexistent")

        assert result is None

    def test_filters_by_branch(self, sessions_file, sample_sessions):
        """Should filter by branch when provided."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.find_session_by_workspace("/tmp/proj2", branch="develop")

        assert result is not None
        assert result["branch"] == "develop"

    def test_returns_none_when_branch_mismatch(self, sessions_file, sample_sessions):
        """Should return None when branch doesn't match."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.find_session_by_workspace("/tmp/proj1", branch="feature")

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for prune_orphaned_sessions
# ═══════════════════════════════════════════════════════════════════════════════


class TestPruneOrphanedSessions:
    """Tests for prune_orphaned_sessions() function."""

    def test_removes_sessions_with_missing_workspaces(self, sessions_file, tmp_path):
        """Should remove sessions whose workspaces don't exist."""
        # Create one real directory
        real_dir = tmp_path / "real-project"
        real_dir.mkdir()

        test_sessions = [
            {"workspace": str(real_dir), "last_used": datetime.now().isoformat()},
            {"workspace": "/nonexistent/path", "last_used": datetime.now().isoformat()},
        ]
        sessions_file.write_text(json.dumps({"sessions": test_sessions}))

        pruned_count = sessions.prune_orphaned_sessions()

        assert pruned_count == 1
        saved = json.loads(sessions_file.read_text())
        assert len(saved["sessions"]) == 1
        assert saved["sessions"][0]["workspace"] == str(real_dir)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for format_relative_time
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatRelativeTime:
    """Tests for format_relative_time() function."""

    def test_just_now(self):
        """Should return 'just now' for recent times."""
        now = datetime.now()
        result = sessions.format_relative_time(now)
        assert result == "just now"

    def test_minutes_ago(self):
        """Should format as minutes."""
        past = datetime.now() - timedelta(minutes=5)
        result = sessions.format_relative_time(past)
        assert result == "5m ago"

    def test_hours_ago(self):
        """Should format as hours."""
        past = datetime.now() - timedelta(hours=3)
        result = sessions.format_relative_time(past)
        assert result == "3h ago"

    def test_days_ago(self):
        """Should format as days."""
        past = datetime.now() - timedelta(days=2)
        result = sessions.format_relative_time(past)
        assert result == "2d ago"

    def test_weeks_ago(self):
        """Should format as weeks."""
        past = datetime.now() - timedelta(weeks=3)
        result = sessions.format_relative_time(past)
        assert result == "3w ago"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for clear_history
# ═══════════════════════════════════════════════════════════════════════════════


class TestClearHistory:
    """Tests for clear_history() function."""

    def test_clears_all_sessions(self, sessions_file, sample_sessions):
        """Should remove all sessions and return count."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        count = sessions.clear_history()

        assert count == 3
        saved = json.loads(sessions_file.read_text())
        assert saved["sessions"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for remove_session
# ═══════════════════════════════════════════════════════════════════════════════


class TestRemoveSession:
    """Tests for remove_session() function."""

    def test_removes_session_by_workspace(self, sessions_file, sample_sessions):
        """Should remove session matching workspace."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.remove_session("/tmp/proj1")

        assert result is True
        saved = json.loads(sessions_file.read_text())
        assert len(saved["sessions"]) == 2
        workspaces = [s["workspace"] for s in saved["sessions"]]
        assert "/tmp/proj1" not in workspaces

    def test_returns_false_when_not_found(self, sessions_file, sample_sessions):
        """Should return False when session not found."""
        sessions_file.write_text(json.dumps({"sessions": sample_sessions}))

        result = sessions.remove_session("/tmp/nonexistent")

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Legacy Migration (Phase 1.2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLegacyMigration:
    """Tests for legacy session migration during load."""

    def test_migrates_base_team_to_none(self, sessions_file):
        """Sessions with team='base' should be migrated to team=None (standalone)."""
        legacy_sessions = [
            {
                "workspace": "/tmp/legacy-project",
                "team": "base",  # Old hardcoded fallback
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": legacy_sessions}))

        result = sessions.get_most_recent()

        assert result is not None
        assert result["team"] is None  # Migrated from "base"

    def test_preserves_valid_team_names(self, sessions_file):
        """Sessions with actual team names should not be modified."""
        valid_sessions = [
            {
                "workspace": "/tmp/project",
                "team": "platform",
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": valid_sessions}))

        result = sessions.get_most_recent()

        assert result is not None
        assert result["team"] == "platform"

    def test_preserves_none_team(self, sessions_file):
        """Sessions with team=None should remain None."""
        none_team_sessions = [
            {
                "workspace": "/tmp/standalone-project",
                "team": None,
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": none_team_sessions}))

        result = sessions.get_most_recent()

        assert result is not None
        assert result["team"] is None

    def test_migration_does_not_persist_without_save(self, sessions_file):
        """Migration happens in memory; original file unchanged until save."""
        legacy_sessions = [
            {
                "workspace": "/tmp/legacy",
                "team": "base",
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": legacy_sessions}))

        # Just load, don't save
        sessions.get_most_recent()

        # File should still have "base"
        raw = json.loads(sessions_file.read_text())
        assert raw["sessions"][0]["team"] == "base"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for schema_version (Phase 1.3)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaVersion:
    """Tests for schema_version field in SessionRecord."""

    def test_new_session_has_schema_version(self, sessions_file):
        """New sessions should have schema_version=1."""
        sessions_file.write_text(json.dumps({"sessions": []}))

        record = sessions.record_session(
            workspace="/tmp/new-project",
            team="dev",
        )

        assert record.schema_version == 1

        # Verify saved
        saved = json.loads(sessions_file.read_text())
        assert saved["sessions"][0].get("schema_version") == 1

    def test_legacy_session_without_schema_version_defaults_to_1(self, sessions_file):
        """Sessions without schema_version should default to 1 when loaded."""
        legacy_session = [
            {
                "workspace": "/tmp/old-project",
                "team": "platform",
                "last_used": datetime.now().isoformat(),
                # No schema_version field
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": legacy_session}))

        # Load via SessionRecord.from_dict
        raw = sessions._load_sessions()[0]
        record = sessions.SessionRecord.from_dict(raw)

        assert record.schema_version == 1

    def test_schema_version_preserved_on_update(self, sessions_file):
        """schema_version should be preserved when updating existing session."""
        initial = [
            {
                "workspace": "/tmp/proj",
                "branch": "main",
                "schema_version": 1,
                "last_used": "2024-01-01T00:00:00",
                "created_at": "2024-01-01T00:00:00",
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": initial}))

        sessions.record_session(
            workspace="/tmp/proj",
            team="new-team",
            branch="main",
        )

        saved = json.loads(sessions_file.read_text())
        assert saved["sessions"][0].get("schema_version") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Standalone Mode (team=None round-trip)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStandaloneMode:
    """Tests for standalone mode (team=None) sessions."""

    def test_standalone_session_round_trips(self, sessions_file):
        """Session with team=None should save and load correctly."""
        sessions_file.write_text(json.dumps({"sessions": []}))

        # Record standalone session
        record = sessions.record_session(
            workspace="/tmp/standalone",
            team=None,  # Explicit standalone
            session_name="test",
        )

        assert record.team is None

        # Load it back
        result = sessions.find_session_by_workspace("/tmp/standalone")

        assert result is not None
        # to_dict() excludes None values, so team key may not exist
        assert result.get("team") is None

    def test_list_recent_includes_standalone_sessions(self, sessions_file):
        """list_recent should include standalone (team=None) sessions."""
        test_sessions = [
            {
                "workspace": "/tmp/standalone",
                "team": None,
                "last_used": datetime.now().isoformat(),
            }
        ]
        sessions_file.write_text(json.dumps({"sessions": test_sessions}))

        result = sessions.list_recent()

        assert len(result) == 1
        assert result[0]["team"] is None
