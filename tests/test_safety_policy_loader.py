"""Tests for core.safety_policy_loader — typed policy extraction from raw org config."""

from __future__ import annotations

import tokenize
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from scc_cli.core.contracts import SafetyPolicy
from scc_cli.core.safety_policy_loader import load_safety_policy

# ── Helpers ──────────────────────────────────────────────────────────────────


def _org(safety_net: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal org config dict with the given safety_net section."""
    return {"security": {"safety_net": safety_net}}


# ── None / empty / malformed org config ──────────────────────────────────────


class TestDefaultBlockFallback:
    """All parse failures must produce SafetyPolicy(action='block')."""

    def test_none_org_config_returns_default_block(self) -> None:
        policy = load_safety_policy(None)
        assert isinstance(policy, SafetyPolicy)
        assert policy.action == "block"

    def test_empty_dict_returns_default_block(self) -> None:
        policy = load_safety_policy({})
        assert policy.action == "block"

    def test_missing_security_key_returns_default_block(self) -> None:
        policy = load_safety_policy({"other": True})
        assert policy.action == "block"

    def test_missing_safety_net_key_returns_default_block(self) -> None:
        policy = load_safety_policy({"security": {"other_section": True}})
        assert policy.action == "block"

    def test_non_dict_org_config_returns_default_block(self) -> None:
        # Pass a string instead of dict — should still be fail-closed.
        policy = load_safety_policy("not-a-dict")  # type: ignore[arg-type]
        assert isinstance(policy, SafetyPolicy)
        assert policy.action == "block"

    def test_non_dict_security_returns_default_block(self) -> None:
        policy = load_safety_policy({"security": "string"})
        assert policy.action == "block"

    def test_non_dict_safety_net_returns_default_block(self) -> None:
        policy = load_safety_policy({"security": {"safety_net": 42}})
        assert policy.action == "block"


# ── Valid action passthrough ─────────────────────────────────────────────────


class TestValidActions:
    """Valid action strings must be returned unchanged."""

    @pytest.mark.parametrize("action", ["block", "warn", "allow"])
    def test_valid_action_passthrough(self, action: str) -> None:
        policy = load_safety_policy(_org({"action": action}))
        assert policy.action == action

    def test_invalid_action_falls_back_to_block(self) -> None:
        policy = load_safety_policy(_org({"action": "yolo"}))
        assert policy.action == "block"

    def test_missing_action_falls_back_to_block(self) -> None:
        policy = load_safety_policy(_org({"some_rule": True}))
        assert policy.action == "block"


# ── Rules extraction ─────────────────────────────────────────────────────────


class TestRulesExtraction:
    """Non-action keys must land in the rules dict."""

    def test_rules_extracted_from_policy(self) -> None:
        policy = load_safety_policy(
            _org({"action": "warn", "git_push_force": False, "shell_rm_rf": True})
        )
        assert policy.action == "warn"
        assert policy.rules == {"git_push_force": False, "shell_rm_rf": True}

    def test_rules_empty_when_only_action(self) -> None:
        policy = load_safety_policy(_org({"action": "allow"}))
        assert policy.rules == {}

    def test_source_is_set(self) -> None:
        policy = load_safety_policy(_org({"action": "warn"}))
        assert policy.source == "org.security.safety_net"


# ── Return-type invariant ────────────────────────────────────────────────────


class TestReturnTypeInvariant:
    """load_safety_policy must always return SafetyPolicy — never None, never raw dict."""

    @pytest.mark.parametrize(
        "org_config",
        [
            None,
            {},
            {"security": None},
            _org({"action": "block"}),
            _org({"action": "invalid"}),
            "not-a-dict",
            42,
            [],
        ],
    )
    def test_always_returns_safety_policy(self, org_config: Any) -> None:
        result = load_safety_policy(org_config)
        assert isinstance(result, SafetyPolicy)


# ── Import guardrail ────────────────────────────────────────────────────────


class TestNoDockerImport:
    """safety_policy_loader.py must never import from scc_cli.docker."""

    def test_no_import_from_docker_launch(self) -> None:
        source_path = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "scc_cli"
            / "core"
            / "safety_policy_loader.py"
        )
        source = source_path.read_text()

        # Use tokenize to check for NAME token "docker" in import contexts.
        tokens = list(tokenize.generate_tokens(StringIO(source).readline))

        in_import = False
        for tok in tokens:
            if tok.type == tokenize.NAME and tok.string in ("import", "from"):
                in_import = True
            elif tok.type == tokenize.NEWLINE or tok.type == tokenize.NL:
                in_import = False
            elif in_import and tok.type == tokenize.NAME and tok.string == "docker":
                pytest.fail(
                    "safety_policy_loader.py must not import from the docker package — "
                    f"found 'docker' token at line {tok.start[0]}"
                )
