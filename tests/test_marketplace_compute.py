"""
Unit tests for effective plugin computation.

TDD: Tests written before implementation.
Tests cover:
- BlockedPlugin dataclass
- EffectivePlugins dataclass
- compute_effective_plugins() pure function logic
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from scc_cli.marketplace.schema import DelegationConfig, OrganizationConfig, TeamProfile


def make_org_config(**kwargs: Any) -> OrganizationConfig:
    from scc_cli.marketplace.schema import OrganizationConfig, OrganizationInfo

    organization = kwargs.pop(
        "organization",
        OrganizationInfo(name="Test Org", id="test-org"),
    )
    schema_version = kwargs.pop("schema_version", "1.0.0")
    return OrganizationConfig(
        schema_version=schema_version,
        organization=organization,
        **kwargs,
    )


def make_team_profile(**kwargs: Any) -> TeamProfile:
    from scc_cli.marketplace.schema import TeamProfile

    return TeamProfile(**kwargs)


def allow_all_delegation() -> DelegationConfig:
    from scc_cli.marketplace.schema import DelegationConfig, DelegationTeamsConfig

    return DelegationConfig(
        teams=DelegationTeamsConfig(allow_additional_plugins=["*"]),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BlockedPlugin Dataclass Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockedPlugin:
    """Tests for BlockedPlugin dataclass."""

    def test_create_blocked_plugin(self) -> None:
        """BlockedPlugin should store plugin_id, reason, and pattern."""
        from scc_cli.marketplace.compute import BlockedPlugin

        blocked = BlockedPlugin(
            plugin_id="risky-tool@internal",
            reason="Security review pending",
            pattern="risky-*@*",
        )
        assert blocked.plugin_id == "risky-tool@internal"
        assert blocked.reason == "Security review pending"
        assert blocked.pattern == "risky-*@*"

    def test_blocked_plugin_equality(self) -> None:
        """Two BlockedPlugins with same values should be equal."""
        from scc_cli.marketplace.compute import BlockedPlugin

        b1 = BlockedPlugin(plugin_id="x@y", reason="test", pattern="*")
        b2 = BlockedPlugin(plugin_id="x@y", reason="test", pattern="*")
        assert b1 == b2

    def test_blocked_plugin_immutable(self) -> None:
        """BlockedPlugin should be frozen (immutable)."""
        from scc_cli.marketplace.compute import BlockedPlugin

        blocked = BlockedPlugin(plugin_id="x@y", reason="test", pattern="*")
        with pytest.raises(AttributeError):
            blocked.plugin_id = "new@value"  # type: ignore[misc]


# ═══════════════════════════════════════════════════════════════════════════════
# EffectivePlugins Dataclass Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestEffectivePlugins:
    """Tests for EffectivePlugins dataclass."""

    def test_create_effective_plugins(self) -> None:
        """EffectivePlugins should have all required fields."""
        from scc_cli.marketplace.compute import BlockedPlugin, EffectivePlugins

        effective = EffectivePlugins(
            enabled={"code-review@internal", "linter@internal"},
            blocked=[
                BlockedPlugin(
                    plugin_id="risky@internal",
                    reason="Blocked by policy",
                    pattern="risky@*",
                )
            ],
            not_allowed=["debug-tool@internal"],
            disabled=["deprecated@internal"],
            extra_marketplaces=["experimental"],
        )
        assert "code-review@internal" in effective.enabled
        assert len(effective.blocked) == 1
        assert effective.not_allowed == ["debug-tool@internal"]
        assert effective.disabled == ["deprecated@internal"]
        assert "experimental" in effective.extra_marketplaces

    def test_effective_plugins_defaults(self) -> None:
        """EffectivePlugins should have sensible defaults."""
        from scc_cli.marketplace.compute import EffectivePlugins

        effective = EffectivePlugins()
        assert effective.enabled == set()
        assert effective.blocked == []
        assert effective.not_allowed == []
        assert effective.disabled == []
        assert effective.extra_marketplaces == []


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Basic Scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsBasic:
    """Tests for compute_effective_plugins() basic functionality."""

    def test_minimal_config_returns_empty(self) -> None:
        """Minimal config with no plugins should return empty effective plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins

        config = make_org_config(
            profiles={"base": make_team_profile()},
        )
        result = compute_effective_plugins(config, team_id="base")

        assert result.enabled == set()
        assert result.blocked == []
        assert result.not_allowed == []
        assert result.disabled == []

    def test_defaults_enabled_plugins_are_included(self) -> None:
        """Defaults enabled_plugins should appear in effective.enabled."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal", "linter@internal"],
            ),
            profiles={"backend": make_team_profile()},
        )
        result = compute_effective_plugins(config, team_id="backend")

        assert "code-review@internal" in result.enabled
        assert "linter@internal" in result.enabled

    def test_team_not_found_raises_error(self) -> None:
        """compute_effective_plugins should raise for unknown team_id."""
        from scc_cli.marketplace.compute import (
            TeamNotFoundError,
            compute_effective_plugins,
        )

        config = make_org_config(
            profiles={"backend": make_team_profile()},
        )

        with pytest.raises(TeamNotFoundError) as exc_info:
            compute_effective_plugins(config, team_id="nonexistent")

        assert "nonexistent" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Plugin Merging
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsMerging:
    """Tests for plugin merging in compute_effective_plugins()."""

    def test_profile_additional_plugins_merged_with_defaults(self) -> None:
        """Profile additional_plugins should be merged with defaults.enabled_plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "backend": make_team_profile(
                    additional_plugins=["api-tools@internal"],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="backend")

        # Should have both defaults and additional
        assert "code-review@internal" in result.enabled
        assert "api-tools@internal" in result.enabled
        assert len(result.enabled) == 2

    def test_duplicate_plugins_are_deduplicated(self) -> None:
        """Same plugin in defaults and additional should appear only once."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "backend": make_team_profile(
                    additional_plugins=["code-review@internal"],  # duplicate
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="backend")

        assert "code-review@internal" in result.enabled
        assert len(result.enabled) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Disabled Plugins
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsDisabled:
    """Tests for disabled_plugins pattern matching."""

    def test_disabled_pattern_removes_matching_plugins(self) -> None:
        """Profile disabled_plugins should remove matching plugins from enabled."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["debug-tool@internal", "code-review@internal"],
                disabled_plugins=["debug-*@*"],
            ),
            profiles={
                "production": make_team_profile(),
            },
        )
        result = compute_effective_plugins(config, team_id="production")

        # debug-tool should be disabled
        assert "debug-tool@internal" not in result.enabled
        assert "debug-tool@internal" in result.disabled
        # code-review should remain
        assert "code-review@internal" in result.enabled

    def test_disabled_exact_match(self) -> None:
        """Exact plugin name should work as disabled pattern."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["tool-a@internal", "tool-b@internal"],
                disabled_plugins=["tool-a@internal"],
            ),
            profiles={
                "minimal": make_team_profile(),
            },
        )
        result = compute_effective_plugins(config, team_id="minimal")

        assert "tool-a@internal" not in result.enabled
        assert "tool-a@internal" in result.disabled
        assert "tool-b@internal" in result.enabled


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Allowed Plugins (Allowlist)
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsAllowed:
    """Tests for allowed_plugins allowlist filtering."""

    def test_allowed_plugins_null_means_allow_all(self) -> None:
        """allowed_plugins=None should allow all plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal", "linter@internal"],
                allowed_plugins=None,
            ),
            delegation=allow_all_delegation(),
            profiles={
                "open": make_team_profile(
                    additional_plugins=["extra-tool@internal"],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="open")

        assert "code-review@internal" in result.enabled
        assert "linter@internal" in result.enabled
        assert "extra-tool@internal" in result.enabled
        assert result.not_allowed == []

    def test_allowed_plugins_empty_list_blocks_additional(self) -> None:
        """allowed_plugins=[] should block all team additional plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal"],
                allowed_plugins=[],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "locked": make_team_profile(
                    additional_plugins=["extra-tool@internal"],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="locked")

        # Defaults should still be there
        assert "code-review@internal" in result.enabled
        # Additional should be blocked
        assert "extra-tool@internal" not in result.enabled
        assert "extra-tool@internal" in result.not_allowed

    def test_allowed_plugins_filters_additional(self) -> None:
        """Only additional plugins in allowed_plugins list should be enabled."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal"],
                allowed_plugins=["api-tools@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "restricted": make_team_profile(
                    additional_plugins=["api-tools@internal", "risky-tool@internal"],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="restricted")

        # Defaults always allowed
        assert "code-review@internal" in result.enabled
        # Allowed additional
        assert "api-tools@internal" in result.enabled
        # Not allowed additional
        assert "risky-tool@internal" not in result.enabled
        assert "risky-tool@internal" in result.not_allowed


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Blocked Plugins (Security)
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsBlocked:
    """Tests for security.blocked_plugins enforcement."""

    def test_blocked_plugins_removes_from_enabled(self) -> None:
        """Security blocked_plugins should remove matching plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig, SecurityConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal", "risky-tool@internal"],
            ),
            security=SecurityConfig(
                blocked_plugins=["risky-*@*"],
            ),
            profiles={
                "backend": make_team_profile(),
            },
        )
        result = compute_effective_plugins(config, team_id="backend")

        # risky-tool should be blocked
        assert "risky-tool@internal" not in result.enabled
        assert len(result.blocked) == 1
        assert result.blocked[0].plugin_id == "risky-tool@internal"
        assert result.blocked[0].reason == "Blocked by security policy"
        assert result.blocked[0].pattern == "risky-*@*"
        # code-review should remain
        assert "code-review@internal" in result.enabled

    def test_blocked_applies_to_additional_plugins(self) -> None:
        """Blocked patterns should also apply to profile additional_plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import SecurityConfig

        config = make_org_config(
            security=SecurityConfig(
                blocked_plugins=["dangerous-*@*"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "dev": make_team_profile(
                    additional_plugins=["dangerous-util@internal", "safe-tool@internal"],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="dev")

        assert "dangerous-util@internal" not in result.enabled
        assert "safe-tool@internal" in result.enabled
        assert len(result.blocked) == 1

    def test_blocked_takes_precedence_over_allowed(self) -> None:
        """Blocked plugins should be blocked even if in allowed_plugins list."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig, SecurityConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                allowed_plugins=["evil@internal"],
            ),
            security=SecurityConfig(
                blocked_plugins=["evil@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "team": make_team_profile(
                    additional_plugins=["evil@internal"],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="team")

        assert "evil@internal" not in result.enabled
        assert len(result.blocked) == 1
        assert result.blocked[0].plugin_id == "evil@internal"


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Extra Marketplaces
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsMarketplaces:
    """Tests for extra_marketplaces collection."""

    def test_defaults_extra_marketplaces_included(self) -> None:
        """Defaults extra_marketplaces should appear in result."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                extra_marketplaces=["experimental"],
            ),
            profiles={
                "team": make_team_profile(),
            },
        )
        result = compute_effective_plugins(config, team_id="team")

        assert "experimental" in result.extra_marketplaces

    def test_duplicate_marketplaces_are_deduplicated(self) -> None:
        """Same marketplace in defaults and profile should appear once."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                extra_marketplaces=["shared", "shared"],
            ),
            profiles={
                "team": make_team_profile(),
            },
        )
        result = compute_effective_plugins(config, team_id="team")

        assert result.extra_marketplaces.count("shared") == 1


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Plugin Normalization
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsNormalization:
    """Tests for plugin reference normalization during computation."""

    def test_bare_plugin_name_auto_resolves_single_marketplace(self) -> None:
        """Bare plugin name should auto-resolve when org has 1 marketplace."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig, MarketplaceSourceGitHub

        config = make_org_config(
            marketplaces={
                "internal": MarketplaceSourceGitHub(
                    source="github",
                    owner="org",
                    repo="plugins",
                ),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["code-review"],  # bare name, no @marketplace
            ),
            profiles={
                "team": make_team_profile(),
            },
        )
        result = compute_effective_plugins(config, team_id="team")

        # Should auto-resolve to code-review@internal
        assert "code-review@internal" in result.enabled

    def test_bare_plugin_name_resolves_to_official_when_no_marketplaces(self) -> None:
        """Bare plugin name should resolve to claude-plugins-official when 0 org marketplaces."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            marketplaces={},  # no org marketplaces
            defaults=DefaultsConfig(
                enabled_plugins=["code-review"],  # bare name
            ),
            profiles={
                "team": make_team_profile(),
            },
        )
        result = compute_effective_plugins(config, team_id="team")

        # Should resolve to official marketplace
        assert "code-review@claude-plugins-official" in result.enabled

    def test_ambiguous_plugin_raises_error(self) -> None:
        """Bare plugin name with 2+ org marketplaces should raise error."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.normalize import AmbiguousMarketplaceError
        from scc_cli.marketplace.schema import DefaultsConfig, MarketplaceSourceGitHub

        config = make_org_config(
            marketplaces={
                "internal": MarketplaceSourceGitHub(
                    source="github",
                    owner="org1",
                    repo="plugins",
                ),
                "external": MarketplaceSourceGitHub(
                    source="github",
                    owner="org2",
                    repo="plugins",
                ),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["ambiguous-tool"],  # bare name, 2 marketplaces!
            ),
            profiles={
                "team": make_team_profile(),
            },
        )

        with pytest.raises(AmbiguousMarketplaceError):
            compute_effective_plugins(config, team_id="team")


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins Tests - Full Workflow
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsFullWorkflow:
    """Integration tests for complete plugin computation workflow."""

    def test_complex_scenario_with_all_features(self) -> None:
        """Full workflow: defaults + additional + allowlist + blocked + disabled."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import (
            DefaultsConfig,
            MarketplaceSourceGitHub,
            SecurityConfig,
        )

        config = make_org_config(
            marketplaces={
                "internal": MarketplaceSourceGitHub(
                    source="github",
                    owner="sundsvall",
                    repo="claude-plugins",
                ),
            },
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "code-review@internal",
                    "linter@internal",
                    "debug-tool@internal",
                ],
                disabled_plugins=["debug-*@*"],
                allowed_plugins=["api-tools@internal", "evil-plugin@internal"],
                extra_marketplaces=["experimental"],
            ),
            security=SecurityConfig(
                blocked_plugins=["evil-*@*"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "backend": make_team_profile(
                    description="Backend developers",
                    additional_plugins=[
                        "api-tools@internal",
                        "evil-plugin@internal",  # should be blocked
                    ],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="backend")

        # Enabled: defaults (code-review, linter) + allowed additional (api-tools)
        # minus disabled (debug-tool) minus blocked (evil-plugin)
        assert "code-review@internal" in result.enabled
        assert "linter@internal" in result.enabled
        assert "api-tools@internal" in result.enabled

        # Disabled: debug-tool matched debug-*@*
        assert "debug-tool@internal" in result.disabled
        assert "debug-tool@internal" not in result.enabled

        # Blocked: evil-plugin matched evil-*@*
        assert len(result.blocked) == 1
        assert result.blocked[0].plugin_id == "evil-plugin@internal"
        assert result.blocked[0].reason == "Blocked by security policy"

        # Extra marketplaces: defaults only
        assert "experimental" in result.extra_marketplaces

    def test_order_of_operations(self) -> None:
        """Verify: normalize → disable defaults → allowlist → block."""
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import DefaultsConfig, SecurityConfig

        # This test verifies the order of operations matters:
        # 1. Apply defaults.disabled_plugins
        # 2. Add delegated additional plugins (allowlist enforced)
        # 3. Apply security.blocked_plugins (final gate)

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["tool-a@internal", "tool-b@internal"],
                disabled_plugins=["tool-a@internal"],
                allowed_plugins=["tool-c@internal", "tool-d@internal"],
            ),
            security=SecurityConfig(
                blocked_plugins=["tool-c@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "team": make_team_profile(
                    additional_plugins=[
                        "tool-c@internal",
                        "tool-d@internal",
                        "tool-e@internal",
                    ],
                ),
            },
        )
        result = compute_effective_plugins(config, team_id="team")

        # tool-a: disabled by defaults
        assert "tool-a@internal" in result.disabled
        assert "tool-a@internal" not in result.enabled

        # tool-b: from defaults, not disabled, not blocked
        assert "tool-b@internal" in result.enabled

        # tool-c: allowed but blocked by security
        assert "tool-c@internal" not in result.enabled
        assert len(result.blocked) == 1
        assert result.blocked[0].plugin_id == "tool-c@internal"

        # tool-d: allowed additional, enabled
        assert "tool-d@internal" in result.enabled
        # tool-e: not allowlisted
        assert "tool-e@internal" in result.not_allowed

        # tool-e: not in allowlist, should be in not_allowed
        assert "tool-e@internal" not in result.enabled
        assert "tool-e@internal" in result.not_allowed


# ═══════════════════════════════════════════════════════════════════════════════
# compute_effective_plugins_federated() Tests (Federated)
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeEffectivePluginsFederated:
    """Tests for compute_effective_plugins_federated() with 6-step precedence."""

    def test_step1_org_defaults_enabled_plugins(self) -> None:
        """Step 1: Start with org defaults.enabled_plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import DefaultsConfig, TeamConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["default-plugin@internal"],
            ),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(schema_version="1.0.0")

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )
        assert "default-plugin@internal" in result.enabled

    def test_step2_team_config_enabled_plugins(self) -> None:
        """Step 2: Add team config enabled_plugins."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import DefaultsConfig, TeamConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["default-plugin@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["team-plugin@internal"],
        )

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )
        # Both org defaults and team plugins should be enabled
        assert "default-plugin@internal" in result.enabled
        assert "team-plugin@internal" in result.enabled

    def test_step3_team_config_disabled_plugins(self) -> None:
        """Step 3: Apply team config disabled_plugins patterns."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import DefaultsConfig, TeamConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["old-tool@internal", "new-tool@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(
            schema_version="1.0.0",
            disabled_plugins=["old-*@*"],  # Team disables old-* pattern
        )

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )
        # old-tool disabled by team, new-tool remains
        assert "old-tool@internal" not in result.enabled
        assert "old-tool@internal" in result.disabled
        assert "new-tool@internal" in result.enabled

    def test_step4_org_defaults_disabled_plugins(self) -> None:
        """Step 4: Apply org defaults.disabled_plugins patterns."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import DefaultsConfig, TeamConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                disabled_plugins=["legacy-*@*"],  # Org defaults disables legacy-*
            ),
            delegation=allow_all_delegation(),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["legacy-tool@internal", "modern-tool@internal"],
        )

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )
        # legacy-tool disabled by org defaults, modern-tool remains
        assert "legacy-tool@internal" not in result.enabled
        assert "legacy-tool@internal" in result.disabled
        assert "modern-tool@internal" in result.enabled

    def test_step5_allowed_plugins_enforced_for_federated(self) -> None:
        """Step 5: allowed_plugins filter applies to federated teams."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import DefaultsConfig, TeamConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                allowed_plugins=["only-this@internal"],
            ),
            delegation=allow_all_delegation(),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["other-plugin@internal"],  # Not in allowlist
        )

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )
        assert "other-plugin@internal" not in result.enabled
        assert "other-plugin@internal" in result.not_allowed

    def test_step6_security_blocked_always_enforced(self) -> None:
        """Step 6: Apply org security.blocked_plugins (ALWAYS enforced)."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import SecurityConfig, TeamConfig

        config = make_org_config(
            security=SecurityConfig(
                blocked_plugins=["risky-*@*"],
            ),
            delegation=allow_all_delegation(),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["risky-tool@internal", "safe-tool@internal"],
        )

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )
        # risky-tool blocked by security, safe-tool enabled
        assert "risky-tool@internal" not in result.enabled
        assert len(result.blocked) == 1
        assert result.blocked[0].plugin_id == "risky-tool@internal"
        assert result.blocked[0].reason == "Blocked by security policy"
        assert result.blocked[0].pattern == "risky-*@*"
        assert "safe-tool@internal" in result.enabled

    def test_full_6_step_precedence(self) -> None:
        """Complete test of all 6 steps in precedence order."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import DefaultsConfig, SecurityConfig, TeamConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["default-a@internal", "default-b@internal"],
                disabled_plugins=["team-disabled-by-org@*"],
            ),
            security=SecurityConfig(
                blocked_plugins=["blocked-*@*"],
            ),
            delegation=allow_all_delegation(),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=[
                "team-c@internal",
                "team-disabled-by-org@internal",
                "blocked-by-security@internal",
            ],
            disabled_plugins=["default-a@*"],  # Team disables default-a
        )

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )

        # Step 1: default-a, default-b from org defaults
        # Step 2: + team-c, team-disabled-by-org, blocked-by-security
        # Step 3: - default-a (disabled by team)
        # Step 4: - team-disabled-by-org (disabled by org defaults)
        # Step 5: skipped (federated)
        # Step 6: - blocked-by-security (blocked by security)

        assert "default-a@internal" in result.disabled  # Step 3
        assert "default-b@internal" in result.enabled  # Survives all steps
        assert "team-c@internal" in result.enabled  # Survives all steps
        assert "team-disabled-by-org@internal" in result.disabled  # Step 4
        assert len(result.blocked) == 1
        assert result.blocked[0].plugin_id == "blocked-by-security@internal"  # Step 6

    def test_team_not_found_raises_error(self) -> None:
        """Non-existent team should raise TeamNotFoundError."""
        from scc_cli.marketplace.compute import (
            TeamNotFoundError,
            compute_effective_plugins_federated,
        )
        from scc_cli.marketplace.schema import TeamConfig

        config = make_org_config(
            profiles={},
        )
        team_config = TeamConfig(schema_version="1.0.0")

        with pytest.raises(TeamNotFoundError) as exc_info:
            compute_effective_plugins_federated(
                config=config, team_id="unknown", team_config=team_config
            )
        assert exc_info.value.team_id == "unknown"

    def test_collects_extra_marketplaces_from_defaults(self) -> None:
        """Extra marketplaces should come from org defaults."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import DefaultsConfig, TeamConfig

        config = make_org_config(
            defaults=DefaultsConfig(extra_marketplaces=["org-mp"]),
            profiles={"backend": make_team_profile()},
            marketplaces={"internal": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(schema_version="1.0.0")

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )

        assert result.extra_marketplaces == ["org-mp"]

    def test_normalizes_plugin_references(self) -> None:
        """Plugin references should be normalized with marketplace resolution."""
        from scc_cli.marketplace.compute import compute_effective_plugins_federated
        from scc_cli.marketplace.schema import TeamConfig

        # Single marketplace - bare names should auto-resolve
        config = make_org_config(
            delegation=allow_all_delegation(),
            profiles={"backend": make_team_profile()},
            marketplaces={"only-one": {"source": "directory", "path": "/plugins"}},
        )
        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["bare-plugin"],  # Should resolve to @only-one
        )

        result = compute_effective_plugins_federated(
            config=config, team_id="backend", team_config=team_config
        )
        assert "bare-plugin@only-one" in result.enabled
