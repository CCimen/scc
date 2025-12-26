"""
Tests for managed state tracking (TDD Red Phase).

This module tests the ManagedState dataclass and load/save operations
that track what SCC has added to settings.local.json.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class TestManagedStateDataclass:
    """Tests for ManagedState data structure."""

    def test_create_empty_state(self) -> None:
        """Should create state with empty lists."""
        from scc_cli.marketplace.managed import ManagedState

        state = ManagedState()
        assert state.managed_plugins == []
        assert state.managed_marketplaces == []
        assert state.last_sync is None
        assert state.org_config_url is None

    def test_create_with_plugins(self) -> None:
        """Should create state with plugins list."""
        from scc_cli.marketplace.managed import ManagedState

        state = ManagedState(managed_plugins=["plugin-a@marketplace-1", "plugin-b@marketplace-1"])
        assert state.managed_plugins == ["plugin-a@marketplace-1", "plugin-b@marketplace-1"]
        assert state.managed_marketplaces == []

    def test_create_with_marketplaces(self) -> None:
        """Should create state with marketplaces list."""
        from scc_cli.marketplace.managed import ManagedState

        state = ManagedState(
            managed_marketplaces=[
                ".claude/.scc-marketplaces/internal",
                ".claude/.scc-marketplaces/security",
            ]
        )
        assert len(state.managed_marketplaces) == 2

    def test_create_with_full_metadata(self) -> None:
        """Should create state with all metadata fields."""
        from scc_cli.marketplace.managed import ManagedState

        sync_time = datetime.now(UTC)
        state = ManagedState(
            managed_plugins=["test@mp"],
            managed_marketplaces=[".claude/.scc-marketplaces/test"],
            last_sync=sync_time,
            org_config_url="https://example.com/org-config.json",
            team_id="backend",
        )
        assert state.last_sync == sync_time
        assert state.org_config_url == "https://example.com/org-config.json"
        assert state.team_id == "backend"

    def test_to_dict(self) -> None:
        """Should serialize to dictionary."""
        from scc_cli.marketplace.managed import ManagedState

        sync_time = datetime.now(UTC)
        state = ManagedState(
            managed_plugins=["p1@m1", "p2@m1"],
            managed_marketplaces=[".claude/.scc-marketplaces/m1"],
            last_sync=sync_time,
            org_config_url="https://example.com/config.json",
            team_id="frontend",
        )

        data = state.to_dict()
        assert data["managed_plugins"] == ["p1@m1", "p2@m1"]
        assert data["managed_marketplaces"] == [".claude/.scc-marketplaces/m1"]
        assert "last_sync" in data
        assert data["org_config_url"] == "https://example.com/config.json"
        assert data["team_id"] == "frontend"

    def test_from_dict_empty(self) -> None:
        """Should deserialize from empty dictionary."""
        from scc_cli.marketplace.managed import ManagedState

        state = ManagedState.from_dict({})
        assert state.managed_plugins == []
        assert state.managed_marketplaces == []
        assert state.last_sync is None

    def test_from_dict_full(self) -> None:
        """Should deserialize from full dictionary."""
        from scc_cli.marketplace.managed import ManagedState

        data = {
            "managed_plugins": ["a@m", "b@m"],
            "managed_marketplaces": [".path/1", ".path/2"],
            "last_sync": "2025-01-15T10:30:00+00:00",
            "org_config_url": "https://example.com/config.json",
            "team_id": "devops",
        }

        state = ManagedState.from_dict(data)
        assert state.managed_plugins == ["a@m", "b@m"]
        assert state.managed_marketplaces == [".path/1", ".path/2"]
        assert state.last_sync is not None
        assert state.org_config_url == "https://example.com/config.json"
        assert state.team_id == "devops"


class TestLoadManagedState:
    """Tests for loading managed state from disk."""

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Should return empty state if file doesn't exist."""
        from scc_cli.marketplace.managed import load_managed_state

        state = load_managed_state(tmp_path)
        assert state.managed_plugins == []
        assert state.managed_marketplaces == []

    def test_load_empty_file(self, tmp_path: Path) -> None:
        """Should return empty state if file is empty JSON object."""
        from scc_cli.marketplace.managed import load_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".scc-managed.json").write_text("{}")

        state = load_managed_state(tmp_path)
        assert state.managed_plugins == []
        assert state.managed_marketplaces == []

    def test_load_with_plugins(self, tmp_path: Path) -> None:
        """Should load plugins list from file."""
        from scc_cli.marketplace.managed import load_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".scc-managed.json").write_text(
            json.dumps({"managed_plugins": ["plugin-a@mp", "plugin-b@mp"]})
        )

        state = load_managed_state(tmp_path)
        assert state.managed_plugins == ["plugin-a@mp", "plugin-b@mp"]

    def test_load_with_marketplaces(self, tmp_path: Path) -> None:
        """Should load marketplaces list from file."""
        from scc_cli.marketplace.managed import load_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".scc-managed.json").write_text(
            json.dumps({"managed_marketplaces": [".claude/.scc-marketplaces/internal"]})
        )

        state = load_managed_state(tmp_path)
        assert state.managed_marketplaces == [".claude/.scc-marketplaces/internal"]

    def test_load_full_state(self, tmp_path: Path) -> None:
        """Should load complete state with metadata."""
        from scc_cli.marketplace.managed import load_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".scc-managed.json").write_text(
            json.dumps(
                {
                    "managed_plugins": ["p1@m", "p2@m"],
                    "managed_marketplaces": [".path/m"],
                    "last_sync": "2025-01-15T10:30:00+00:00",
                    "org_config_url": "https://example.com/config.json",
                    "team_id": "backend",
                }
            )
        )

        state = load_managed_state(tmp_path)
        assert len(state.managed_plugins) == 2
        assert state.team_id == "backend"

    def test_load_corrupted_json(self, tmp_path: Path) -> None:
        """Should return empty state if JSON is corrupted."""
        from scc_cli.marketplace.managed import load_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".scc-managed.json").write_text("not valid json")

        state = load_managed_state(tmp_path)
        assert state.managed_plugins == []
        assert state.managed_marketplaces == []


