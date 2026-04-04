"""Cross-adapter audit integration tests — engine → adapter → audit event chain."""

from __future__ import annotations

from scc_cli.adapters.claude_safety_adapter import ClaudeSafetyAdapter
from scc_cli.adapters.codex_safety_adapter import CodexSafetyAdapter
from scc_cli.bootstrap import DefaultAdapters
from scc_cli.core.contracts import SafetyPolicy
from scc_cli.core.enums import SeverityLevel
from scc_cli.core.safety_engine import DefaultSafetyEngine
from tests.fakes import FakeAuditEventSink

_POLICY = SafetyPolicy()


def _make_claude() -> tuple[ClaudeSafetyAdapter, FakeAuditEventSink]:
    engine = DefaultSafetyEngine()
    sink = FakeAuditEventSink()
    return ClaudeSafetyAdapter(engine=engine, audit_sink=sink), sink


def _make_codex() -> tuple[CodexSafetyAdapter, FakeAuditEventSink]:
    engine = DefaultSafetyEngine()
    sink = FakeAuditEventSink()
    return CodexSafetyAdapter(engine=engine, audit_sink=sink), sink


class TestClaudeAdapterFullChainBlocked:
    def test_blocked_verdict_and_audit_event(self) -> None:
        adapter, sink = _make_claude()
        result = adapter.check_command("git push --force", _POLICY)

        assert result.verdict.allowed is False
        assert result.audit_emitted is True
        assert "[Claude] Command blocked" in result.user_message

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.metadata["provider_id"] == "claude"
        assert event.severity == SeverityLevel.WARNING


class TestCodexAdapterFullChainBlocked:
    def test_blocked_verdict_and_audit_event(self) -> None:
        adapter, sink = _make_codex()
        result = adapter.check_command("git push --force", _POLICY)

        assert result.verdict.allowed is False
        assert result.audit_emitted is True
        assert "[Codex] Command blocked" in result.user_message

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.metadata["provider_id"] == "codex"
        assert event.severity == SeverityLevel.WARNING


class TestClaudeAdapterFullChainAllowed:
    def test_allowed_verdict_and_audit_event(self) -> None:
        adapter, sink = _make_claude()
        result = adapter.check_command("git status", _POLICY)

        assert result.verdict.allowed is True
        assert result.user_message == "[Claude] Command allowed"

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.severity == SeverityLevel.INFO


class TestCodexAdapterFullChainAllowed:
    def test_allowed_verdict_and_audit_event(self) -> None:
        adapter, sink = _make_codex()
        result = adapter.check_command("git status", _POLICY)

        assert result.verdict.allowed is True
        assert result.user_message == "[Codex] Command allowed"

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.severity == SeverityLevel.INFO


class TestBothAdaptersShareEngineVerdicts:
    def test_same_command_produces_same_verdict(self) -> None:
        engine = DefaultSafetyEngine()
        claude_sink = FakeAuditEventSink()
        codex_sink = FakeAuditEventSink()
        claude = ClaudeSafetyAdapter(engine=engine, audit_sink=claude_sink)
        codex = CodexSafetyAdapter(engine=engine, audit_sink=codex_sink)

        policy = SafetyPolicy()
        command = "git push --force"

        claude_result = claude.check_command(command, policy)
        codex_result = codex.check_command(command, policy)

        assert claude_result.verdict.allowed == codex_result.verdict.allowed
        assert claude_result.verdict.matched_rule == codex_result.verdict.matched_rule


class TestAuditMetadataKeysAreAllStrings:
    def test_all_metadata_values_are_strings(self) -> None:
        adapter, sink = _make_claude()
        adapter.check_command("git push --force", _POLICY)

        event = sink.events[0]
        for key, value in event.metadata.items():
            assert isinstance(value, str), (
                f"metadata[{key!r}] is {type(value).__name__}, expected str"
            )


class TestBootstrapWiringHasSafetyAdapterFields:
    def test_default_adapters_accepts_safety_adapter_fields(self) -> None:
        """Verify DefaultAdapters has the new fields (no Docker probe call)."""
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(DefaultAdapters)}
        assert "claude_safety_adapter" in field_names
        assert "codex_safety_adapter" in field_names

    def test_fields_default_to_none(self) -> None:
        """Verify new fields are optional with None default."""
        import dataclasses

        fields_by_name = {f.name: f for f in dataclasses.fields(DefaultAdapters)}
        for name in ("claude_safety_adapter", "codex_safety_adapter"):
            f = fields_by_name[name]
            assert f.default is None, f"{name} default is {f.default!r}, expected None"
