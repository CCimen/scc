"""
Tests for config invariant validation.

TDD tests for validate_config_invariants() function.
Tests the governance invariants:
- enabled plugins must be subset of allowed (enabled ⊆ allowed)
- enabled plugins must not be blocked (enabled ∩ blocked = ∅)

Follows the semantics:
- allowed_plugins: None = unrestricted, [] = deny all, ["*"] = explicit unrestricted
"""

from __future__ import annotations

from scc_cli.validate import InvariantViolation, validate_config_invariants


class TestInvariantViolationDataclass:
    """Test InvariantViolation dataclass structure."""

    def test_invariant_violation_has_required_fields(self) -> None:
        """InvariantViolation should have rule, message, and severity fields."""
        violation = InvariantViolation(
            rule="test_rule",
            message="Test message",
            severity="error",
        )
        assert violation.rule == "test_rule"
        assert violation.message == "Test message"
        assert violation.severity == "error"

    def test_invariant_violation_severity_can_be_warning(self) -> None:
        """InvariantViolation should accept 'warning' severity."""
        violation = InvariantViolation(
            rule="test_rule",
            message="Test message",
            severity="warning",
        )
        assert violation.severity == "warning"


class TestAllowedPluginsSemantics:
    """Test allowed_plugins semantics: None = unrestricted, [] = deny all, ["*"] = unrestricted."""

    def test_allowed_plugins_none_means_unrestricted(self) -> None:
        """When allowed_plugins is None (missing), all plugins are allowed."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-a@marketplace", "plugin-b@marketplace"],
                # allowed_plugins is missing = unrestricted
            }
        }
        violations = validate_config_invariants(config)
        # No violations because missing = unrestricted
        assert len(violations) == 0

    def test_allowed_plugins_empty_list_means_deny_all(self) -> None:
        """When allowed_plugins is [], no plugins are allowed."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-a@marketplace"],
                "allowed_plugins": [],  # Empty = nothing allowed
            }
        }
        violations = validate_config_invariants(config)
        # Should have 1 violation: plugin-a is enabled but nothing is allowed
        assert len(violations) == 1
        assert violations[0].rule == "enabled_must_be_allowed"
        assert "plugin-a@marketplace" in violations[0].message
        assert "empty" in violations[0].message.lower()
        assert violations[0].severity == "error"

    def test_allowed_plugins_wildcard_means_unrestricted(self) -> None:
        """When allowed_plugins is ["*"], all plugins are allowed."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-a@marketplace", "plugin-b@marketplace"],
                "allowed_plugins": ["*"],  # Explicit unrestricted
            }
        }
        violations = validate_config_invariants(config)
        # No violations because ["*"] = unrestricted
        assert len(violations) == 0


class TestEnabledSubsetOfAllowed:
    """Test invariant: enabled plugins must be in allowed list."""

    def test_enabled_plugin_in_allowed_list_passes(self) -> None:
        """Enabled plugin that is in allowed list should pass."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-a@marketplace"],
                "allowed_plugins": ["plugin-a@marketplace", "plugin-b@marketplace"],
            }
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 0

    def test_enabled_plugin_not_in_allowed_list_fails(self) -> None:
        """Enabled plugin not in allowed list should fail."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-c@marketplace"],
                "allowed_plugins": ["plugin-a@marketplace", "plugin-b@marketplace"],
            }
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 1
        assert violations[0].rule == "enabled_must_be_allowed"
        assert "plugin-c@marketplace" in violations[0].message
        assert violations[0].severity == "error"

    def test_multiple_enabled_plugins_not_allowed_produces_multiple_violations(self) -> None:
        """Multiple enabled plugins not in allowed list should produce multiple violations."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-a@mp", "plugin-b@mp", "plugin-c@mp"],
                "allowed_plugins": ["plugin-a@mp"],  # Only plugin-a allowed
            }
        }
        violations = validate_config_invariants(config)
        # plugin-b and plugin-c should fail
        assert len(violations) == 2
        violation_messages = [v.message for v in violations]
        assert any("plugin-b@mp" in msg for msg in violation_messages)
        assert any("plugin-c@mp" in msg for msg in violation_messages)

    def test_allowed_plugins_pattern_matching(self) -> None:
        """Allowed plugins should support fnmatch pattern matching."""
        config = {
            "defaults": {
                "enabled_plugins": ["safety-net@official", "linter@official"],
                "allowed_plugins": ["*@official"],  # All plugins from official marketplace
            }
        }
        violations = validate_config_invariants(config)
        # Both should match the pattern
        assert len(violations) == 0

    def test_allowed_plugins_pattern_no_match(self) -> None:
        """Plugin that doesn't match any allowed pattern should fail."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin@internal"],
                "allowed_plugins": ["*@official"],  # Only official marketplace allowed
            }
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 1
        assert "plugin@internal" in violations[0].message


class TestEnabledNotInBlocked:
    """Test invariant: enabled plugins must not be in blocked list."""

    def test_enabled_plugin_not_blocked_passes(self) -> None:
        """Enabled plugin that is not blocked should pass."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-a@marketplace"],
            },
            "security": {
                "blocked_plugins": ["malicious-*"],
            },
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 0

    def test_enabled_plugin_exactly_blocked_fails(self) -> None:
        """Enabled plugin that exactly matches blocked pattern should fail."""
        config = {
            "defaults": {
                "enabled_plugins": ["malicious-plugin@marketplace"],
            },
            "security": {
                "blocked_plugins": ["malicious-plugin@marketplace"],
            },
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 1
        assert violations[0].rule == "enabled_not_blocked"
        assert "malicious-plugin@marketplace" in violations[0].message
        assert violations[0].severity == "error"

    def test_enabled_plugin_matches_blocked_pattern_fails(self) -> None:
        """Enabled plugin that matches blocked pattern should fail."""
        config = {
            "defaults": {
                "enabled_plugins": ["malicious-crypto-miner@shady"],
            },
            "security": {
                "blocked_plugins": ["malicious-*"],  # Pattern match
            },
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 1
        assert violations[0].rule == "enabled_not_blocked"
        assert "malicious-crypto-miner@shady" in violations[0].message

    def test_multiple_enabled_plugins_blocked_produces_multiple_violations(self) -> None:
        """Multiple enabled plugins matching blocked patterns produce multiple violations."""
        config = {
            "defaults": {
                "enabled_plugins": ["bad-plugin@mp", "evil-plugin@mp", "good-plugin@mp"],
            },
            "security": {
                "blocked_plugins": ["bad-*", "evil-*"],
            },
        }
        violations = validate_config_invariants(config)
        # bad-plugin and evil-plugin should fail
        blocked_violations = [v for v in violations if v.rule == "enabled_not_blocked"]
        assert len(blocked_violations) == 2


class TestCombinedInvariants:
    """Test combined invariant violations."""

    def test_plugin_violates_both_allowed_and_blocked(self) -> None:
        """Plugin that violates both allowed and blocked should produce violations for both."""
        config = {
            "defaults": {
                "enabled_plugins": ["malicious-plugin@mp"],
                "allowed_plugins": ["safe-plugin@mp"],  # malicious not in allowed
            },
            "security": {
                "blocked_plugins": ["malicious-*"],  # malicious is also blocked
            },
        }
        violations = validate_config_invariants(config)
        # Should have 2 violations: not allowed AND blocked
        assert len(violations) == 2
        rules = {v.rule for v in violations}
        assert "enabled_must_be_allowed" in rules
        assert "enabled_not_blocked" in rules

    def test_no_enabled_plugins_passes(self) -> None:
        """No enabled plugins should always pass."""
        config = {
            "defaults": {
                "enabled_plugins": [],
                "allowed_plugins": ["plugin-a@mp"],
            },
            "security": {
                "blocked_plugins": ["plugin-b@mp"],
            },
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 0

    def test_missing_defaults_section_passes(self) -> None:
        """Missing defaults section should pass (nothing to validate)."""
        config = {
            "security": {
                "blocked_plugins": ["plugin-*"],
            },
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 0

    def test_missing_security_section_uses_empty_blocked(self) -> None:
        """Missing security section should treat blocked_plugins as empty."""
        config = {
            "defaults": {
                "enabled_plugins": ["plugin-a@mp"],
                # No allowed_plugins = unrestricted
            },
            # No security section
        }
        violations = validate_config_invariants(config)
        # Should pass - plugin is enabled, allowed (unrestricted), not blocked (empty)
        assert len(violations) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_config_passes(self) -> None:
        """Empty config should pass (nothing to validate)."""
        config: dict[str, object] = {}
        violations = validate_config_invariants(config)
        assert len(violations) == 0

    def test_enabled_plugins_missing_but_allowed_set_passes(self) -> None:
        """Missing enabled_plugins with set allowed_plugins should pass."""
        config = {
            "defaults": {
                "allowed_plugins": ["plugin-a@mp"],
                # enabled_plugins is missing = empty
            },
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 0

    def test_allowed_plugins_empty_but_no_enabled_passes(self) -> None:
        """Empty allowed_plugins with no enabled plugins should pass."""
        config = {
            "defaults": {
                "enabled_plugins": [],
                "allowed_plugins": [],
            },
        }
        violations = validate_config_invariants(config)
        assert len(violations) == 0
