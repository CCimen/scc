"""Backwards compatibility tests for inline profiles after Phase 2 federation.

These tests verify that inline profiles (those without config_source) continue
to work exactly as they did in Phase 1. This ensures organizations that haven't
adopted federation experience no regressions.

Key guarantees:
- Inline profiles resolve to is_federated=False
- Plugin computation follows Phase 1 precedence rules
- Marketplace resolution works for org-defined marketplaces
- to_phase1_format() adapter produces compatible output
- Security filtering (blocked/allowed) works unchanged

Note on plugin schema:
- `defaults.enabled_plugins` - org-wide base plugins for all teams
- `profile.additional_plugins` - team-specific plugins added on top of defaults
- `profile.disabled_plugins` - patterns to remove from inherited defaults
- `profile.allowed_plugins` - allowlist filter for additional_plugins only
"""

from __future__ import annotations

from typing import Any

import pytest

from scc_cli.marketplace.compute import (
    EffectivePlugins,
    TeamNotFoundError,
    compute_effective_plugins,
)
from scc_cli.marketplace.resolve import resolve_effective_config
from scc_cli.marketplace.schema import (
    DefaultsConfig,
    MarketplaceSourceGitHub,
    OrganizationConfig,
    SecurityConfig,
    TeamProfile,
)

# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────


def _create_inline_org_config(
    *,
    profiles: dict[str, TeamProfile] | None = None,
    defaults: DefaultsConfig | None = None,
    security: SecurityConfig | None = None,
    marketplaces: dict[str, MarketplaceSourceGitHub] | None = None,
    include_default_marketplace: bool = True,
) -> OrganizationConfig:
    """Create an org config with inline profiles (no config_source).

    OrganizationConfig requires 'name' and 'schema_version' fields.
    Optional fields have default_factory, so we only pass them if not None.

    By default includes an 'internal' marketplace so plugins can reference it.
    Set include_default_marketplace=False to test without org marketplaces.

    For inline profiles, plugins come from:
    - defaults.enabled_plugins: org-wide base
    - profile.additional_plugins: team-specific additions
    """
    if profiles is None:
        profiles = {
            "dev": TeamProfile(name="Dev Team"),
        }

    # If no defaults provided, add some base plugins
    if defaults is None:
        defaults = DefaultsConfig(enabled_plugins=["tool@internal"])

    # Build kwargs - only include optional fields if they have values
    kwargs: dict[str, Any] = {
        "name": "Test Organization",
        "schema_version": 1,
        "profiles": profiles,
        "defaults": defaults,
    }
    if security is not None:
        kwargs["security"] = security
    if marketplaces is not None:
        kwargs["marketplaces"] = marketplaces
    elif include_default_marketplace:
        # Add default internal marketplace so plugins can reference @internal
        kwargs["marketplaces"] = {
            "internal": MarketplaceSourceGitHub(
                source="github", owner="test-org", repo="internal-plugins"
            ),
        }

    return OrganizationConfig(**kwargs)


# ─────────────────────────────────────────────────────────────────────────────
# Inline Profile Resolution Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInlineProfileResolution:
    """Test that inline profiles resolve correctly after federation changes."""

    def test_inline_profile_is_federated_false(self) -> None:
        """Inline profiles must have is_federated=False."""
        config = _create_inline_org_config()
        result = resolve_effective_config(config, "dev")

        assert result.is_federated is False
        assert result.config_source is None
        assert result.config_commit_sha is None
        assert result.config_etag is None

    def test_inline_profile_source_description(self) -> None:
        """Inline profiles must report 'inline' as source description."""
        config = _create_inline_org_config()
        result = resolve_effective_config(config, "dev")

        assert result.source_description == "inline"

    def test_inline_profile_team_id_preserved(self) -> None:
        """Team ID must be correctly set in result."""
        profiles = {
            "backend": TeamProfile(name="Backend"),
            "frontend": TeamProfile(name="Frontend"),
        }
        config = _create_inline_org_config(profiles=profiles)

        backend_result = resolve_effective_config(config, "backend")
        frontend_result = resolve_effective_config(config, "frontend")

        assert backend_result.team_id == "backend"
        assert frontend_result.team_id == "frontend"

    def test_nonexistent_team_raises_error(self) -> None:
        """Missing team must raise TeamNotFoundError."""
        config = _create_inline_org_config()

        with pytest.raises(TeamNotFoundError) as exc_info:
            resolve_effective_config(config, "nonexistent")

        assert exc_info.value.team_id == "nonexistent"
        assert "dev" in exc_info.value.available_teams


