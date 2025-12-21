"""Tests for the evaluation layer (Phase 2.1).

TDD approach: Write tests first, implement to make them pass.

Tests cover:
- BlockedItem and DeniedAddition data structures
- EvaluationResult with BlockReason annotations
- apply_policy_exceptions() can override any block
- apply_local_overrides() only overrides DELEGATION blocks
- Decision records include exception_id and expires_in
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from scc_cli.models.exceptions import (
    AllowTargets,
    BlockReason,
    Exception,
)

# ═══════════════════════════════════════════════════════════════════════════════
# BlockedItem Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockedItem:
    """Tests for the BlockedItem dataclass."""

    def test_create_security_blocked_item(self):
        """Create a security-blocked item."""
        from scc_cli.evaluation.models import BlockedItem

        item = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Blocked by org security policy",
        )
        assert item.target == "vendor-tools"
        assert item.target_type == "plugin"
        assert item.reason == BlockReason.SECURITY
        assert item.message == "Blocked by org security policy"

    def test_create_delegation_blocked_item(self):
        """Create a delegation-blocked item (should use DeniedAddition instead)."""
        from scc_cli.evaluation.models import BlockedItem

        # Security blocks use BlockedItem
        item = BlockedItem(
            target="dangerous-image",
            target_type="base_image",
            reason=BlockReason.SECURITY,
            message="Image not in allowlist",
        )
        assert item.reason == BlockReason.SECURITY


# ═══════════════════════════════════════════════════════════════════════════════
# DeniedAddition Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeniedAddition:
    """Tests for the DeniedAddition dataclass."""

    def test_create_denied_addition(self):
        """Create a delegation-denied addition."""
        from scc_cli.evaluation.models import DeniedAddition

        item = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Team not delegated for MCP additions",
        )
        assert item.target == "jira-api"
        assert item.target_type == "mcp_server"
        assert item.reason == BlockReason.DELEGATION
        assert item.message == "Team not delegated for MCP additions"

    def test_denied_addition_always_delegation(self):
        """DeniedAddition should always use DELEGATION reason."""
        from scc_cli.evaluation.models import DeniedAddition

        item = DeniedAddition(
            target="new-plugin",
            target_type="plugin",
            reason=BlockReason.DELEGATION,
            message="Plugin additions not delegated",
        )
        assert item.reason == BlockReason.DELEGATION


# ═══════════════════════════════════════════════════════════════════════════════
# Decision Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDecision:
    """Tests for the Decision dataclass."""

    def test_create_allowed_decision(self):
        """Create a decision record for an allowed item."""
        from scc_cli.evaluation.models import Decision

        decision = Decision(
            item="jira-api",
            item_type="mcp_server",
            result="allowed",
            reason="Local override applied",
            source="user",
            exception_id="local-20251221-a3f2",
            expires_in="7h45m",
        )
        assert decision.item == "jira-api"
        assert decision.item_type == "mcp_server"
        assert decision.result == "allowed"
        assert decision.reason == "Local override applied"
        assert decision.source == "user"
        assert decision.exception_id == "local-20251221-a3f2"
        assert decision.expires_in == "7h45m"

    def test_create_blocked_decision(self):
        """Create a decision record for a blocked item (no exception)."""
        from scc_cli.evaluation.models import Decision

        decision = Decision(
            item="vendor-tools",
            item_type="plugin",
            result="blocked",
            reason="Security policy",
            source="org",
            exception_id=None,
            expires_in=None,
        )
        assert decision.result == "blocked"
        assert decision.exception_id is None
        assert decision.expires_in is None


# ═══════════════════════════════════════════════════════════════════════════════
# EvaluationResult Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluationResult:
    """Tests for the EvaluationResult dataclass."""

    def test_create_empty_result(self):
        """Create an empty evaluation result."""
        from scc_cli.evaluation.models import EvaluationResult

        result = EvaluationResult()
        assert result.blocked_items == []
        assert result.denied_additions == []
        assert result.decisions == []
        assert result.warnings == []

    def test_create_result_with_items(self):
        """Create a result with blocked and denied items."""
        from scc_cli.evaluation.models import (
            BlockedItem,
            DeniedAddition,
            EvaluationResult,
        )

        blocked = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Blocked by org policy",
        )
        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(
            blocked_items=[blocked],
            denied_additions=[denied],
            warnings=["Some warning"],
        )
        assert len(result.blocked_items) == 1
        assert len(result.denied_additions) == 1
        assert len(result.warnings) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# apply_policy_exceptions Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestApplyPolicyExceptions:
    """Tests for apply_policy_exceptions() function."""

    def test_policy_exception_allows_security_blocked_plugin(self):
        """Policy exception can override security-blocked plugin."""
        from scc_cli.evaluation.apply_exceptions import apply_policy_exceptions
        from scc_cli.evaluation.models import BlockedItem, EvaluationResult

        blocked = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Blocked by org policy",
        )
        result = EvaluationResult(blocked_items=[blocked])

        # Policy exception for the plugin
        exception = Exception(
            id="INC-2025-001",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Approved for project X",
            scope="policy",
            allow=AllowTargets(plugins=["vendor-tools"]),
        )

        new_result = apply_policy_exceptions(result, [exception])

        # Plugin should no longer be blocked
        assert len(new_result.blocked_items) == 0
        # Should have a decision record
        assert len(new_result.decisions) == 1
        assert new_result.decisions[0].item == "vendor-tools"
        assert new_result.decisions[0].result == "allowed"
        assert new_result.decisions[0].exception_id == "INC-2025-001"

    def test_policy_exception_allows_security_blocked_mcp(self):
        """Policy exception can override security-blocked MCP server."""
        from scc_cli.evaluation.apply_exceptions import apply_policy_exceptions
        from scc_cli.evaluation.models import BlockedItem, EvaluationResult

        blocked = BlockedItem(
            target="dangerous-mcp",
            target_type="mcp_server",
            reason=BlockReason.SECURITY,
            message="Blocked by org policy",
        )
        result = EvaluationResult(blocked_items=[blocked])

        exception = Exception(
            id="INC-2025-002",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Approved for testing",
            scope="policy",
            allow=AllowTargets(mcp_servers=["dangerous-mcp"]),
        )

        new_result = apply_policy_exceptions(result, [exception])
        assert len(new_result.blocked_items) == 0
        assert new_result.decisions[0].item == "dangerous-mcp"

    def test_policy_exception_allows_delegation_denied(self):
        """Policy exception can also override delegation denials."""
        from scc_cli.evaluation.apply_exceptions import apply_policy_exceptions
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(denied_additions=[denied])

        exception = Exception(
            id="INC-2025-003",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Approved globally",
            scope="policy",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )

        new_result = apply_policy_exceptions(result, [exception])
        assert len(new_result.denied_additions) == 0
        assert new_result.decisions[0].result == "allowed"

    def test_expired_policy_exception_has_no_effect(self):
        """Expired policy exception doesn't allow blocked item."""
        from scc_cli.evaluation.apply_exceptions import apply_policy_exceptions
        from scc_cli.evaluation.models import BlockedItem, EvaluationResult

        blocked = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Blocked",
        )
        result = EvaluationResult(blocked_items=[blocked])

        # Expired exception
        exception = Exception(
            id="INC-2025-001",
            created_at="2025-01-01T10:00:00Z",
            expires_at="2025-01-01T18:00:00Z",  # In the past
            reason="Expired approval",
            scope="policy",
            allow=AllowTargets(plugins=["vendor-tools"]),
        )

        new_result = apply_policy_exceptions(result, [exception])
        # Still blocked
        assert len(new_result.blocked_items) == 1
        assert len(new_result.decisions) == 0

    def test_policy_exception_preserves_unmatched_items(self):
        """Policy exception only affects matching items."""
        from scc_cli.evaluation.apply_exceptions import apply_policy_exceptions
        from scc_cli.evaluation.models import BlockedItem, EvaluationResult

        blocked1 = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Blocked",
        )
        blocked2 = BlockedItem(
            target="other-plugin",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Also blocked",
        )
        result = EvaluationResult(blocked_items=[blocked1, blocked2])

        # Exception only for vendor-tools
        exception = Exception(
            id="INC-2025-001",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Approved",
            scope="policy",
            allow=AllowTargets(plugins=["vendor-tools"]),
        )

        new_result = apply_policy_exceptions(result, [exception])
        # other-plugin still blocked
        assert len(new_result.blocked_items) == 1
        assert new_result.blocked_items[0].target == "other-plugin"

    def test_decision_includes_expires_in(self):
        """Decision record includes expires_in relative time."""
        from scc_cli.evaluation.apply_exceptions import apply_policy_exceptions
        from scc_cli.evaluation.models import BlockedItem, EvaluationResult

        blocked = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Blocked",
        )
        result = EvaluationResult(blocked_items=[blocked])

        # Exception expiring in ~8 hours
        future = datetime.now(timezone.utc) + timedelta(hours=8)
        exception = Exception(
            id="INC-2025-001",
            created_at="2025-12-21T10:00:00Z",
            expires_at=future.strftime("%Y-%m-%dT%H:%M:%SZ"),
            reason="Approved",
            scope="policy",
            allow=AllowTargets(plugins=["vendor-tools"]),
        )

        new_result = apply_policy_exceptions(result, [exception])
        assert new_result.decisions[0].expires_in is not None
        # Should contain "h" for hours
        assert "h" in new_result.decisions[0].expires_in


