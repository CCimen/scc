"""Tests for the exception store implementations (Phase 2.1).

TDD approach: Write tests first, implement to make them pass.

Tests cover:
- ExceptionStore protocol interface
- UserStore implementation (~/.config/scc/exceptions.json)
- RepoStore implementation (.scc/exceptions.json)
- Backup-on-corrupt with .bak-<timestamp>
- Pruning expired exceptions
- Forward compatibility warnings
"""

from __future__ import annotations

import json

from scc_cli.models.exceptions import (
    AllowTargets,
    Exception,
    ExceptionFile,
)

# ═══════════════════════════════════════════════════════════════════════════════
# UserStore Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestUserStore:
    """Tests for the UserStore implementation."""

    def test_read_empty_when_no_file(self, temp_config_dir):
        """read() returns empty ExceptionFile when file doesn't exist."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        ef = store.read()
        assert ef.schema_version == 1
        assert ef.exceptions == []

    def test_write_creates_file(self, temp_config_dir):
        """write() creates the exceptions file."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        ef = ExceptionFile(tool_version="2.1.0")
        store.write(ef)

        # File should exist
        path = temp_config_dir / "exceptions.json"
        assert path.exists()

        # Content should be valid JSON
        content = json.loads(path.read_text())
        assert content["schema_version"] == 1
        assert content["tool_version"] == "2.1.0"

    def test_write_then_read_roundtrip(self, temp_config_dir):
        """write() then read() preserves all data."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Testing roundtrip",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
            created_by="dev@example.com",
        )
        ef = ExceptionFile(
            schema_version=1,
            tool_version="2.1.0",
            exceptions=[exc],
        )
        store.write(ef)

        ef2 = store.read()
        assert ef2.schema_version == 1
        assert ef2.tool_version == "2.1.0"
        assert len(ef2.exceptions) == 1
        assert ef2.exceptions[0].id == "local-20251221-a3f2"
        assert ef2.exceptions[0].reason == "Testing roundtrip"

    def test_prune_expired_removes_old(self, temp_config_dir):
        """prune_expired() removes expired exceptions and returns count."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()

        # One expired, one active
        expired = Exception(
            id="expired-1",
            created_at="2025-01-01T10:00:00Z",
            expires_at="2025-01-01T18:00:00Z",  # Past
            reason="Expired",
            scope="local",
            allow=AllowTargets(),
        )
        active = Exception(
            id="active-1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",  # Far future
            reason="Active",
            scope="local",
            allow=AllowTargets(),
        )
        ef = ExceptionFile(exceptions=[expired, active])
        store.write(ef)

        count = store.prune_expired()
        assert count == 1

        # Only active remains
        ef2 = store.read()
        assert len(ef2.exceptions) == 1
        assert ef2.exceptions[0].id == "active-1"

    def test_prune_expired_returns_zero_when_none(self, temp_config_dir):
        """prune_expired() returns 0 when no expired exceptions."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        active = Exception(
            id="active-1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Active",
            scope="local",
            allow=AllowTargets(),
        )
        ef = ExceptionFile(exceptions=[active])
        store.write(ef)

        count = store.prune_expired()
        assert count == 0

    def test_backup_creates_backup_file(self, temp_config_dir):
        """backup() creates .bak-<timestamp> file."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        ef = ExceptionFile(tool_version="2.1.0")
        store.write(ef)

        backup_path = store.backup()
        assert backup_path is not None
        assert backup_path.exists()
        assert ".bak-" in backup_path.name
        # Verify backup name follows pattern: exceptions.json.bak-YYYYMMDDHHMMSS
        assert backup_path.name.startswith("exceptions.json.bak-")
        assert not backup_path.name.endswith(".json")  # No .json extension after timestamp

    def test_backup_returns_none_when_no_file(self, temp_config_dir):
        """backup() returns None when no file exists."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        backup_path = store.backup()
        assert backup_path is None

    def test_reset_removes_file(self, temp_config_dir):
        """reset() removes the exceptions file."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        ef = ExceptionFile(tool_version="2.1.0")
        store.write(ef)

        path = temp_config_dir / "exceptions.json"
        assert path.exists()

        store.reset()
        assert not path.exists()

    def test_reset_does_nothing_when_no_file(self, temp_config_dir):
        """reset() doesn't error when file doesn't exist."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        store.reset()  # Should not raise

    def test_path_property(self, temp_config_dir):
        """path property returns the correct path."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        assert store.path == temp_config_dir / "exceptions.json"