# ─────────────────────────────────────────────────────────────────────────────
# Plugin Computation Precedence Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInlinePluginPrecedence:
    """Test Phase 1 precedence rules work unchanged for inline profiles."""

    def test_team_additional_plugins_enabled(self) -> None:
        """Team-level additional_plugins must be included."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["tool-a@internal", "tool-b@internal"],
            ),
        }
        defaults = DefaultsConfig(enabled_plugins=[])  # No defaults
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        assert "tool-a@internal" in result.enabled_plugins
        assert "tool-b@internal" in result.enabled_plugins

    def test_defaults_plugins_inherited(self) -> None:
        """Defaults enabled_plugins must be inherited by teams."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["team-tool@internal"],
            )
        }
        defaults = DefaultsConfig(enabled_plugins=["default-tool@internal"])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        assert "team-tool@internal" in result.enabled_plugins
        assert "default-tool@internal" in result.enabled_plugins

    def test_team_disabled_removes_defaults(self) -> None:
        """Team disabled_plugins must remove plugins from defaults."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["team-tool@internal"],
                disabled_plugins=["unwanted@internal"],
            ),
        }
        defaults = DefaultsConfig(enabled_plugins=["unwanted@internal", "wanted@internal"])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        assert "unwanted@internal" not in result.enabled_plugins
        assert "wanted@internal" in result.enabled_plugins
        assert "unwanted@internal" in result.disabled_plugins

    def test_allowed_plugins_filters_additional(self) -> None:
        """Team allowed_plugins must filter additional_plugins.

        Note: allowed_plugins uses EXACT string matching, not glob patterns.
        This is by design - whitelists use exact match for security.
        """
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["allowed@internal", "blocked@internal"],
                allowed_plugins=["allowed@internal"],  # Exact match, not glob
            ),
        }
        defaults = DefaultsConfig(enabled_plugins=[])  # No defaults
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        assert "allowed@internal" in result.enabled_plugins
        assert "blocked@internal" not in result.enabled_plugins
        assert "blocked@internal" in result.not_allowed_plugins


# ─────────────────────────────────────────────────────────────────────────────
# Security Filtering Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInlineSecurityFiltering:
    """Test security filtering works unchanged for inline profiles."""

    def test_blocked_plugins_removed(self) -> None:
        """Security blocked_plugins must remove from enabled set."""
        defaults = DefaultsConfig(enabled_plugins=["safe@internal", "dangerous@internal"])
        profiles = {"dev": TeamProfile(name="Dev")}
        security = SecurityConfig(
            blocked_plugins=["dangerous@*"],
            blocked_reason="Security violation",
        )
        config = _create_inline_org_config(profiles=profiles, defaults=defaults, security=security)
        result = resolve_effective_config(config, "dev")

        assert "safe@internal" in result.enabled_plugins
        assert "dangerous@internal" not in result.enabled_plugins
        assert len(result.blocked_plugins) == 1
        assert result.blocked_plugins[0].plugin_id == "dangerous@internal"

    def test_blocked_plugin_details_preserved(self) -> None:
        """Blocked plugins must include reason and pattern."""
        defaults = DefaultsConfig(enabled_plugins=["banned@external"])
        profiles = {"dev": TeamProfile(name="Dev")}
        security = SecurityConfig(
            blocked_plugins=["*@external"],
            blocked_reason="External plugins not allowed",
        )
        # Need to add external marketplace for the plugin reference
        marketplaces = {
            "external": MarketplaceSourceGitHub(source="github", owner="vendor", repo="plugins"),
        }
        config = _create_inline_org_config(
            profiles=profiles,
            defaults=defaults,
            security=security,
            marketplaces=marketplaces,
        )
        result = resolve_effective_config(config, "dev")

        assert len(result.blocked_plugins) == 1
        blocked = result.blocked_plugins[0]
        assert blocked.plugin_id == "banned@external"
        assert blocked.pattern == "*@external"
        assert blocked.reason == "External plugins not allowed"

    def test_has_security_violations_property(self) -> None:
        """has_security_violations must reflect blocked_plugins state."""
        # No violations
        defaults = DefaultsConfig(enabled_plugins=["safe@internal"])
        profiles = {"dev": TeamProfile(name="Dev")}
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")
        assert result.has_security_violations is False

        # With violations
        security = SecurityConfig(blocked_plugins=["safe@*"])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults, security=security)
        result = resolve_effective_config(config, "dev")
        assert result.has_security_violations is True


# ─────────────────────────────────────────────────────────────────────────────
# Marketplace Resolution Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInlineMarketplaceResolution:
    """Test marketplace resolution works unchanged for inline profiles."""

    def test_org_marketplaces_included(self) -> None:
        """Org-defined marketplaces must be in effective marketplaces."""
        marketplaces = {
            "internal": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
        }
        config = _create_inline_org_config(marketplaces=marketplaces)
        result = resolve_effective_config(config, "dev")

        assert "internal" in result.marketplaces
        assert result.marketplaces["internal"] == marketplaces["internal"]

    def test_multiple_marketplaces_preserved(self) -> None:
        """Multiple org marketplaces must all be included."""
        marketplaces = {
            "internal": MarketplaceSourceGitHub(
                source="github", owner="org", repo="internal-plugins"
            ),
            "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="shared-plugins"),
            "external": MarketplaceSourceGitHub(source="github", owner="vendor", repo="plugins"),
        }
        config = _create_inline_org_config(marketplaces=marketplaces)
        result = resolve_effective_config(config, "dev")

        assert len(result.marketplaces) == 3
        assert "internal" in result.marketplaces
        assert "shared" in result.marketplaces
        assert "external" in result.marketplaces

    def test_extra_marketplaces_empty_for_inline(self) -> None:
        """Inline profiles should have empty extra_marketplaces."""
        config = _create_inline_org_config()
        result = resolve_effective_config(config, "dev")

        # extra_marketplaces is for team-defined marketplaces in federated mode
        assert result.extra_marketplaces == []


# ─────────────────────────────────────────────────────────────────────────────
# Phase 1 Compatibility Adapter Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestPhase1CompatibilityAdapter:
    """Test to_phase1_format() adapter produces compatible output."""

    def test_adapter_returns_tuple(self) -> None:
        """Adapter must return (EffectivePlugins, marketplaces) tuple."""
        config = _create_inline_org_config()
        result = resolve_effective_config(config, "dev")

        phase1_result = result.to_phase1_format()

        assert isinstance(phase1_result, tuple)
        assert len(phase1_result) == 2

    def test_adapter_effective_plugins_type(self) -> None:
        """First element must be EffectivePlugins dataclass."""
        config = _create_inline_org_config()
        result = resolve_effective_config(config, "dev")

        plugins, _ = result.to_phase1_format()

        assert isinstance(plugins, EffectivePlugins)

    def test_adapter_marketplaces_type(self) -> None:
        """Second element must be dict[str, MarketplaceSource]."""
        marketplaces = {
            "internal": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
        }
        config = _create_inline_org_config(marketplaces=marketplaces)
        result = resolve_effective_config(config, "dev")

        _, mktplaces = result.to_phase1_format()

        assert isinstance(mktplaces, dict)
        assert "internal" in mktplaces

    def test_adapter_enabled_plugins_match(self) -> None:
        """Adapter enabled plugins must match EffectiveConfig."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["tool-a@internal", "tool-b@internal"],
            ),
        }
        defaults = DefaultsConfig(enabled_plugins=[])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        plugins, _ = result.to_phase1_format()

        assert plugins.enabled == result.enabled_plugins

    def test_adapter_blocked_plugins_match(self) -> None:
        """Adapter blocked plugins must match EffectiveConfig."""
        defaults = DefaultsConfig(enabled_plugins=["blocked@external"])
        profiles = {"dev": TeamProfile(name="Dev")}
        security = SecurityConfig(blocked_plugins=["*@external"])
        marketplaces = {
            "external": MarketplaceSourceGitHub(source="github", owner="vendor", repo="plugins"),
        }
        config = _create_inline_org_config(
            profiles=profiles,
            defaults=defaults,
            security=security,
            marketplaces=marketplaces,
        )
        result = resolve_effective_config(config, "dev")

        plugins, _ = result.to_phase1_format()

        assert len(plugins.blocked) == len(result.blocked_plugins)
        assert plugins.blocked[0].plugin_id == result.blocked_plugins[0].plugin_id

    def test_adapter_disabled_plugins_match(self) -> None:
        """Adapter disabled plugins must match EffectiveConfig."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                disabled_plugins=["unwanted@internal"],
            ),
        }
        defaults = DefaultsConfig(enabled_plugins=["unwanted@internal"])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        plugins, _ = result.to_phase1_format()

        assert plugins.disabled == result.disabled_plugins

    def test_adapter_not_allowed_plugins_match(self) -> None:
        """Adapter not_allowed plugins must match EffectiveConfig."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["allowed@internal", "rejected@internal"],
                allowed_plugins=["allowed@*"],
            ),
        }
        defaults = DefaultsConfig(enabled_plugins=[])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        plugins, _ = result.to_phase1_format()

        assert plugins.not_allowed == result.not_allowed_plugins


