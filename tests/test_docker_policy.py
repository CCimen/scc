"""Unit tests for safety-net policy extraction and validation functions.

These tests verify the pure functions in docker/launch.py that handle
safety-net policy extraction from org config and validation with fail-closed
behavior.

Test Coverage:
- extract_safety_net_policy: 12 tests
- validate_safety_net_policy: 15 tests
- get_effective_safety_net_policy: 10 tests
- Constants verification: 8 tests
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scc_cli.docker.launch import (
    DEFAULT_SAFETY_NET_POLICY,
    VALID_SAFETY_NET_ACTIONS,
    extract_safety_net_policy,
    get_effective_safety_net_policy,
    validate_safety_net_policy,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def full_safety_net_policy() -> dict[str, Any]:
    """Full policy with all rule flags."""
    return {
        "action": "block",
        "block_force_push": True,
        "block_reset_hard": True,
        "block_branch_force_delete": True,
        "block_checkout_restore": True,
        "block_clean": True,
        "block_stash_destructive": True,
    }


@pytest.fixture
def org_config_with_safety_net(full_safety_net_policy: dict[str, Any]) -> dict[str, Any]:
    """Org config with safety_net section."""
    return {
        "organization": {"name": "Test Org", "id": "test-org"},
        "security": {"safety_net": full_safety_net_policy},
    }


@pytest.fixture
def example_09_org_config() -> dict[str, Any]:
    """Load the example 09 org config file."""
    example_path = Path(__file__).parent.parent / "examples" / "09-org-safety-net-enabled.json"
    if example_path.exists():
        data: dict[str, Any] = json.loads(example_path.read_text())
        return data
    # Fallback if example doesn't exist
    return {
        "security": {
            "safety_net": {
                "action": "block",
                "block_force_push": True,
                "block_reset_hard": True,
            }
        }
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TestExtractSafetyNetPolicy - 12 tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExtractSafetyNetPolicy:
    """Tests for extract_safety_net_policy function."""

    def test_extract_from_valid_org_config_with_safety_net(
        self, org_config_with_safety_net: dict[str, Any]
    ) -> None:
        """Extract safety_net from a valid org config."""
        result = extract_safety_net_policy(org_config_with_safety_net)

        assert result is not None
        assert result["action"] == "block"
        assert result["block_force_push"] is True

    def test_extract_returns_none_when_org_config_is_none(self) -> None:
        """Return None when org_config is None."""
        result = extract_safety_net_policy(None)

        assert result is None

    def test_extract_returns_none_when_security_section_missing(self) -> None:
        """Return None when security section is missing."""
        org_config = {"organization": {"name": "Test Org"}}

        result = extract_safety_net_policy(org_config)

        assert result is None

    def test_extract_returns_none_when_safety_net_missing(self) -> None:
        """Return None when safety_net is missing from security."""
        org_config = {"security": {"blocked_plugins": ["*malicious*"]}}

        result = extract_safety_net_policy(org_config)

        assert result is None

    def test_extract_with_empty_safety_net_returns_empty_dict(self) -> None:
        """Return empty dict when safety_net is empty."""
        org_config: dict[str, Any] = {"security": {"safety_net": {}}}

        result = extract_safety_net_policy(org_config)

        assert result == {}

    def test_extract_preserves_all_rule_flags(self, full_safety_net_policy: dict[str, Any]) -> None:
        """All rule flags are preserved during extraction."""
        org_config = {"security": {"safety_net": full_safety_net_policy}}

        result = extract_safety_net_policy(org_config)

        assert result is not None
        assert result["block_force_push"] is True
        assert result["block_reset_hard"] is True
        assert result["block_branch_force_delete"] is True
        assert result["block_checkout_restore"] is True
        assert result["block_clean"] is True
        assert result["block_stash_destructive"] is True

    def test_extract_ignores_non_safety_net_security_fields(self) -> None:
        """Only safety_net is extracted, other security fields are ignored."""
        org_config = {
            "security": {
                "blocked_plugins": ["*malicious*"],
                "blocked_mcp_servers": ["*.untrusted.com"],
                "safety_net": {"action": "warn"},
            }
        }

        result = extract_safety_net_policy(org_config)

        assert result is not None
        assert result == {"action": "warn"}
        assert "blocked_plugins" not in result

    def test_extract_with_nested_org_config_structure(
        self, example_09_org_config: dict[str, Any]
    ) -> None:
        """Extract from a realistic nested org config structure."""
        result = extract_safety_net_policy(example_09_org_config)

        assert result is not None
        assert "action" in result

    def test_extract_returns_none_for_empty_org_config(self) -> None:
        """Return None for empty org config."""
        result = extract_safety_net_policy({})

        assert result is None

    def test_extract_returns_none_for_security_equals_none(self) -> None:
        """Return None when security is explicitly None."""
        org_config: dict[str, Any] = {"security": None}

        result = extract_safety_net_policy(org_config)

        assert result is None

    def test_extract_returns_none_for_safety_net_equals_none(self) -> None:
        """Return None when safety_net is explicitly None."""
        org_config: dict[str, Any] = {"security": {"safety_net": None}}

        result = extract_safety_net_policy(org_config)

        assert result is None

    def test_extract_handles_string_safety_net_value_gracefully(self) -> None:
        """Return None when safety_net is not a dict (e.g., string)."""
        org_config = {"security": {"safety_net": "invalid"}}

        result = extract_safety_net_policy(org_config)

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# TestValidateSafetyNetPolicy - 15 tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateSafetyNetPolicy:
    """Tests for validate_safety_net_policy function with fail-closed behavior."""

    def test_validate_valid_block_action_unchanged(self) -> None:
        """Valid 'block' action remains unchanged."""
        policy = {"action": "block"}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_valid_warn_action_unchanged(self) -> None:
        """Valid 'warn' action remains unchanged."""
        policy = {"action": "warn"}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "warn"

    def test_validate_valid_allow_action_unchanged(self) -> None:
        """Valid 'allow' action remains unchanged."""
        policy = {"action": "allow"}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "allow"

    def test_validate_invalid_action_defaults_to_block(self) -> None:
        """Invalid action defaults to 'block' (FAIL-CLOSED behavior)."""
        policy = {"action": "invalid"}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_missing_action_defaults_to_block(self) -> None:
        """Missing action defaults to 'block'."""
        policy = {"block_force_push": True}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"
        assert result["block_force_push"] is True

    def test_validate_empty_policy_adds_block_action(self) -> None:
        """Empty policy gets 'block' action added."""
        policy: dict[str, Any] = {}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_preserves_rule_flags_with_invalid_action(self) -> None:
        """Rule flags are preserved even when action is corrected."""
        policy = {"action": "xyz", "block_force_push": True, "block_reset_hard": False}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"
        assert result["block_force_push"] is True
        assert result["block_reset_hard"] is False

    def test_validate_case_sensitivity_block(self) -> None:
        """Uppercase 'BLOCK' defaults to 'block' (case sensitive)."""
        policy = {"action": "BLOCK"}

        result = validate_safety_net_policy(policy)

        # Case sensitive - 'BLOCK' is not in valid set, defaults to 'block'
        assert result["action"] == "block"

    def test_validate_case_sensitivity_warn(self) -> None:
        """Uppercase 'WARN' defaults to 'block' (case sensitive)."""
        policy = {"action": "WARN"}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_whitespace_action_defaults_to_block(self) -> None:
        """Action with whitespace defaults to 'block'."""
        policy = {"action": " warn "}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_numeric_action_defaults_to_block(self) -> None:
        """Numeric action defaults to 'block'."""
        policy: dict[str, Any] = {"action": 1}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_none_action_defaults_to_block(self) -> None:
        """None action defaults to 'block'."""
        policy: dict[str, Any] = {"action": None}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_empty_string_action_defaults_to_block(self) -> None:
        """Empty string action defaults to 'block'."""
        policy = {"action": ""}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "block"

    def test_validate_preserves_all_boolean_flags(self) -> None:
        """All boolean rule flags are preserved during validation."""
        policy = {
            "action": "warn",
            "block_force_push": True,
            "block_reset_hard": False,
            "block_branch_force_delete": True,
            "block_checkout_restore": False,
            "block_clean": True,
            "block_stash_destructive": False,
        }

        result = validate_safety_net_policy(policy)

        assert result["action"] == "warn"
        assert result["block_force_push"] is True
        assert result["block_reset_hard"] is False
        assert result["block_branch_force_delete"] is True
        assert result["block_checkout_restore"] is False
        assert result["block_clean"] is True
        assert result["block_stash_destructive"] is False

    def test_validate_ignores_unknown_fields(self) -> None:
        """Unknown fields are passed through unchanged."""
        policy = {"action": "warn", "unknown_field": True, "custom_setting": "value"}

        result = validate_safety_net_policy(policy)

        assert result["action"] == "warn"
        assert result["unknown_field"] is True
        assert result["custom_setting"] == "value"


# ═══════════════════════════════════════════════════════════════════════════════
# TestGetEffectiveSafetyNetPolicy - 10 tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetEffectiveSafetyNetPolicy:
    """Tests for get_effective_safety_net_policy composed function."""

    def test_effective_with_valid_org_config(
        self, org_config_with_safety_net: dict[str, Any]
    ) -> None:
        """Get effective policy from valid org config."""
        result = get_effective_safety_net_policy(org_config_with_safety_net)

        assert result["action"] == "block"
        assert result["block_force_push"] is True

    def test_effective_with_none_org_config_returns_default(self) -> None:
        """None org config returns DEFAULT_SAFETY_NET_POLICY."""
        result = get_effective_safety_net_policy(None)

        assert result == DEFAULT_SAFETY_NET_POLICY
        assert result["action"] == "block"

    def test_effective_with_missing_safety_net_returns_default(self) -> None:
        """Missing safety_net returns default policy."""
        org_config: dict[str, Any] = {"security": {"blocked_plugins": []}}

        result = get_effective_safety_net_policy(org_config)

        assert result == DEFAULT_SAFETY_NET_POLICY

    def test_effective_with_invalid_action_returns_corrected(self) -> None:
        """Invalid action is corrected to 'block'."""
        org_config = {"security": {"safety_net": {"action": "bad"}}}

        result = get_effective_safety_net_policy(org_config)

        assert result["action"] == "block"

    def test_effective_with_empty_org_config_returns_default(self) -> None:
        """Empty org config returns default policy."""
        result = get_effective_safety_net_policy({})

        assert result == DEFAULT_SAFETY_NET_POLICY

    def test_effective_uses_example_09_org_config(
        self, example_09_org_config: dict[str, Any]
    ) -> None:
        """Correctly extracts policy from example 09 config."""
        result = get_effective_safety_net_policy(example_09_org_config)

        assert result is not None
        assert "action" in result
        # The example uses "block" action
        assert result["action"] in VALID_SAFETY_NET_ACTIONS

    def test_effective_combines_extract_and_validate_correctly(self) -> None:
        """Composition order: extract first, then validate."""
        # Invalid action should be corrected
        org_config = {"security": {"safety_net": {"action": "typo", "block_force_push": True}}}

        result = get_effective_safety_net_policy(org_config)

        # Action corrected, rule preserved
        assert result["action"] == "block"
        assert result["block_force_push"] is True

    def test_effective_with_partial_policy_adds_action(self) -> None:
        """Partial policy (no action) gets action added."""
        org_config = {"security": {"safety_net": {"block_force_push": False}}}

        result = get_effective_safety_net_policy(org_config)

        assert result["action"] == "block"
        assert result["block_force_push"] is False

    def test_effective_never_returns_none(self) -> None:
        """get_effective_safety_net_policy never returns None."""
        test_cases: list[dict[str, Any] | None] = [
            None,
            {},
            {"security": None},
            {"security": {}},
            {"security": {"safety_net": None}},
        ]

        for test_input in test_cases:
            result = get_effective_safety_net_policy(test_input)
            assert result is not None, f"Failed for input: {test_input}"
            assert isinstance(result, dict)

    def test_effective_action_always_in_valid_set(self) -> None:
        """Returned action is always in VALID_SAFETY_NET_ACTIONS."""
        test_cases = [
            None,
            {},
            {"security": {"safety_net": {"action": "invalid"}}},
            {"security": {"safety_net": {"action": "block"}}},
            {"security": {"safety_net": {"action": "warn"}}},
            {"security": {"safety_net": {"action": "allow"}}},
        ]

        for test_input in test_cases:
            result = get_effective_safety_net_policy(test_input)
            assert result["action"] in VALID_SAFETY_NET_ACTIONS, f"Failed for: {test_input}"


# ═══════════════════════════════════════════════════════════════════════════════
# TestConstants - 8 tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    """Tests for safety-net related constants."""

    def test_valid_actions_contains_block_warn_allow(self) -> None:
        """VALID_SAFETY_NET_ACTIONS contains exactly block, warn, allow."""
        assert VALID_SAFETY_NET_ACTIONS == frozenset({"block", "warn", "allow"})

    def test_default_policy_has_block_action(self) -> None:
        """DEFAULT_SAFETY_NET_POLICY has 'block' action."""
        assert DEFAULT_SAFETY_NET_POLICY["action"] == "block"

    def test_constants_are_immutable(self) -> None:
        """Constants are immutable types."""
        # frozenset is immutable
        assert isinstance(VALID_SAFETY_NET_ACTIONS, frozenset)

        # Try to modify - should fail or not affect original
        with pytest.raises((TypeError, AttributeError)):
            VALID_SAFETY_NET_ACTIONS.add("new_action")  # type: ignore[attr-defined]

    def test_expected_rule_flags_are_supported(self) -> None:
        """Expected rule flags are documented and supported."""
        expected_flags = {
            "block_force_push",
            "block_reset_hard",
            "block_branch_force_delete",
            "block_checkout_restore",
            "block_clean",
            "block_stash_destructive",
        }

        # Verify these flags work with validation
        policy: dict[str, Any] = {flag: True for flag in expected_flags}
        policy["action"] = "warn"

        result = validate_safety_net_policy(policy)

        for flag in expected_flags:
            assert flag in result

    def test_action_field_name_matches_schema(self) -> None:
        """The 'action' field name matches expected schema."""
        policy = {"action": "block"}

        result = validate_safety_net_policy(policy)

        assert "action" in result

    def test_policy_structure_matches_plugin_expectations(self) -> None:
        """Policy structure matches what scc-safety-net plugin expects.

        The plugin's DEFAULT_POLICY has:
        - action: "block"
        - block_force_push: True
        - block_reset_hard: True
        - block_branch_force_delete: True
        - block_checkout_restore: True
        - block_clean: True
        - block_stash_destructive: True
        """
        plugin_expected_keys = {
            "action",
            "block_force_push",
            "block_reset_hard",
            "block_branch_force_delete",
            "block_checkout_restore",
            "block_clean",
            "block_stash_destructive",
        }

        # Create a full policy
        policy = {
            "action": "block",
            "block_force_push": True,
            "block_reset_hard": True,
            "block_branch_force_delete": True,
            "block_checkout_restore": True,
            "block_clean": True,
            "block_stash_destructive": True,
        }

        result = validate_safety_net_policy(policy)

        # All expected keys should be present
        for key in plugin_expected_keys:
            assert key in result

    def test_nested_security_path_matches_schema(self) -> None:
        """The security.safety_net path matches org schema."""
        org_config = {"security": {"safety_net": {"action": "warn"}}}

        result = extract_safety_net_policy(org_config)

        assert result is not None
        assert result["action"] == "warn"

    def test_policy_compatible_with_json_serialization(self) -> None:
        """Policy can be serialized to JSON and back."""
        policy = {
            "action": "block",
            "block_force_push": True,
            "block_reset_hard": False,
        }

        # Round-trip: dict → JSON → dict
        json_str = json.dumps(policy)
        roundtrip = json.loads(json_str)

        assert roundtrip == policy
        assert validate_safety_net_policy(roundtrip)["action"] == "block"