# ═══════════════════════════════════════════════════════════════════════════════
# RepoStore Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRepoStore:
    """Tests for the RepoStore implementation."""

    def test_read_empty_when_no_file(self, temp_dir):
        """read() returns empty ExceptionFile when file doesn't exist."""
        from scc_cli.stores.exception_store import RepoStore

        store = RepoStore(repo_root=temp_dir)
        ef = store.read()
        assert ef.schema_version == 1
        assert ef.exceptions == []

    def test_write_creates_directory_and_file(self, temp_dir):
        """write() creates .scc/ directory and exceptions file."""
        from scc_cli.stores.exception_store import RepoStore

        store = RepoStore(repo_root=temp_dir)
        ef = ExceptionFile(tool_version="2.1.0")
        store.write(ef)

        # Directory should exist
        scc_dir = temp_dir / ".scc"
        assert scc_dir.exists()

        # File should exist
        path = scc_dir / "exceptions.json"
        assert path.exists()

    def test_write_then_read_roundtrip(self, temp_dir):
        """write() then read() preserves all data."""
        from scc_cli.stores.exception_store import RepoStore

        store = RepoStore(repo_root=temp_dir)
        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Testing roundtrip",
            scope="local",
            allow=AllowTargets(plugins=["plugin-a"]),
        )
        ef = ExceptionFile(exceptions=[exc])
        store.write(ef)

        ef2 = store.read()
        assert len(ef2.exceptions) == 1
        assert ef2.exceptions[0].id == "local-20251221-a3f2"

    def test_path_property(self, temp_dir):
        """path property returns the correct path."""
        from scc_cli.stores.exception_store import RepoStore

        store = RepoStore(repo_root=temp_dir)
        assert store.path == temp_dir / ".scc" / "exceptions.json"

    def test_prune_expired_works(self, temp_dir):
        """prune_expired() removes expired exceptions."""
        from scc_cli.stores.exception_store import RepoStore

        store = RepoStore(repo_root=temp_dir)
        expired = Exception(
            id="expired-1",
            created_at="2025-01-01T10:00:00Z",
            expires_at="2025-01-01T18:00:00Z",
            reason="Expired",
            scope="local",
            allow=AllowTargets(),
        )
        ef = ExceptionFile(exceptions=[expired])
        store.write(ef)

        count = store.prune_expired()
        assert count == 1

        ef2 = store.read()
        assert len(ef2.exceptions) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Corrupt File Recovery Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCorruptFileRecovery:
    """Tests for corrupt file recovery with backup."""

    def test_read_corrupt_file_creates_backup(self, temp_config_dir, capsys):
        """read() on corrupt JSON backs up file and returns empty."""
        from scc_cli.stores.exception_store import UserStore

        # Create corrupt file
        path = temp_config_dir / "exceptions.json"
        path.write_text("{ invalid json }")

        store = UserStore()
        ef = store.read()

        # Should return empty ExceptionFile
        assert ef.schema_version == 1
        assert ef.exceptions == []

        # Should have created backup
        backups = list(temp_config_dir.glob("exceptions.json.bak-*"))
        assert len(backups) == 1

        # Should print warning
        captured = capsys.readouterr()
        assert "corrupted" in captured.err.lower() or "backed up" in captured.err.lower()

    def test_read_corrupt_backup_contains_original(self, temp_config_dir):
        """Backup file contains the original corrupt content."""
        from scc_cli.stores.exception_store import UserStore

        # Create corrupt file
        path = temp_config_dir / "exceptions.json"
        corrupt_content = "{ invalid json }"
        path.write_text(corrupt_content)

        store = UserStore()
        store.read()  # Triggers backup

        # Backup should contain original content
        backups = list(temp_config_dir.glob("exceptions.json.bak-*"))
        assert backups[0].read_text() == corrupt_content