class TestSaveManagedState:
    """Tests for saving managed state to disk."""

    def test_save_empty_state(self, tmp_path: Path) -> None:
        """Should save empty state to file."""
        from scc_cli.marketplace.managed import ManagedState, save_managed_state

        state = ManagedState()
        save_managed_state(tmp_path, state)

        managed_path = tmp_path / ".claude" / ".scc-managed.json"
        assert managed_path.exists()

        data = json.loads(managed_path.read_text())
        assert data["managed_plugins"] == []
        assert data["managed_marketplaces"] == []

    def test_save_creates_claude_dir(self, tmp_path: Path) -> None:
        """Should create .claude directory if it doesn't exist."""
        from scc_cli.marketplace.managed import ManagedState, save_managed_state

        state = ManagedState(managed_plugins=["test@mp"])
        save_managed_state(tmp_path, state)

        claude_dir = tmp_path / ".claude"
        assert claude_dir.exists()
        assert claude_dir.is_dir()

    def test_save_with_plugins(self, tmp_path: Path) -> None:
        """Should save plugins list to file."""
        from scc_cli.marketplace.managed import ManagedState, save_managed_state

        state = ManagedState(managed_plugins=["plugin-a@mp-1", "plugin-b@mp-2"])
        save_managed_state(tmp_path, state)

        managed_path = tmp_path / ".claude" / ".scc-managed.json"
        data = json.loads(managed_path.read_text())
        assert data["managed_plugins"] == ["plugin-a@mp-1", "plugin-b@mp-2"]

    def test_save_with_marketplaces(self, tmp_path: Path) -> None:
        """Should save marketplaces list to file."""
        from scc_cli.marketplace.managed import ManagedState, save_managed_state

        state = ManagedState(
            managed_marketplaces=[
                ".claude/.scc-marketplaces/internal",
                ".claude/.scc-marketplaces/security",
            ]
        )
        save_managed_state(tmp_path, state)

        managed_path = tmp_path / ".claude" / ".scc-managed.json"
        data = json.loads(managed_path.read_text())
        assert len(data["managed_marketplaces"]) == 2

    def test_save_overwrites_existing(self, tmp_path: Path) -> None:
        """Should overwrite existing file."""
        from scc_cli.marketplace.managed import ManagedState, save_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".scc-managed.json").write_text(json.dumps({"managed_plugins": ["old@mp"]}))

        state = ManagedState(managed_plugins=["new@mp"])
        save_managed_state(tmp_path, state)

        data = json.loads((claude_dir / ".scc-managed.json").read_text())
        assert data["managed_plugins"] == ["new@mp"]

    def test_save_full_metadata(self, tmp_path: Path) -> None:
        """Should save complete state with all metadata."""
        from scc_cli.marketplace.managed import ManagedState, save_managed_state

        sync_time = datetime.now(UTC)
        state = ManagedState(
            managed_plugins=["p1@m", "p2@m"],
            managed_marketplaces=[".path/m"],
            last_sync=sync_time,
            org_config_url="https://example.com/config.json",
            team_id="backend",
        )
        save_managed_state(tmp_path, state)

        managed_path = tmp_path / ".claude" / ".scc-managed.json"
        data = json.loads(managed_path.read_text())
        assert data["org_config_url"] == "https://example.com/config.json"
        assert data["team_id"] == "backend"
        assert "last_sync" in data