# ─────────────────────────────────────────────────────────────────────────────
# Compute Function Compatibility Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestComputeFunctionCompatibility:
    """Test compute_effective_plugins() still works for inline profiles."""

    def test_compute_function_available(self) -> None:
        """Phase 1 compute function must still be available."""
        config = _create_inline_org_config()
        result = compute_effective_plugins(config, "dev")

        assert isinstance(result, EffectivePlugins)

    def test_compute_matches_resolve(self) -> None:
        """compute_effective_plugins must match resolve_effective_config for inline."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["tool-a@internal", "tool-b@internal"],
            ),
        }
        defaults = DefaultsConfig(enabled_plugins=["default@internal"])
        security = SecurityConfig(blocked_plugins=["tool-b@*"])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults, security=security)

        # Both methods should produce equivalent results
        compute_result = compute_effective_plugins(config, "dev")
        resolve_result = resolve_effective_config(config, "dev")

        assert compute_result.enabled == resolve_result.enabled_plugins
        assert len(compute_result.blocked) == len(resolve_result.blocked_plugins)

    def test_compute_team_not_found(self) -> None:
        """compute_effective_plugins must raise TeamNotFoundError."""
        config = _create_inline_org_config()

        with pytest.raises(TeamNotFoundError):
            compute_effective_plugins(config, "nonexistent")


# ─────────────────────────────────────────────────────────────────────────────
# Edge Cases
# ─────────────────────────────────────────────────────────────────────────────


class TestInlineEdgeCases:
    """Test edge cases for inline profile handling."""

    def test_empty_plugins(self) -> None:
        """Teams with no plugins must work."""
        profiles = {"dev": TeamProfile(name="Dev")}
        defaults = DefaultsConfig(enabled_plugins=[])
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)
        result = resolve_effective_config(config, "dev")

        assert result.enabled_plugins == set()
        assert result.plugin_count == 0

    def test_no_defaults_no_security(self) -> None:
        """Profiles without defaults or security must work."""
        profiles = {"dev": TeamProfile(name="Dev", additional_plugins=["tool@internal"])}
        marketplaces = {
            "internal": MarketplaceSourceGitHub(source="github", owner="test-org", repo="plugins"),
        }
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles=profiles,
            marketplaces=marketplaces,
        )
        result = resolve_effective_config(config, "dev")

        assert "tool@internal" in result.enabled_plugins
        assert result.blocked_plugins == []

    def test_no_marketplaces(self) -> None:
        """Profiles without org marketplaces must work for implicit marketplaces."""
        profiles = {
            "dev": TeamProfile(
                name="Dev",
                additional_plugins=["tool@claude-plugins-official"],
            )
        }
        # No marketplaces - but claude-plugins-official is implicit
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles=profiles,
        )
        result = resolve_effective_config(config, "dev")

        assert "tool@claude-plugins-official" in result.enabled_plugins
        assert result.marketplaces == {}

    def test_multiple_teams_isolated(self) -> None:
        """Each team must have isolated plugin sets."""
        profiles = {
            "backend": TeamProfile(name="Backend", additional_plugins=["api-tool@internal"]),
            "frontend": TeamProfile(name="Frontend", additional_plugins=["ui-tool@internal"]),
            "security": TeamProfile(name="Security", additional_plugins=["scan-tool@internal"]),
        }
        defaults = DefaultsConfig(enabled_plugins=[])  # No shared defaults
        config = _create_inline_org_config(profiles=profiles, defaults=defaults)

        backend = resolve_effective_config(config, "backend")
        frontend = resolve_effective_config(config, "frontend")
        security = resolve_effective_config(config, "security")

        assert "api-tool@internal" in backend.enabled_plugins
        assert "api-tool@internal" not in frontend.enabled_plugins
        assert "api-tool@internal" not in security.enabled_plugins

        assert "ui-tool@internal" in frontend.enabled_plugins
        assert "ui-tool@internal" not in backend.enabled_plugins

    def test_wildcard_patterns_work(self) -> None:
        """Glob patterns must work for blocking and filtering."""
        defaults = DefaultsConfig(
            enabled_plugins=[
                "safe-tool@internal",
                "unsafe-tool@external",
                "another@external",
            ]
        )
        profiles = {"dev": TeamProfile(name="Dev")}
        security = SecurityConfig(blocked_plugins=["*@external"])
        marketplaces = {
            "internal": MarketplaceSourceGitHub(
                source="github", owner="test-org", repo="internal-plugins"
            ),
            "external": MarketplaceSourceGitHub(source="github", owner="vendor", repo="plugins"),
        }
        config = _create_inline_org_config(
            profiles=profiles,
            defaults=defaults,
            security=security,
            marketplaces=marketplaces,
        )
        result = resolve_effective_config(config, "dev")

        assert "safe-tool@internal" in result.enabled_plugins
        assert "unsafe-tool@external" not in result.enabled_plugins
        assert "another@external" not in result.enabled_plugins
        assert len(result.blocked_plugins) == 2