# ═══════════════════════════════════════════════════════════════════════════════
# Forward Compatibility Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestForwardCompatibility:
    """Tests for schema version handling and forward compatibility."""

    def test_read_newer_schema_version_warns_local(self, temp_config_dir, capsys):
        """Reading newer schema_version from local store warns and ignores."""
        from scc_cli.stores.exception_store import UserStore

        # Create file with newer schema
        path = temp_config_dir / "exceptions.json"
        content = {
            "schema_version": 2,  # Newer than current
            "exceptions": [
                {
                    "id": "future-1",
                    "created_at": "2025-12-21T10:00:00Z",
                    "expires_at": "2099-12-31T23:59:59Z",
                    "reason": "Future exception",
                    "scope": "local",
                    "allow": {},
                }
            ],
        }
        path.write_text(json.dumps(content))

        store = UserStore()
        ef = store.read()

        # For local stores: warn + ignore file (fail-open)
        # Returns empty, continues working
        assert ef.schema_version == 1
        assert ef.exceptions == []

        # Should print warning about upgrade
        captured = capsys.readouterr()
        assert "newer" in captured.err.lower() or "upgrade" in captured.err.lower()

    def test_read_preserves_extra_fields(self, temp_config_dir):
        """Reading file with unknown fields preserves them in _extra."""
        from scc_cli.stores.exception_store import UserStore

        # Create file with extra fields
        path = temp_config_dir / "exceptions.json"
        content = {
            "schema_version": 1,
            "future_flag": True,  # Unknown field
            "exceptions": [
                {
                    "id": "test-1",
                    "created_at": "2025-12-21T10:00:00Z",
                    "expires_at": "2099-12-31T23:59:59Z",
                    "reason": "Test",
                    "scope": "local",
                    "allow": {},
                    "future_exception_field": "preserved",  # Unknown field
                }
            ],
        }
        path.write_text(json.dumps(content))

        store = UserStore()
        ef = store.read()

        # File-level extra preserved
        assert ef._extra.get("future_flag") is True

        # Exception-level extra preserved
        assert ef.exceptions[0]._extra.get("future_exception_field") == "preserved"

    def test_write_preserves_extra_fields_roundtrip(self, temp_config_dir):
        """Writing and reading preserves _extra fields."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()
        exc = Exception(
            id="test-1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Test",
            scope="local",
            allow=AllowTargets(),
            _extra={"future_field": "value"},
        )
        ef = ExceptionFile(
            exceptions=[exc],
            _extra={"file_future": True},
        )
        store.write(ef)

        ef2 = store.read()
        assert ef2._extra.get("file_future") is True
        assert ef2.exceptions[0]._extra.get("future_field") == "value"


# ═══════════════════════════════════════════════════════════════════════════════
# Store Interface Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStoreInterface:
    """Tests that both stores implement the same interface."""

    def test_user_store_has_required_methods(self, temp_config_dir):
        """UserStore has all required protocol methods."""
        from scc_cli.stores.exception_store import UserStore

        store = UserStore()

        # All required methods exist
        assert callable(store.read)
        assert callable(store.write)
        assert callable(store.prune_expired)
        assert callable(store.backup)
        assert callable(store.reset)
        assert hasattr(store, "path")

    def test_repo_store_has_required_methods(self, temp_dir):
        """RepoStore has all required protocol methods."""
        from scc_cli.stores.exception_store import RepoStore

        store = RepoStore(repo_root=temp_dir)

        # All required methods exist
        assert callable(store.read)
        assert callable(store.write)
        assert callable(store.prune_expired)
        assert callable(store.backup)
        assert callable(store.reset)
        assert hasattr(store, "path")