class TestRoundTrip:
    """Tests for load/save roundtrip."""

    def test_roundtrip_empty(self, tmp_path: Path) -> None:
        """Should preserve empty state through roundtrip."""
        from scc_cli.marketplace.managed import (
            ManagedState,
            load_managed_state,
            save_managed_state,
        )

        original = ManagedState()
        save_managed_state(tmp_path, original)
        loaded = load_managed_state(tmp_path)

        assert loaded.managed_plugins == original.managed_plugins
        assert loaded.managed_marketplaces == original.managed_marketplaces

    def test_roundtrip_full(self, tmp_path: Path) -> None:
        """Should preserve full state through roundtrip."""
        from scc_cli.marketplace.managed import (
            ManagedState,
            load_managed_state,
            save_managed_state,
        )

        sync_time = datetime.now(UTC)
        original = ManagedState(
            managed_plugins=["p1@m1", "p2@m2"],
            managed_marketplaces=[".path/m1", ".path/m2"],
            last_sync=sync_time,
            org_config_url="https://example.com/org.json",
            team_id="devops",
        )

        save_managed_state(tmp_path, original)
        loaded = load_managed_state(tmp_path)

        assert loaded.managed_plugins == original.managed_plugins
        assert loaded.managed_marketplaces == original.managed_marketplaces
        assert loaded.org_config_url == original.org_config_url
        assert loaded.team_id == original.team_id
        # DateTime comparison - within 1 second tolerance
        assert loaded.last_sync is not None
        assert original.last_sync is not None
        assert abs((loaded.last_sync - original.last_sync).total_seconds()) < 1


class TestClearManagedState:
    """Tests for clearing managed state."""

    def test_clear_existing_state(self, tmp_path: Path) -> None:
        """Should remove managed state file."""
        from scc_cli.marketplace.managed import clear_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        managed_path = claude_dir / ".scc-managed.json"
        managed_path.write_text(json.dumps({"managed_plugins": ["test@mp"]}))

        assert managed_path.exists()
        clear_managed_state(tmp_path)
        assert not managed_path.exists()

    def test_clear_nonexistent_state(self, tmp_path: Path) -> None:
        """Should not error if file doesn't exist."""
        from scc_cli.marketplace.managed import clear_managed_state

        # Should not raise
        clear_managed_state(tmp_path)

    def test_clear_preserves_claude_dir(self, tmp_path: Path) -> None:
        """Should preserve .claude directory when clearing."""
        from scc_cli.marketplace.managed import clear_managed_state

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / ".scc-managed.json").write_text("{}")
        (claude_dir / "settings.local.json").write_text("{}")

        clear_managed_state(tmp_path)

        assert claude_dir.exists()
        assert (claude_dir / "settings.local.json").exists()
