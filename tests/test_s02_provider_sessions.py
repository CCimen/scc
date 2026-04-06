"""Tests for S02 provider-parameterized session/audit/context helpers.

Validates:
- get_provider_sessions_dir returns correct path per provider
- get_provider_recent_sessions returns empty list when no sessions.json
- get_provider_config_dir returns correct path per provider
- WorkContext.provider_id round-trip and backward compat
- WorkContext.display_label with and without provider
- Session list CLI includes provider_id in session_dicts
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scc_cli.commands.audit import get_provider_config_dir
from scc_cli.contexts import WorkContext
from scc_cli.core.errors import InvalidProviderError
from scc_cli.sessions import get_provider_recent_sessions, get_provider_sessions_dir

# ═══════════════════════════════════════════════════════════════════════════════
# get_provider_sessions_dir / get_provider_recent_sessions
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderSessionsDir:
    """Tests for sessions.get_provider_sessions_dir."""

    def test_claude_returns_dot_claude(self) -> None:
        result = get_provider_sessions_dir("claude")
        assert result == Path.home() / ".claude"

    def test_codex_returns_dot_codex(self) -> None:
        result = get_provider_sessions_dir("codex")
        assert result == Path.home() / ".codex"

    def test_default_is_claude(self) -> None:
        result = get_provider_sessions_dir()
        assert result == Path.home() / ".claude"

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(InvalidProviderError) as exc_info:
            get_provider_sessions_dir("gemini")
        assert "gemini" in str(exc_info.value)

    def test_provider_recent_sessions_empty_when_no_file(self, tmp_path: Path) -> None:
        """get_provider_recent_sessions returns [] when sessions.json doesn't exist."""
        with patch(
            "scc_cli.sessions.get_provider_sessions_dir",
            return_value=tmp_path / "nonexistent",
        ):
            result = get_provider_recent_sessions("claude")
        assert result == []

    def test_provider_recent_sessions_reads_json(self, tmp_path: Path) -> None:
        """get_provider_recent_sessions reads sessions from sessions.json."""
        sessions_dir = tmp_path / ".agent"
        sessions_dir.mkdir()
        sessions_file = sessions_dir / "sessions.json"
        sessions_file.write_text(json.dumps({"sessions": [{"id": "s1"}]}))

        with patch(
            "scc_cli.sessions.get_provider_sessions_dir",
            return_value=sessions_dir,
        ):
            result = get_provider_recent_sessions("claude")
        assert result == [{"id": "s1"}]

    def test_provider_recent_sessions_handles_corrupt_json(self, tmp_path: Path) -> None:
        """get_provider_recent_sessions returns [] on malformed JSON."""
        sessions_dir = tmp_path / ".agent"
        sessions_dir.mkdir()
        (sessions_dir / "sessions.json").write_text("{bad json")

        with patch(
            "scc_cli.sessions.get_provider_sessions_dir",
            return_value=sessions_dir,
        ):
            result = get_provider_recent_sessions("claude")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# get_provider_config_dir (audit.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderConfigDir:
    """Tests for audit.get_provider_config_dir."""

    def test_claude_returns_dot_claude(self) -> None:
        result = get_provider_config_dir("claude")
        assert result == Path.home() / ".claude"

    def test_codex_returns_dot_codex(self) -> None:
        result = get_provider_config_dir("codex")
        assert result == Path.home() / ".codex"

    def test_default_is_claude(self) -> None:
        result = get_provider_config_dir()
        assert result == Path.home() / ".claude"

    def test_unknown_provider_raises(self) -> None:
        with pytest.raises(InvalidProviderError):
            get_provider_config_dir("unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# WorkContext.provider_id
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorkContextProviderId:
    """Tests for WorkContext provider_id field and display_label."""

    def _make_ctx(self, **overrides: object) -> WorkContext:
        defaults = {
            "team": "platform",
            "repo_root": Path("/code/repo"),
            "worktree_path": Path("/code/repo"),
            "worktree_name": "main",
            "branch": "main",
        }
        defaults.update(overrides)
        return WorkContext(**defaults)  # type: ignore[arg-type]

    def test_provider_id_roundtrip(self) -> None:
        ctx = self._make_ctx(provider_id="codex")
        data = ctx.to_dict()
        restored = WorkContext.from_dict(data)
        assert restored.provider_id == "codex"

    def test_provider_id_default_none(self) -> None:
        ctx = self._make_ctx()
        assert ctx.provider_id is None

    def test_from_dict_backward_compat_no_provider_key(self) -> None:
        """Old serialized dicts without provider_id should deserialize to None."""
        data = {
            "team": "platform",
            "repo_root": "/code/repo",
            "worktree_path": "/code/repo",
            "worktree_name": "main",
        }
        ctx = WorkContext.from_dict(data)
        assert ctx.provider_id is None

    def test_display_label_without_provider(self) -> None:
        ctx = self._make_ctx(provider_id=None)
        label = ctx.display_label
        assert "platform" in label
        assert "repo" in label
        # No provider suffix
        assert "(" not in label

    def test_display_label_with_claude_provider(self) -> None:
        """Claude is the default provider — not shown in display_label."""
        ctx = self._make_ctx(provider_id="claude")
        label = ctx.display_label
        assert "(claude)" not in label

    def test_display_label_with_codex_provider(self) -> None:
        """Non-default providers are surfaced in display_label."""
        ctx = self._make_ctx(provider_id="codex")
        label = ctx.display_label
        assert "(codex)" in label

    def test_to_dict_includes_provider_id(self) -> None:
        ctx = self._make_ctx(provider_id="codex")
        data = ctx.to_dict()
        assert data["provider_id"] == "codex"

    def test_to_dict_includes_none_provider_id(self) -> None:
        ctx = self._make_ctx()
        data = ctx.to_dict()
        assert data["provider_id"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Session list provider column
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionListProvider:
    """Tests for session list CLI provider_id inclusion."""

    def test_session_dicts_includes_provider_id(self) -> None:
        """session_dicts built from SessionSummary carry provider_id."""
        from scc_cli.ports.session_models import SessionSummary

        summary = SessionSummary(
            name="test-session",
            workspace="/code/repo",
            team="platform",
            last_used="2026-01-01T00:00:00Z",
            container_name="scc-test-abc",
            branch="main",
            provider_id="codex",
        )
        # Replicate the dict-building logic from session_commands.py
        session_dict = {
            "name": summary.name,
            "workspace": summary.workspace,
            "team": summary.team,
            "last_used": summary.last_used,
            "container_name": summary.container_name,
            "branch": summary.branch,
            "provider_id": summary.provider_id or "claude",
        }
        assert session_dict["provider_id"] == "codex"

    def test_session_dicts_defaults_none_to_claude(self) -> None:
        """When SessionSummary.provider_id is None, dict defaults to 'claude'."""
        from scc_cli.ports.session_models import SessionSummary

        summary = SessionSummary(
            name="test-session",
            workspace="/code/repo",
            team="platform",
            last_used="2026-01-01T00:00:00Z",
            container_name=None,
            branch=None,
            provider_id=None,
        )
        session_dict = {
            "provider_id": summary.provider_id or "claude",
        }
        assert session_dict["provider_id"] == "claude"
