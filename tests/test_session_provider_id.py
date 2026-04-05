"""Tests for provider_id threading through session models and services."""

from __future__ import annotations

from scc_cli.ports.session_models import (
    SessionFilter,
    SessionRecord,
    SessionSummary,
)


class TestSessionRecordProviderIdField:
    """SessionRecord carries provider_id through round-trip serialization."""

    def test_provider_id_present_in_to_dict(self) -> None:
        record = SessionRecord(workspace="/tmp/ws", provider_id="codex")
        data = record.to_dict()
        assert data["provider_id"] == "codex"

    def test_provider_id_none_omitted_from_to_dict(self) -> None:
        record = SessionRecord(workspace="/tmp/ws")
        data = record.to_dict()
        assert "provider_id" not in data

    def test_from_dict_with_provider_id(self) -> None:
        record = SessionRecord.from_dict(
            {"workspace": "/tmp/ws", "provider_id": "claude"}
        )
        assert record.provider_id == "claude"

    def test_from_dict_without_provider_id_defaults_none(self) -> None:
        record = SessionRecord.from_dict({"workspace": "/tmp/ws"})
        assert record.provider_id is None

    def test_round_trip_preserves_provider_id(self) -> None:
        original = SessionRecord(workspace="/tmp/ws", provider_id="codex", team="acme")
        data = original.to_dict()
        restored = SessionRecord.from_dict(data)
        assert restored.provider_id == original.provider_id
        assert restored.team == original.team

    def test_schema_version_defaults_to_2(self) -> None:
        record = SessionRecord(workspace="/tmp/ws")
        assert record.schema_version == 2

    def test_from_dict_preserves_legacy_schema_version(self) -> None:
        record = SessionRecord.from_dict(
            {"workspace": "/tmp/ws", "schema_version": 1}
        )
        assert record.schema_version == 1


class TestSessionSummaryProviderIdField:
    """SessionSummary carries provider_id."""

    def test_provider_id_set(self) -> None:
        summary = SessionSummary(
            name="test",
            workspace="/tmp/ws",
            team=None,
            last_used=None,
            container_name=None,
            branch=None,
            provider_id="codex",
        )
        assert summary.provider_id == "codex"

    def test_provider_id_defaults_none(self) -> None:
        summary = SessionSummary(
            name="test",
            workspace="/tmp/ws",
            team=None,
            last_used=None,
            container_name=None,
            branch=None,
        )
        assert summary.provider_id is None


class TestSessionFilterProviderIdField:
    """SessionFilter supports provider_id filtering."""

    def test_provider_id_defaults_none(self) -> None:
        f = SessionFilter()
        assert f.provider_id is None

    def test_provider_id_set(self) -> None:
        f = SessionFilter(provider_id="claude")
        assert f.provider_id == "claude"


class TestSessionFilterProviderIdFiltering:
    """Provider-id filtering in _filter_sessions via SessionService.list_recent."""

    def test_filter_by_provider_id(self) -> None:
        from unittest.mock import MagicMock

        from scc_cli.application.sessions.use_cases import SessionService

        claude_record = SessionRecord(
            workspace="/tmp/a",
            provider_id="claude",
            last_used="2025-01-02T00:00:00",
        )
        codex_record = SessionRecord(
            workspace="/tmp/b",
            provider_id="codex",
            last_used="2025-01-01T00:00:00",
        )
        none_record = SessionRecord(
            workspace="/tmp/c",
            last_used="2025-01-03T00:00:00",
        )
        store = MagicMock()
        store.load_sessions.return_value = [claude_record, codex_record, none_record]
        service = SessionService(store=store)
        result = service.list_recent(
            SessionFilter(include_all=True, provider_id="codex")
        )
        assert len(result.sessions) == 1
        assert result.sessions[0].provider_id == "codex"

    def test_filter_without_provider_id_returns_all(self) -> None:
        from unittest.mock import MagicMock

        from scc_cli.application.sessions.use_cases import SessionService

        r1 = SessionRecord(
            workspace="/tmp/a",
            provider_id="claude",
            last_used="2025-01-01T00:00:00",
        )
        r2 = SessionRecord(
            workspace="/tmp/b",
            provider_id="codex",
            last_used="2025-01-02T00:00:00",
        )
        store = MagicMock()
        store.load_sessions.return_value = [r1, r2]
        service = SessionService(store=store)
        result = service.list_recent(SessionFilter(include_all=True))
        assert len(result.sessions) == 2
