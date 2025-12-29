"""Tests for work context tracking (contexts.py)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from scc_cli.contexts import (
    MAX_CONTEXTS,
    WorkContext,
    clear_contexts,
    get_context_for_path,
    load_recent_contexts,
    record_context,
    toggle_pin,
)

# ─────────────────────────────────────────────────────────────────────────────
# WorkContext dataclass tests
# ─────────────────────────────────────────────────────────────────────────────


class TestWorkContext:
    """Tests for WorkContext dataclass."""

    def test_create_basic_context(self) -> None:
        """Create a context with required fields."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api-service"),
            worktree_path=Path("/code/api-service"),
            worktree_name="main",
        )
        assert ctx.team == "platform"
        assert ctx.repo_root == Path("/code/api-service")
        assert ctx.worktree_path == Path("/code/api-service")
        assert ctx.worktree_name == "main"
        assert ctx.last_session_id is None
        assert ctx.pinned is False

    def test_repo_name_property(self) -> None:
        """Repo name is extracted from path."""
        ctx = WorkContext(
            team="data",
            repo_root=Path("/home/user/projects/ml-pipeline"),
            worktree_path=Path("/home/user/projects/ml-pipeline"),
            worktree_name="main",
        )
        assert ctx.repo_name == "ml-pipeline"

    def test_display_label_property(self) -> None:
        """Display label shows team · repo · worktree."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api-service"),
            worktree_path=Path("/code/api-service-feature"),
            worktree_name="feature-auth",
        )
        assert ctx.display_label == "platform · api-service · feature-auth"

    def test_team_label_returns_team_name(self) -> None:
        """team_label returns team name when set."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        assert ctx.team_label == "platform"

    def test_team_label_returns_standalone_when_none(self) -> None:
        """team_label returns 'standalone' when team is None."""
        ctx = WorkContext(
            team=None,
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        assert ctx.team_label == "standalone"

    def test_display_label_standalone_mode(self) -> None:
        """Display label shows 'standalone' for team=None."""
        ctx = WorkContext(
            team=None,
            repo_root=Path("/home/user/my-project"),
            worktree_path=Path("/home/user/my-project"),
            worktree_name="main",
        )
        assert ctx.display_label == "standalone · my-project · main"

    def test_unique_key_property(self) -> None:
        """Unique key is (team, repo_root, worktree_path)."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api-feature"),
            worktree_name="feature",
        )
        assert ctx.unique_key == ("platform", Path("/code/api"), Path("/code/api-feature"))

    def test_to_dict_and_from_dict_roundtrip(self) -> None:
        """Context serializes and deserializes correctly."""
        original = WorkContext(
            team="data",
            repo_root=Path("/code/ml"),
            worktree_path=Path("/code/ml"),
            worktree_name="main",
            last_session_id="sess-123",
            last_used="2024-01-15T10:30:00+00:00",
            pinned=True,
        )
        data = original.to_dict()
        restored = WorkContext.from_dict(data)

        assert restored.team == original.team
        # Paths are normalized on from_dict, so compare resolved
        assert restored.repo_root.name == original.repo_root.name
        assert restored.worktree_name == original.worktree_name
        assert restored.last_session_id == original.last_session_id
        assert restored.last_used == original.last_used
        assert restored.pinned == original.pinned

    def test_from_dict_handles_missing_optional_fields(self) -> None:
        """Missing optional fields get defaults."""
        data = {
            "team": "web",
            "repo_root": "/code/frontend",
            "worktree_path": "/code/frontend",
            "worktree_name": "main",
        }
        ctx = WorkContext.from_dict(data)
        assert ctx.last_session_id is None
        assert ctx.pinned is False
        # last_used should have a default

    def test_standalone_context_serialization_roundtrip(self) -> None:
        """Standalone context (team=None) serializes and deserializes correctly."""
        original = WorkContext(
            team=None,
            repo_root=Path("/code/personal-project"),
            worktree_path=Path("/code/personal-project"),
            worktree_name="main",
            last_session_id="sess-standalone",
        )
        data = original.to_dict()
        assert data["team"] is None  # Explicitly None in JSON

        restored = WorkContext.from_dict(data)
        assert restored.team is None
        assert restored.team_label == "standalone"
        assert restored.display_label == "standalone · personal-project · main"


# ─────────────────────────────────────────────────────────────────────────────
# Storage and retrieval tests
# ─────────────────────────────────────────────────────────────────────────────


class TestContextStorage:
    """Tests for context persistence."""

    @pytest.fixture(autouse=True)
    def use_temp_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Use a temporary directory for cache."""
        cache_dir = tmp_path / "cache" / "scc"
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
        # Clear any existing state
        if cache_dir.exists():
            for f in cache_dir.iterdir():
                f.unlink()

    def test_load_returns_empty_when_no_file(self) -> None:
        """Load returns empty list when no contexts file exists."""
        contexts = load_recent_contexts()
        assert contexts == []

    def test_record_creates_new_context(self) -> None:
        """Recording a new context adds it to storage."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        record_context(ctx)

        loaded = load_recent_contexts()
        assert len(loaded) == 1
        assert loaded[0].team == "platform"

    def test_record_updates_existing_context(self) -> None:
        """Recording same context updates last_used and session."""
        ctx1 = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            last_session_id="sess-001",
        )
        record_context(ctx1)

        # Record same context with new session
        ctx2 = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            last_session_id="sess-002",
        )
        record_context(ctx2)

        loaded = load_recent_contexts()
        assert len(loaded) == 1  # Still one context
        assert loaded[0].last_session_id == "sess-002"  # Updated

    def test_record_preserves_pinned_status(self) -> None:
        """Recording existing context preserves its pinned status."""
        ctx = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
        )
        record_context(ctx)
        toggle_pin("platform", "/code/api", "/code/api")

        # Re-record same context
        ctx2 = WorkContext(
            team="platform",
            repo_root=Path("/code/api"),
            worktree_path=Path("/code/api"),
            worktree_name="main",
            last_session_id="new-session",
        )
        record_context(ctx2)

        loaded = load_recent_contexts()
        assert loaded[0].pinned is True  # Still pinned

    def test_load_sorts_by_recency(self) -> None:
        """Load returns contexts sorted by last_used descending."""
        # Create contexts with explicit different timestamps
        ctx_old = WorkContext(
            team="old",
            repo_root=Path("/old"),
            worktree_path=Path("/old"),
            worktree_name="main",
            last_used="2024-01-01T10:00:00+00:00",
        )
        ctx_new = WorkContext(
            team="new",
            repo_root=Path("/new"),
            worktree_path=Path("/new"),
            worktree_name="main",
            last_used="2024-01-02T10:00:00+00:00",
        )

        # Record in order (old first, new second)
        record_context(ctx_old)
        time.sleep(0.01)  # Ensure different timestamps
        record_context(ctx_new)

        loaded = load_recent_contexts()
        # Most recent first
        assert loaded[0].team == "new"
        assert loaded[1].team == "old"

    def test_load_sorts_pinned_first(self) -> None:
        """Pinned contexts appear before unpinned regardless of recency."""
        # Create old context first
        ctx_old = WorkContext(
            team="old",
            repo_root=Path("/old"),
            worktree_path=Path("/old"),
            worktree_name="main",
        )
        record_context(ctx_old)

        time.sleep(0.01)  # Ensure different timestamp

        # Create newer context
        ctx_new = WorkContext(
            team="new",
            repo_root=Path("/new"),
            worktree_path=Path("/new"),
            worktree_name="main",
        )
        record_context(ctx_new)

        # Pin the older context
        result = toggle_pin("old", "/old", "/old")
        assert result is True  # Confirm it was pinned

        loaded = load_recent_contexts()
        assert loaded[0].team == "old"  # Pinned comes first
        assert loaded[0].pinned is True
        assert loaded[1].team == "new"  # Unpinned second

    def test_load_respects_limit(self) -> None:
        """Load returns at most 'limit' contexts."""
        for i in range(10):
            record_context(
                WorkContext(
                    team=f"team-{i}",
                    repo_root=Path(f"/repo-{i}"),
                    worktree_path=Path(f"/repo-{i}"),
                    worktree_name="main",
                )
            )

        loaded = load_recent_contexts(limit=3)
        assert len(loaded) == 3

    def test_max_contexts_enforced(self) -> None:
        """Storage trims to MAX_CONTEXTS."""
        for i in range(MAX_CONTEXTS + 10):
            record_context(
                WorkContext(
                    team=f"team-{i}",
                    repo_root=Path(f"/repo-{i}"),
                    worktree_path=Path(f"/repo-{i}"),
                    worktree_name="main",
                )
            )

        loaded = load_recent_contexts(limit=100)
        assert len(loaded) <= MAX_CONTEXTS


class TestTogglePin:
    """Tests for pin/unpin functionality."""

    @pytest.fixture(autouse=True)
    def use_temp_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Use a temporary directory for cache."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def test_toggle_pin_on(self) -> None:
        """Toggle unpinned context to pinned."""
        record_context(
            WorkContext(
                team="a",
                repo_root=Path("/a"),
                worktree_path=Path("/a"),
                worktree_name="main",
            )
        )

        result = toggle_pin("a", "/a", "/a")
        assert result is True

        loaded = load_recent_contexts()
        assert loaded[0].pinned is True

    def test_toggle_pin_off(self) -> None:
        """Toggle pinned context to unpinned."""
        # Record unpinned first
        record_context(
            WorkContext(
                team="a",
                repo_root=Path("/a"),
                worktree_path=Path("/a"),
                worktree_name="main",
            )
        )

        # Pin it
        result1 = toggle_pin("a", "/a", "/a")
        assert result1 is True

        # Unpin it
        result2 = toggle_pin("a", "/a", "/a")
        assert result2 is False

        loaded = load_recent_contexts()
        assert loaded[0].pinned is False

    def test_toggle_pin_returns_none_when_not_found(self) -> None:
        """Toggle returns None when context doesn't exist."""
        result = toggle_pin("nonexistent", "/nonexistent", "/nonexistent")
        assert result is None


class TestClearContexts:
    """Tests for clearing context cache."""

    @pytest.fixture(autouse=True)
    def use_temp_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Use a temporary directory for cache."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def test_clear_removes_all_contexts(self) -> None:
        """Clear removes all contexts from storage."""
        for i in range(5):
            record_context(
                WorkContext(
                    team=f"team-{i}",
                    repo_root=Path(f"/repo-{i}"),
                    worktree_path=Path(f"/repo-{i}"),
                    worktree_name="main",
                )
            )

        count = clear_contexts()
        assert count == 5

        loaded = load_recent_contexts()
        assert loaded == []


class TestGetContextForPath:
    """Tests for finding context by path."""

    @pytest.fixture(autouse=True)
    def use_temp_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Use a temporary directory for cache."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def test_find_by_path(self, tmp_path: Path) -> None:
        """Find context by worktree path."""
        # Use real paths within tmp_path to avoid normalization issues
        wt_path = tmp_path / "a" / "wt"
        wt_path.mkdir(parents=True)
        b_path = tmp_path / "b"
        b_path.mkdir(parents=True)

        record_context(
            WorkContext(
                team="a",
                repo_root=tmp_path / "a",
                worktree_path=wt_path,
                worktree_name="wt",
            )
        )
        record_context(
            WorkContext(
                team="b",
                repo_root=b_path,
                worktree_path=b_path,
                worktree_name="main",
            )
        )

        ctx = get_context_for_path(wt_path)
        assert ctx is not None
        assert ctx.team == "a"

    def test_find_by_path_with_team_filter(self, tmp_path: Path) -> None:
        """Find context by path with team filter."""
        shared_path = tmp_path / "shared"
        shared_path.mkdir(parents=True)

        record_context(
            WorkContext(
                team="a",
                repo_root=shared_path,
                worktree_path=shared_path,
                worktree_name="main",
            )
        )
        record_context(
            WorkContext(
                team="b",
                repo_root=shared_path,
                worktree_path=shared_path,
                worktree_name="main",
            )
        )

        ctx = get_context_for_path(shared_path, team="b")
        assert ctx is not None
        assert ctx.team == "b"

    def test_find_returns_none_when_not_found(self) -> None:
        """Returns None when no matching context."""
        ctx = get_context_for_path("/nonexistent")
        assert ctx is None


# ─────────────────────────────────────────────────────────────────────────────
# Edge cases and error handling
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.fixture(autouse=True)
    def use_temp_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Use a temporary directory for cache."""
        self.cache_dir = tmp_path / "cache" / "scc"
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    def test_handles_corrupted_json(self) -> None:
        """Handles corrupted JSON file gracefully."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "contexts.json").write_text("{ invalid json }")

        # Should return empty list, not crash
        contexts = load_recent_contexts()
        assert contexts == []

    def test_handles_non_list_json(self) -> None:
        """Handles JSON that's not a list or versioned dict."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "contexts.json").write_text('{"not": "valid structure"}')

        contexts = load_recent_contexts()
        assert contexts == []

    def test_handles_legacy_list_format(self) -> None:
        """Handles legacy raw list format (auto-migrates on next write)."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        legacy_data = [
            {
                "team": "legacy",
                "repo_root": "/legacy",
                "worktree_path": "/legacy",
                "worktree_name": "main",
                "last_used": "2024-01-01T00:00:00+00:00",
            }
        ]
        (self.cache_dir / "contexts.json").write_text(json.dumps(legacy_data))

        contexts = load_recent_contexts()
        assert len(contexts) == 1
        assert contexts[0].team == "legacy"

    def test_creates_cache_directory_if_missing(self) -> None:
        """Creates cache directory when recording context."""
        ctx = WorkContext(
            team="test",
            repo_root=Path("/test"),
            worktree_path=Path("/test"),
            worktree_name="main",
        )
        record_context(ctx)

        assert self.cache_dir.exists()
        assert (self.cache_dir / "contexts.json").exists()

    def test_versioned_schema_on_write(self) -> None:
        """Written file uses versioned schema format."""
        ctx = WorkContext(
            team="test",
            repo_root=Path("/test"),
            worktree_path=Path("/test"),
            worktree_name="main",
        )
        record_context(ctx)

        with (self.cache_dir / "contexts.json").open() as f:
            data = json.load(f)

        assert "version" in data
        assert data["version"] == 1
        assert "contexts" in data
        assert isinstance(data["contexts"], list)
