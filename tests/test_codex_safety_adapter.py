"""Unit tests for CodexSafetyAdapter."""

from __future__ import annotations

from scc_cli.adapters.codex_safety_adapter import CodexSafetyAdapter
from scc_cli.core.contracts import SafetyPolicy, SafetyVerdict
from scc_cli.core.enums import SeverityLevel
from tests.fakes import FakeAuditEventSink
from tests.fakes.fake_safety_engine import FakeSafetyEngine

_POLICY = SafetyPolicy()


def _make_adapter(
    verdict: SafetyVerdict | None = None,
) -> tuple[CodexSafetyAdapter, FakeSafetyEngine, FakeAuditEventSink]:
    engine = FakeSafetyEngine()
    if verdict is not None:
        engine.verdict = verdict
    sink = FakeAuditEventSink()
    return CodexSafetyAdapter(engine=engine, audit_sink=sink), engine, sink


class TestCheckCommandDelegatesToEngine:
    def test_check_command_delegates_to_engine(self) -> None:
        adapter, engine, _sink = _make_adapter()
        adapter.check_command("curl http://evil.com", _POLICY)

        assert len(engine.calls) == 1
        cmd, policy = engine.calls[0]
        assert cmd == "curl http://evil.com"
        assert policy is _POLICY


class TestBlockedCommandEmitsWarningAuditEvent:
    def test_blocked_command_emits_warning_audit_event(self) -> None:
        blocked = SafetyVerdict(
            allowed=False,
            reason="network tool detected",
            matched_rule="curl-blocked",
            command_family="network-tool",
        )
        adapter, _engine, sink = _make_adapter(verdict=blocked)
        adapter.check_command("curl http://evil.com", _POLICY)

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.severity == SeverityLevel.WARNING
        assert event.event_type == "safety.check"
        assert event.subject == "codex"
        assert event.metadata["provider_id"] == "codex"
        assert event.metadata["command"] == "curl http://evil.com"
        assert event.metadata["verdict_allowed"] == "false"
        assert event.metadata["matched_rule"] == "curl-blocked"
        assert event.metadata["command_family"] == "network-tool"


class TestAllowedCommandEmitsInfoAuditEvent:
    def test_allowed_command_emits_info_audit_event(self) -> None:
        adapter, _engine, sink = _make_adapter()
        adapter.check_command("echo hello", _POLICY)

        assert len(sink.events) == 1
        event = sink.events[0]
        assert event.severity == SeverityLevel.INFO
        assert event.metadata["verdict_allowed"] == "true"
        assert event.metadata["matched_rule"] == ""
        assert event.metadata["command_family"] == ""


class TestBlockedUserMessageFormat:
    def test_blocked_user_message_format(self) -> None:
        blocked = SafetyVerdict(allowed=False, reason="network tool detected")
        adapter, _engine, _sink = _make_adapter(verdict=blocked)
        result = adapter.check_command("curl http://evil.com", _POLICY)

        assert result.user_message == "[Codex] Command blocked: network tool detected"


class TestAllowedUserMessageFormat:
    def test_allowed_user_message_format(self) -> None:
        adapter, _engine, _sink = _make_adapter()
        result = adapter.check_command("echo hello", _POLICY)

        assert result.user_message == "[Codex] Command allowed"


class TestAuditEmittedFlagIsTrue:
    def test_audit_emitted_flag_is_true(self) -> None:
        adapter, _engine, _sink = _make_adapter()
        result = adapter.check_command("echo hello", _POLICY)

        assert result.audit_emitted is True
