"""Characterization tests for core/personal_profiles.py.

These tests capture the current behavior of the personal profiles module
before S02 surgery decomposes it. They protect against accidental behavior
changes during the split.

Target: src/scc_cli/core/personal_profiles.py (839 lines, 7 existing tests)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scc_cli.core import personal_profiles


def _write_json(path: Path, data: dict) -> None:
    """Helper to write JSON to a path, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


# ═══════════════════��═══════════════════════════��═══════════════════════════════
# Profile CRUD — Create
# ══════════════════════════════════════════════��═══════════════════════════��════


class TestSavePersonalProfile:
    """Characterize save_personal_profile behavior."""

    def test_save_creates_profile_file(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Saving a profile creates a JSON file in the personal projects dir."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: tmp_path / "personal")

        profile = personal_profiles.save_personal_profile(
            tmp_path / "workspace",
            {"enabledPlugins": {"p@m": True}},
            {"mcpServers": {}},
        )
        assert profile.path.exists()
        data = json.loads(profile.path.read_text())
        assert data["version"] == personal_profiles.PROFILE_VERSION
        assert data["settings"]["enabledPlugins"]["p@m"] is True
        assert data["mcp"] == {"mcpServers": {}}

    def test_save_with_none_settings_stores_empty_dicts(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Saving with None settings and mcp still stores empty dicts (not None)."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: tmp_path / "personal")

        profile = personal_profiles.save_personal_profile(tmp_path / "ws", None, None)
        data = json.loads(profile.path.read_text())
        assert data["settings"] == {}
        assert data["mcp"] == {}

    def test_save_overwrites_existing_profile(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Saving a profile for the same workspace overwrites the previous one."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: tmp_path / "personal")

        ws = tmp_path / "workspace"
        personal_profiles.save_personal_profile(ws, {"old": True}, None)
        profile = personal_profiles.save_personal_profile(ws, {"new": True}, None)
        data = json.loads(profile.path.read_text())
        assert data["settings"] == {"new": True}


# ═══════════════════════════════════════════════════════════════════════════════
# Profile CRUD — Read
# ════════════════════════════════════════════════════════════════════════��══════


class TestLoadPersonalProfile:
    """Characterize load_personal_profile behavior."""

    def test_load_nonexistent_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Loading a profile for a workspace with no saved profile returns None."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: tmp_path / "personal")

        result = personal_profiles.load_personal_profile(tmp_path / "no-such-workspace")
        assert result is None

    def test_load_corrupt_file_returns_none(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Loading a corrupt profile JSON returns None (fail-safe)."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        personal_dir = tmp_path / "personal"
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: personal_dir)

        ws = tmp_path / "workspace"
        repo_id = personal_profiles.get_repo_id(ws)
        profile_path = personal_profiles.get_profile_path(repo_id)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text("not valid json{{{")

        result = personal_profiles.load_personal_profile(ws)
        assert result is None

    def test_load_roundtrip_preserves_data(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A save followed by load returns the same data."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: tmp_path / "personal")

        ws = tmp_path / "workspace"
        settings = {"enabledPlugins": {"a@b": True, "c@d": False}}
        mcp = {"mcpServers": {"s1": {"type": "sse", "url": "http://localhost"}}}
        personal_profiles.save_personal_profile(ws, settings, mcp)

        loaded = personal_profiles.load_personal_profile(ws)
        assert loaded is not None
        assert loaded.settings == settings
        assert loaded.mcp == mcp


# ════════════════════���════════════════════════════════════���═════════════════════
# Profile CRUD — List
# ══════════════════════════════════════��════════════════════════════════════════


class TestListPersonalProfiles:
    """Characterize list_personal_profiles behavior."""

    def test_empty_when_no_profiles_exist(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns empty list when the personal projects directory doesn't exist."""
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: tmp_path / "empty")
        result = personal_profiles.list_personal_profiles()
        assert result == []

    def test_lists_multiple_saved_profiles(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Returns all saved profiles when multiple exist."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        personal_dir = tmp_path / "personal"
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: personal_dir)

        ws1 = tmp_path / "ws1"
        ws2 = tmp_path / "ws2"
        personal_profiles.save_personal_profile(ws1, {"a": 1}, None)
        personal_profiles.save_personal_profile(ws2, {"b": 2}, None)

        profiles = personal_profiles.list_personal_profiles()
        assert len(profiles) == 2
        repo_ids = {p.repo_id for p in profiles}
        assert personal_profiles.get_repo_id(ws1) in repo_ids
        assert personal_profiles.get_repo_id(ws2) in repo_ids

    def test_skips_corrupt_files_in_listing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Corrupt JSON files in the personal dir are silently skipped."""
        monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
        personal_dir = tmp_path / "personal"
        monkeypatch.setattr(personal_profiles, "get_personal_projects_dir", lambda: personal_dir)

        # Save one valid profile
        personal_profiles.save_personal_profile(tmp_path / "ws", {"ok": True}, None)
        # Write one corrupt file
        corrupt = personal_dir / "corrupt.json"
        corrupt.write_text("broken{{{")

        profiles = personal_profiles.list_personal_profiles()
        assert len(profiles) == 1


# ═══════════════��══════════════════════════���════════════════════════════���═══════
# Marketplace-state interaction
# ════════════════════════════════════��════════════════════════════════���═════════


class TestMarketplaceInteraction:
    """Characterize merge and marketplace-related behavior."""

    def test_merge_personal_mcp_overlays_correctly(self) -> None:
        """Personal MCP config merges under existing workspace MCP."""
        existing = {"mcpServers": {"s1": {"type": "sse"}}}
        personal = {"mcpServers": {"s2": {"type": "stdio"}}}
        merged = personal_profiles.merge_personal_mcp(existing, personal)
        # deep_merge merges existing into personal copy, so both should be present
        assert "s1" in merged["mcpServers"]
        assert "s2" in merged["mcpServers"]

    def test_merge_personal_mcp_empty_personal_returns_existing(self) -> None:
        """Empty personal MCP config returns existing unchanged."""
        existing = {"mcpServers": {"s1": {"type": "sse"}}}
        merged = personal_profiles.merge_personal_mcp(existing, {})
        assert merged == existing

    def test_merge_personal_mcp_empty_existing_returns_personal(self) -> None:
        """Empty existing MCP config returns personal."""
        personal = {"mcpServers": {"s2": {"type": "stdio"}}}
        merged = personal_profiles.merge_personal_mcp({}, personal)
        assert merged == personal


# ═══════════════════════════════════════════════��═════════════════════════════��═
# Edge cases: applied-state tracking
# ═════════════════════════════════════════��═════════════════════════════════════


class TestAppliedState:
    """Characterize applied state save/load/drift behavior."""

    def test_load_applied_state_missing_returns_none(self, tmp_path: Path) -> None:
        """No applied state file → None."""
        result = personal_profiles.load_applied_state(tmp_path)
        assert result is None

    def test_save_and_load_applied_state(self, tmp_path: Path) -> None:
        """Applied state roundtrip preserves profile_id and fingerprints."""
        fingerprints = {"settings.local.json": "abc123", ".mcp.json": "def456"}
        personal_profiles.save_applied_state(tmp_path, "my-profile", fingerprints)
        state = personal_profiles.load_applied_state(tmp_path)
        assert state is not None
        assert state.profile_id == "my-profile"
        assert state.fingerprints == fingerprints

    def test_drift_false_when_no_state(self, tmp_path: Path) -> None:
        """No applied state → no drift (safe default)."""
        assert personal_profiles.detect_drift(tmp_path) is False

    def test_workspace_has_overrides_false_on_empty(self, tmp_path: Path) -> None:
        """Empty workspace has no overrides."""
        assert personal_profiles.workspace_has_overrides(tmp_path) is False

    def test_workspace_has_overrides_true_with_settings(self, tmp_path: Path) -> None:
        """Workspace with settings.local.json is detected as having overrides."""
        _write_json(tmp_path / ".claude" / "settings.local.json", {"a": 1})
        assert personal_profiles.workspace_has_overrides(tmp_path) is True