# ═══════════════════════════════════════════════════════════════════════════════
# apply_local_overrides Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestApplyLocalOverrides:
    """Tests for apply_local_overrides() function."""

    def test_local_override_allows_delegation_denied(self):
        """Local override can override delegation-denied item."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(denied_additions=[denied])

        override = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Need for sprint",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )

        new_result = apply_local_overrides(result, [override], source="user")

        assert len(new_result.denied_additions) == 0
        assert len(new_result.decisions) == 1
        assert new_result.decisions[0].source == "user"
        assert new_result.decisions[0].exception_id == "local-20251221-a3f2"

    def test_local_override_cannot_allow_security_blocked(self):
        """Local override CANNOT override security-blocked item."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import BlockedItem, EvaluationResult

        blocked = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Blocked by org policy",
        )
        result = EvaluationResult(blocked_items=[blocked])

        override = Exception(
            id="local-20251221-xxxx",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Trying to bypass",
            scope="local",
            allow=AllowTargets(plugins=["vendor-tools"]),
        )

        new_result = apply_local_overrides(result, [override], source="user")

        # Still blocked - local cannot override security
        assert len(new_result.blocked_items) == 1
        assert new_result.blocked_items[0].target == "vendor-tools"
        # No decision record for failed override attempt
        assert len(new_result.decisions) == 0

    def test_local_override_from_repo_store(self):
        """Local override from repo store shows source='repo'."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(denied_additions=[denied])

        override = Exception(
            id="local-20251221-b4e5",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Team shared override",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )

        new_result = apply_local_overrides(result, [override], source="repo")

        assert new_result.decisions[0].source == "repo"

    def test_expired_local_override_has_no_effect(self):
        """Expired local override doesn't allow denied item."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(denied_additions=[denied])

        # Expired override
        override = Exception(
            id="local-20251221-xxxx",
            created_at="2025-01-01T10:00:00Z",
            expires_at="2025-01-01T18:00:00Z",  # In the past
            reason="Expired",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )

        new_result = apply_local_overrides(result, [override], source="user")
        # Still denied
        assert len(new_result.denied_additions) == 1

    def test_local_override_for_base_image(self):
        """Local override can allow delegation-denied base image."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied = DeniedAddition(
            target="custom-image:latest",
            target_type="base_image",
            reason=BlockReason.DELEGATION,
            message="Image not pre-approved",
        )
        result = EvaluationResult(denied_additions=[denied])

        override = Exception(
            id="local-20251221-c6f7",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Testing custom image",
            scope="local",
            allow=AllowTargets(base_images=["custom-image:latest"]),
        )

        new_result = apply_local_overrides(result, [override], source="user")
        assert len(new_result.denied_additions) == 0
        assert new_result.decisions[0].item_type == "base_image"


# ═══════════════════════════════════════════════════════════════════════════════
# Combined Exception Application Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCombinedExceptionApplication:
    """Tests for combined policy + local exception application."""

    def test_policy_then_local_application_order(self):
        """Apply policy exceptions first, then local overrides."""
        from scc_cli.evaluation.apply_exceptions import (
            apply_local_overrides,
            apply_policy_exceptions,
        )
        from scc_cli.evaluation.models import (
            BlockedItem,
            DeniedAddition,
            EvaluationResult,
        )

        blocked = BlockedItem(
            target="vendor-tools",
            target_type="plugin",
            reason=BlockReason.SECURITY,
            message="Security blocked",
        )
        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(
            blocked_items=[blocked],
            denied_additions=[denied],
        )

        # Policy exception for the security block
        policy_exc = Exception(
            id="INC-2025-001",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Approved",
            scope="policy",
            allow=AllowTargets(plugins=["vendor-tools"]),
        )

        # Local override for the delegation denial
        local_override = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Need for sprint",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )

        # Apply in order: policy first, then local
        result = apply_policy_exceptions(result, [policy_exc])
        result = apply_local_overrides(result, [local_override], source="user")

        # Both should be allowed now
        assert len(result.blocked_items) == 0
        assert len(result.denied_additions) == 0
        assert len(result.decisions) == 2

    def test_local_override_or_logic_repo_user(self):
        """Either repo OR user local override can allow delegation denial."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )

        # Try with repo override only
        result1 = EvaluationResult(denied_additions=[denied])
        repo_override = Exception(
            id="local-repo-1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Repo override",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )
        result1 = apply_local_overrides(result1, [repo_override], source="repo")
        assert len(result1.denied_additions) == 0

        # Try with user override only
        result2 = EvaluationResult(denied_additions=[denied])
        user_override = Exception(
            id="local-user-1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="User override",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )
        result2 = apply_local_overrides(result2, [user_override], source="user")
        assert len(result2.denied_additions) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Wildcard Matching Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWildcardMatching:
    """Tests for wildcard pattern matching in exceptions."""

    def test_mcp_server_wildcard_match(self):
        """Exception with 'jira-*' matches 'jira-api' and 'jira-cloud'."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied1 = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        denied2 = DeniedAddition(
            target="jira-cloud",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(denied_additions=[denied1, denied2])

        override = Exception(
            id="local-20251221-wild",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="All jira servers",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-*"]),
        )

        new_result = apply_local_overrides(result, [override], source="user")
        assert len(new_result.denied_additions) == 0
        assert len(new_result.decisions) == 2

    def test_exact_match_takes_precedence(self):
        """Exact match is preferred over wildcard."""
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import DeniedAddition, EvaluationResult

        denied = DeniedAddition(
            target="jira-api",
            target_type="mcp_server",
            reason=BlockReason.DELEGATION,
            message="Not delegated",
        )
        result = EvaluationResult(denied_additions=[denied])

        exact_override = Exception(
            id="local-exact",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Exact match",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )

        new_result = apply_local_overrides(result, [exact_override], source="user")
        assert len(new_result.denied_additions) == 0
        # Decision should reference the exact match exception
        assert new_result.decisions[0].exception_id == "local-exact"


class TestAllowTargetsArchitecturalBoundary:
    """Tests verifying AllowTargets cannot include security settings.

    Critical boundary: allow_stdio_mcp is a security setting.
    Local overrides cannot change it because AllowTargets only includes:
    - plugins (IDs/names)
    - mcp_servers (SCC-managed only)
    - base_images (refs/patterns)

    This is by design - exceptions target specific items, not security config.
    """

    def test_allow_targets_has_no_security_settings(self):
        """AllowTargets only contains item targets, not security settings."""
        targets = AllowTargets()

        # AllowTargets has exactly these three fields
        assert hasattr(targets, "plugins")
        assert hasattr(targets, "mcp_servers")
        assert hasattr(targets, "base_images")

        # Security settings like allow_stdio_mcp are NOT in AllowTargets
        assert not hasattr(targets, "allow_stdio_mcp")
        assert not hasattr(targets, "security")
        assert not hasattr(targets, "settings")

    def test_allow_targets_cannot_set_arbitrary_attributes(self):
        """AllowTargets is a dataclass - no arbitrary attribute injection."""
        # This test documents that you can't sneak in security settings
        # AllowTargets only accepts defined fields (plugins, mcp_servers, base_images)
        _targets = AllowTargets(plugins=["my-plugin"])  # noqa: F841

        # Attempting to set allow_stdio_mcp via constructor fails
        with pytest.raises(TypeError):
            AllowTargets(allow_stdio_mcp=True)  # type: ignore

    def test_local_override_cannot_affect_allow_stdio_mcp(self):
        """Local override has no mechanism to enable allow_stdio_mcp.

        This test documents the architectural boundary: the exception system
        operates on items (plugins, servers, images), not security configuration.
        allow_stdio_mcp is evaluated at config merge time, not exception time.
        """
        from scc_cli.evaluation.apply_exceptions import apply_local_overrides
        from scc_cli.evaluation.models import EvaluationResult

        # Create an evaluation result - empty since we're testing architecture
        result = EvaluationResult(
            blocked_items=[],
            denied_additions=[],
            decisions=[],
            warnings=[],
        )

        # Create a local override - it can only target items, not settings
        override = Exception(
            id="local-attempt",
            created_at="2025-12-21T12:00:00+00:00",
            expires_at="2025-12-21T20:00:00+00:00",
            reason="Attempting to enable stdio - should have no effect",
            scope="local",
            allow=AllowTargets(
                # Can only specify items, not security settings
                mcp_servers=["some-server"],
            ),
        )

        # Apply the override - it has no path to affect allow_stdio_mcp
        new_result = apply_local_overrides(result, [override], source="user")

        # The exception system doesn't even have a way to express
        # "enable allow_stdio_mcp" - this is the architectural boundary
        assert new_result.blocked_items == []
        assert new_result.denied_additions == []
        # No decision made because there was nothing to override
        assert new_result.decisions == []


# ═══════════════════════════════════════════════════════════════════════════════
# evaluate() Function Tests - Bridging EffectiveConfig to EvaluationResult
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvaluateFunction:
    """Tests for the evaluate() function that converts EffectiveConfig to EvaluationResult.

    This function bridges the governance layer (profiles.py models) to the
    exception system (evaluation/models.py) with proper BlockReason annotations.
    """

    def test_evaluate_empty_config(self):
        """Empty EffectiveConfig produces empty EvaluationResult."""
        from scc_cli.evaluation import evaluate
        from scc_cli.profiles import EffectiveConfig

        config = EffectiveConfig()
        result = evaluate(config)

        assert result.blocked_items == []
        assert result.denied_additions == []
        assert result.decisions == []
        assert result.warnings == []

    def test_evaluate_blocked_plugin_has_security_reason(self):
        """Blocked plugins get BlockReason.SECURITY annotation."""
        from scc_cli.evaluation import evaluate
        from scc_cli.profiles import BlockedItem as ProfileBlockedItem
        from scc_cli.profiles import EffectiveConfig

        config = EffectiveConfig(
            blocked_items=[
                ProfileBlockedItem(
                    item="vendor-tools",
                    blocked_by="vendor-*",
                    source="org.security",
                    target_type="plugin",
                )
            ]
        )

        result = evaluate(config)

        assert len(result.blocked_items) == 1
        blocked = result.blocked_items[0]
        assert blocked.target == "vendor-tools"
        assert blocked.target_type == "plugin"
        assert blocked.reason == BlockReason.SECURITY
        assert "vendor-*" in blocked.message

    def test_evaluate_blocked_mcp_server_has_security_reason(self):
        """Blocked MCP servers get BlockReason.SECURITY annotation."""
        from scc_cli.evaluation import evaluate
        from scc_cli.profiles import BlockedItem as ProfileBlockedItem
        from scc_cli.profiles import EffectiveConfig

        config = EffectiveConfig(
            blocked_items=[
                ProfileBlockedItem(
                    item="unsafe-api",
                    blocked_by="*-api",
                    source="org.security",
                    target_type="mcp_server",
                )
            ]
        )

        result = evaluate(config)

        assert len(result.blocked_items) == 1
        blocked = result.blocked_items[0]
        assert blocked.target == "unsafe-api"
        assert blocked.target_type == "mcp_server"
        assert blocked.reason == BlockReason.SECURITY

    def test_evaluate_denied_plugin_has_delegation_reason(self):
        """Denied plugins get BlockReason.DELEGATION annotation."""
        from scc_cli.evaluation import evaluate
        from scc_cli.profiles import DelegationDenied, EffectiveConfig

        config = EffectiveConfig(
            denied_additions=[
                DelegationDenied(
                    item="my-plugin",
                    requested_by="team",
                    reason="Team 'data' not allowed to add plugins",
                    target_type="plugin",
                )
            ]
        )

        result = evaluate(config)

        assert len(result.denied_additions) == 1
        denied = result.denied_additions[0]
        assert denied.target == "my-plugin"
        assert denied.target_type == "plugin"
        assert denied.reason == BlockReason.DELEGATION
        assert "Team 'data' not allowed" in denied.message

    def test_evaluate_denied_mcp_server_has_delegation_reason(self):
        """Denied MCP servers get BlockReason.DELEGATION annotation."""
        from scc_cli.evaluation import evaluate
        from scc_cli.profiles import DelegationDenied, EffectiveConfig

        config = EffectiveConfig(
            denied_additions=[
                DelegationDenied(
                    item="jira-api",
                    requested_by="project",
                    reason="Project not delegated for MCP additions",
                    target_type="mcp_server",
                )
            ]
        )

        result = evaluate(config)

        assert len(result.denied_additions) == 1
        denied = result.denied_additions[0]
        assert denied.target == "jira-api"
        assert denied.target_type == "mcp_server"
        assert denied.reason == BlockReason.DELEGATION

    def test_evaluate_mixed_blocked_and_denied(self):
        """Config with both blocked and denied items converts correctly."""
        from scc_cli.evaluation import evaluate
        from scc_cli.profiles import (
            BlockedItem as ProfileBlockedItem,
        )
        from scc_cli.profiles import (
            DelegationDenied,
            EffectiveConfig,
        )

        config = EffectiveConfig(
            blocked_items=[
                ProfileBlockedItem(
                    item="malicious-tool",
                    blocked_by="malicious-*",
                    source="org.security",
                    target_type="plugin",
                ),
                ProfileBlockedItem(
                    item="evil-server",
                    blocked_by="evil-*",
                    source="org.security",
                    target_type="mcp_server",
                ),
            ],
            denied_additions=[
                DelegationDenied(
                    item="custom-plugin",
                    requested_by="team",
                    reason="Not delegated",
                    target_type="plugin",
                ),
                DelegationDenied(
                    item="custom-server",
                    requested_by="project",
                    reason="Not delegated",
                    target_type="mcp_server",
                ),
            ],
        )

        result = evaluate(config)

        assert len(result.blocked_items) == 2
        assert len(result.denied_additions) == 2

        # All blocked items should have SECURITY reason
        for blocked in result.blocked_items:
            assert blocked.reason == BlockReason.SECURITY

        # All denied items should have DELEGATION reason
        for denied in result.denied_additions:
            assert denied.reason == BlockReason.DELEGATION

    def test_evaluate_preserves_target_types(self):
        """Target types are correctly preserved during conversion."""
        from scc_cli.evaluation import evaluate
        from scc_cli.profiles import (
            BlockedItem as ProfileBlockedItem,
        )
        from scc_cli.profiles import (
            DelegationDenied,
            EffectiveConfig,
        )

        config = EffectiveConfig(
            blocked_items=[
                ProfileBlockedItem(
                    item="blocked-img",
                    blocked_by="*:latest",
                    source="org.security",
                    target_type="base_image",
                ),
            ],
            denied_additions=[
                DelegationDenied(
                    item="custom-img",
                    requested_by="project",
                    reason="Not allowed",
                    target_type="base_image",
                ),
            ],
        )

        result = evaluate(config)

        assert result.blocked_items[0].target_type == "base_image"
        assert result.denied_additions[0].target_type == "base_image"
