"""
Precedence order integration tests for SCC marketplace.

Tests the 5-step and 6-step precedence rules for plugin computation:

Inline Teams (5-step):
    1. Normalize all plugin references
    2. Merge defaults.enabled_plugins + profile.additional_plugins
    3. Apply profile.disabled_plugins patterns
    4. Apply profile.allowed_plugins filter (additional only)
    5. Apply security.blocked_plugins (final gate)

Federated Teams (6-step):
    1. Start with org defaults.enabled_plugins
    2. Add team config enabled_plugins
    3. Apply team config disabled_plugins patterns
    4. Apply org defaults.disabled_plugins patterns
    5. SKIP allowed_plugins (federated teams exempt)
    6. Apply org security.blocked_plugins (ALWAYS enforced)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scc_cli.marketplace.compute import (
    compute_effective_plugins,
    compute_effective_plugins_federated,
)
from scc_cli.marketplace.normalize import (
    fnmatch_with_globstar,
    matches_pattern,
    matches_url_pattern,
    normalize_url_for_matching,
)
from scc_cli.marketplace.schema import (
    DefaultsConfig,
    MarketplaceSourceGitHub,
    OrganizationConfig,
    SecurityConfig,
    TeamConfig,
    TeamProfile,
)

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Inline Team 5-Step Precedence Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInlineTeamPrecedence:
    """Verify 5-step precedence order for inline (non-federated) teams."""

    def test_step1_normalization_applied(self) -> None:
        """Step 1: All plugin references are normalized to canonical form."""
        org_config = OrganizationConfig(
            name="Normalization Test",
            schema_version=1,
            marketplaces={
                "internal": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(enabled_plugins=[]),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=[
                        "@internal/npm-style",  # npm-style format
                        "standard@internal",  # standard format
                    ],
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # Both formats should be normalized to canonical form
        assert "npm-style@internal" in result.enabled
        assert "standard@internal" in result.enabled
        # npm-style format should NOT appear in original form
        assert "@internal/npm-style" not in result.enabled

    def test_step2_merge_defaults_and_additional(self) -> None:
        """Step 2: Merge defaults.enabled_plugins + profile.additional_plugins."""
        org_config = OrganizationConfig(
            name="Merge Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["default-tool@shared", "common-util@shared"],
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=["extra-tool@shared", "team-specific@shared"],
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # Both defaults and additional should be present
        assert "default-tool@shared" in result.enabled
        assert "common-util@shared" in result.enabled
        assert "extra-tool@shared" in result.enabled
        assert "team-specific@shared" in result.enabled

    def test_step3_disabled_patterns_applied(self) -> None:
        """Step 3: profile.disabled_plugins patterns remove from merged set."""
        org_config = OrganizationConfig(
            name="Disabled Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["deprecated-v1@shared", "current-tool@shared"],
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    disabled_plugins=["deprecated-*"],  # Disable deprecated plugins
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # deprecated-v1 should be disabled
        assert "deprecated-v1@shared" not in result.enabled
        assert "deprecated-v1@shared" in result.disabled
        # current-tool should remain enabled
        assert "current-tool@shared" in result.enabled

    def test_step4_allowed_plugins_filter_for_additional_only(self) -> None:
        """Step 4: allowed_plugins filter applies ONLY to additional_plugins."""
        org_config = OrganizationConfig(
            name="Allowed Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["default-tool@shared"],  # In defaults
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=[
                        "allowed-tool@shared",
                        "not-allowed-tool@shared",
                    ],
                    allowed_plugins=[
                        "allowed-tool@shared",
                    ],  # Only this additional is allowed
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # Default tool should ALWAYS be enabled (not subject to allowed_plugins)
        assert "default-tool@shared" in result.enabled
        # Allowed additional should be enabled
        assert "allowed-tool@shared" in result.enabled
        # Not-allowed additional should be rejected
        assert "not-allowed-tool@shared" not in result.enabled
        assert "not-allowed-tool@shared" in result.not_allowed

    def test_step5_security_blocked_final_gate(self) -> None:
        """Step 5: security.blocked_plugins is the FINAL gate, cannot be bypassed."""
        org_config = OrganizationConfig(
            name="Security Gate Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "blocked-but-default@shared",  # In defaults but blocked
                    "safe-default@shared",
                ],
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=[
                        "blocked-additional@shared",  # In additional but blocked
                        "safe-additional@shared",
                    ],
                    # Even if allowed_plugins includes blocked plugin
                    allowed_plugins=[
                        "blocked-additional@shared",
                        "safe-additional@shared",
                    ],
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["blocked-*"],
                blocked_reason="Security policy violation",
            ),
        )

        result = compute_effective_plugins(org_config, "team")

        # Both blocked plugins should be blocked, regardless of source
        blocked_ids = {b.plugin_id for b in result.blocked}
        assert "blocked-but-default@shared" in blocked_ids
        assert "blocked-additional@shared" in blocked_ids
        # Safe plugins should be enabled
        assert "safe-default@shared" in result.enabled
        assert "safe-additional@shared" in result.enabled

    def test_empty_allowed_plugins_blocks_all_additional(self) -> None:
        """Empty allowed_plugins list [] blocks ALL additional_plugins."""
        org_config = OrganizationConfig(
            name="Empty Allowed Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["default-tool@shared"],
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=[
                        "extra-tool@shared",
                        "another-tool@shared",
                    ],
                    allowed_plugins=[],  # Empty list = block all additional
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # Default should remain
        assert "default-tool@shared" in result.enabled
        # All additional should be blocked
        assert "extra-tool@shared" not in result.enabled
        assert "another-tool@shared" not in result.enabled
        assert "extra-tool@shared" in result.not_allowed
        assert "another-tool@shared" in result.not_allowed

    def test_none_allowed_plugins_allows_all_additional(self) -> None:
        """None allowed_plugins (default) allows ALL additional_plugins."""
        org_config = OrganizationConfig(
            name="None Allowed Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(enabled_plugins=[]),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=[
                        "tool-a@shared",
                        "tool-b@shared",
                        "tool-c@shared",
                    ],
                    # allowed_plugins defaults to None
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # All additional should be enabled
        assert "tool-a@shared" in result.enabled
        assert "tool-b@shared" in result.enabled
        assert "tool-c@shared" in result.enabled
        assert len(result.not_allowed) == 0


class TestPrecedenceOrderMatters:
    """Tests that verify the ORDER of operations matters for correct behavior."""

    def test_disabled_before_security_blocked(self) -> None:
        """Disabled patterns are applied before security blocking.

        A plugin disabled by profile should NOT appear in blocked list.
        """
        org_config = OrganizationConfig(
            name="Order Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["risky-tool@shared"],
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    disabled_plugins=["risky-*"],  # Team disables this
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["risky-*"],  # Org also blocks this
                blocked_reason="Blocked by security",
            ),
        )

        result = compute_effective_plugins(org_config, "team")

        # Since disabled is applied first, it should appear in disabled list
        assert "risky-tool@shared" in result.disabled
        # And NOT in blocked list (already removed before security check)
        blocked_ids = {b.plugin_id for b in result.blocked}
        assert "risky-tool@shared" not in blocked_ids

    def test_allowed_before_security_blocked(self) -> None:
        """Allowed filter is applied before security blocking.

        A plugin not in allowed_plugins should appear in not_allowed,
        not in blocked.
        """
        org_config = OrganizationConfig(
            name="Allowed Order Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(enabled_plugins=[]),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=["restricted-tool@shared"],
                    allowed_plugins=["other-tool@shared"],  # restricted not in list
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["restricted-*"],
                blocked_reason="Blocked",
            ),
        )

        result = compute_effective_plugins(org_config, "team")

        # Since allowed filter is applied before security,
        # restricted-tool should be in not_allowed
        assert "restricted-tool@shared" in result.not_allowed
        # And NOT in blocked (already filtered out)
        blocked_ids = {b.plugin_id for b in result.blocked}
        assert "restricted-tool@shared" not in blocked_ids


# ─────────────────────────────────────────────────────────────────────────────
# Federated Team 6-Step Precedence Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestFederatedTeamPrecedence:
    """Verify 6-step precedence order for federated teams."""

    def test_step1_org_defaults_as_base(self) -> None:
        """Step 1: Start with org defaults.enabled_plugins."""
        org_config = OrganizationConfig(
            name="Federated Base Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["org-default-a@shared", "org-default-b@shared"],
            ),
            profiles={
                "federated-team": TeamProfile(
                    name="Federated Team",
                    # No additional_plugins for federated
                ),
            },
            security=SecurityConfig(),
        )

        team_config = TeamConfig(
            schema_version=1,
            enabled_plugins=[],  # Empty team config
        )

        result = compute_effective_plugins_federated(org_config, "federated-team", team_config)

        # Org defaults should be the base
        assert "org-default-a@shared" in result.enabled
        assert "org-default-b@shared" in result.enabled

    def test_step2_team_config_plugins_added(self) -> None:
        """Step 2: Team config enabled_plugins are added to base."""
        org_config = OrganizationConfig(
            name="Federated Add Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["org-tool@shared"],
            ),
            profiles={
                "federated-team": TeamProfile(name="Federated Team"),
            },
            security=SecurityConfig(),
        )

        team_config = TeamConfig(
            schema_version=1,
            enabled_plugins=["team-tool@shared", "custom-tool@shared"],
        )

        result = compute_effective_plugins_federated(org_config, "federated-team", team_config)

        # Both org defaults and team plugins should be present
        assert "org-tool@shared" in result.enabled
        assert "team-tool@shared" in result.enabled
        assert "custom-tool@shared" in result.enabled

    def test_step3_team_disabled_patterns_applied(self) -> None:
        """Step 3: Team config disabled_plugins patterns remove plugins."""
        org_config = OrganizationConfig(
            name="Team Disable Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["old-tool@shared", "new-tool@shared"],
            ),
            profiles={
                "federated-team": TeamProfile(name="Federated Team"),
            },
            security=SecurityConfig(),
        )

        team_config = TeamConfig(
            schema_version=1,
            enabled_plugins=[],
            disabled_plugins=["old-*"],  # Team disables old plugins
        )

        result = compute_effective_plugins_federated(org_config, "federated-team", team_config)

        # old-tool should be disabled by team
        assert "old-tool@shared" not in result.enabled
        assert "old-tool@shared" in result.disabled
        # new-tool should remain
        assert "new-tool@shared" in result.enabled

    def test_step4_org_disabled_patterns_applied(self) -> None:
        """Step 4: Org defaults.disabled_plugins patterns applied after team's."""
        org_config = OrganizationConfig(
            name="Org Disable Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["approved-tool@shared"],
                disabled_plugins=["deprecated-*"],  # Org-level disable
            ),
            profiles={
                "federated-team": TeamProfile(name="Federated Team"),
            },
            security=SecurityConfig(),
        )

        team_config = TeamConfig(
            schema_version=1,
            enabled_plugins=["deprecated-v2@shared"],  # Team wants deprecated
        )

        result = compute_effective_plugins_federated(org_config, "federated-team", team_config)

        # deprecated-v2 should be disabled by org pattern
        assert "deprecated-v2@shared" not in result.enabled
        assert "deprecated-v2@shared" in result.disabled
        # approved should remain
        assert "approved-tool@shared" in result.enabled

    def test_step5_allowed_plugins_not_applied_to_federated(self) -> None:
        """Step 5: allowed_plugins from profile is NOT applied to federated teams."""
        org_config = OrganizationConfig(
            name="Allowed Skip Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(enabled_plugins=[]),
            profiles={
                "federated-team": TeamProfile(
                    name="Federated Team",
                    # Even with allowed_plugins set, it should be ignored
                    allowed_plugins=["only-this@shared"],
                ),
            },
            security=SecurityConfig(),
        )

        team_config = TeamConfig(
            schema_version=1,
            enabled_plugins=[
                "any-tool@shared",  # Would be blocked by allowed_plugins for inline
                "only-this@shared",
            ],
        )

        result = compute_effective_plugins_federated(org_config, "federated-team", team_config)

        # Both should be enabled - allowed_plugins is skipped
        assert "any-tool@shared" in result.enabled
        assert "only-this@shared" in result.enabled
        # nothing should be in not_allowed
        assert len(result.not_allowed) == 0

    def test_step6_security_blocked_always_enforced(self) -> None:
        """Step 6: security.blocked_plugins is ALWAYS enforced for federated."""
        org_config = OrganizationConfig(
            name="Security Always Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(enabled_plugins=[]),
            profiles={
                "federated-team": TeamProfile(name="Federated Team"),
            },
            security=SecurityConfig(
                blocked_plugins=["malicious-*", "risky-*"],
                blocked_reason="Org security policy",
            ),
        )

        team_config = TeamConfig(
            schema_version=1,
            enabled_plugins=[
                "malicious-tool@shared",  # Blocked
                "risky-script@shared",  # Blocked
                "safe-tool@shared",  # Allowed
            ],
        )

        result = compute_effective_plugins_federated(org_config, "federated-team", team_config)

        # Both malicious and risky should be blocked
        blocked_ids = {b.plugin_id for b in result.blocked}
        assert "malicious-tool@shared" in blocked_ids
        assert "risky-script@shared" in blocked_ids
        # safe-tool should be enabled
        assert "safe-tool@shared" in result.enabled


# ─────────────────────────────────────────────────────────────────────────────
# Property-Based Tests for Pattern Matching
# ─────────────────────────────────────────────────────────────────────────────

# Check if Hypothesis is available for property-based testing
try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False
    # Define dummy decorators to prevent NameError during test collection
    from collections.abc import Callable
    from typing import Any, TypeVar

    F = TypeVar("F", bound=Callable[..., Any])

    def given(*args: Any, **kwargs: Any) -> Callable[[F], F]:
        """Dummy @given decorator when Hypothesis not installed."""

        def decorator(f: F) -> F:
            return f

        return decorator

    def settings(*args: Any, **kwargs: Any) -> Callable[[F], F]:
        """Dummy @settings decorator when Hypothesis not installed."""

        def decorator(f: F) -> F:
            return f

        return decorator

    class _DummySt:
        """Dummy strategies module when Hypothesis not installed."""

        @staticmethod
        def text(*args: Any, **kwargs: Any) -> None:
            return None

        @staticmethod
        def sampled_from(*args: Any, **kwargs: Any) -> None:
            return None

    st: Any = _DummySt()  # type: ignore[no-redef]


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="Hypothesis not installed")
class TestPatternMatchingProperties:
    """Property-based tests for pattern matching functions."""

    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_matches_pattern_never_crashes(self, text: str) -> None:
        """Pattern matching must handle any input without crashing."""
        # Any text as pattern or input should not crash
        try:
            result = matches_pattern(text, "*")
            assert isinstance(result, bool)
            result2 = matches_pattern("test-plugin@shared", text)
            assert isinstance(result2, bool)
        except ValueError:
            # Invalid patterns may raise ValueError, which is acceptable
            pass

    @given(st.text(min_size=1, max_size=100))
    @settings(max_examples=100)
    def test_globstar_never_crashes(self, pattern: str) -> None:
        """Globstar matching must handle any pattern without crashing."""
        try:
            result = fnmatch_with_globstar("github.com/test/repo", pattern)
            assert isinstance(result, bool)
        except (ValueError, RecursionError):
            # Complex patterns may raise, but shouldn't crash
            pass

    @given(
        st.sampled_from(["github.com", "gitlab.com", "bitbucket.org"]),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz-_", min_size=1, max_size=20),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz-_", min_size=1, max_size=20),
    )
    @settings(max_examples=100)
    def test_url_normalization_is_idempotent(self, host: str, org: str, repo: str) -> None:
        """normalize(normalize(x)) == normalize(x) - idempotent property."""
        url = f"https://{host}/{org}/{repo}"
        once = normalize_url_for_matching(url)
        twice = normalize_url_for_matching(once)
        assert once == twice, f"Not idempotent: {url} -> {once} -> {twice}"

    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
    )
    @settings(max_examples=50)
    def test_case_insensitivity_property(self, name: str) -> None:
        """Pattern matching must be case-insensitive."""
        lower_plugin = f"{name.lower()}-tool@shared"
        upper_plugin = f"{name.upper()}-TOOL@SHARED"
        mixed_plugin = f"{name.title()}-Tool@Shared"
        pattern = f"{name.lower()}-*"

        # All case variants should match the same pattern
        assert matches_pattern(lower_plugin, pattern)
        assert matches_pattern(upper_plugin, pattern)
        assert matches_pattern(mixed_plugin, pattern)

    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=15),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz-", min_size=1, max_size=15),
    )
    @settings(max_examples=100)
    def test_wildcard_at_end_matches_any_suffix(self, prefix: str, suffix: str) -> None:
        """Pattern 'prefix-*' should match any plugin starting with 'prefix-'."""
        pattern = f"{prefix}-*"
        plugin = f"{prefix}-{suffix}@shared"

        assert matches_pattern(plugin, pattern), f"Pattern '{pattern}' should match '{plugin}'"


@pytest.mark.skipif(not HYPOTHESIS_AVAILABLE, reason="Hypothesis not installed")
class TestURLPatternProperties:
    """Property-based tests for URL pattern matching."""

    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=15),
    )
    @settings(max_examples=100)
    def test_globstar_matches_any_depth(self, org: str, repo: str) -> None:
        """Pattern 'host/**' should match any path depth."""
        pattern = "github.com/**"

        # Various depths should all match
        medium = f"github.com/{org}/{repo}"
        deep = f"github.com/{org}/{repo}/subpath"

        # Test multiple path depths
        assert matches_url_pattern(f"https://{medium}", pattern)
        assert matches_url_pattern(f"https://{deep}", pattern)

    @given(
        st.sampled_from(["https://", "git@", "http://"]),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=10),
    )
    @settings(max_examples=50)
    def test_protocol_independence(self, protocol: str, org: str) -> None:
        """Pattern should match regardless of protocol variant."""
        pattern = f"github.com/{org}/**"

        # Build URLs with different protocols
        if protocol == "git@":
            url = f"git@github.com:{org}/repo.git"
        elif protocol == "http://":
            url = f"http://github.com/{org}/repo"
        else:
            url = f"https://github.com/{org}/repo"

        # All should match after normalization
        assert matches_url_pattern(url, pattern), (
            f"Protocol {protocol} should not affect matching for {url}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Extra Marketplaces Precedence Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestExtraMarketplacesPrecedence:
    """Test extra_marketplaces merging from defaults and profile."""

    def test_extra_marketplaces_merged_from_defaults_and_profile(self) -> None:
        """Extra marketplaces should include both defaults and profile entries."""
        org_config = OrganizationConfig(
            name="Extra Marketplaces Test",
            schema_version=1,
            marketplaces={
                "internal": MarketplaceSourceGitHub(source="github", owner="org", repo="internal"),
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="shared"),
                "experimental": MarketplaceSourceGitHub(
                    source="github", owner="org", repo="experimental"
                ),
            },
            defaults=DefaultsConfig(
                enabled_plugins=[],
                extra_marketplaces=["internal", "shared"],  # Default exposure
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    extra_marketplaces=["experimental"],  # Team-specific
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # All three should be in extra_marketplaces
        assert "internal" in result.extra_marketplaces
        assert "shared" in result.extra_marketplaces
        assert "experimental" in result.extra_marketplaces

    def test_extra_marketplaces_deduplication(self) -> None:
        """Duplicate extra_marketplaces entries should be deduplicated."""
        org_config = OrganizationConfig(
            name="Dedup Test",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(source="github", owner="org", repo="plugins"),
            },
            defaults=DefaultsConfig(
                enabled_plugins=[],
                extra_marketplaces=["shared"],  # In defaults
            ),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    extra_marketplaces=["shared"],  # Also in profile
                ),
            },
            security=SecurityConfig(),
        )

        result = compute_effective_plugins(org_config, "team")

        # Should only appear once
        assert result.extra_marketplaces.count("shared") == 1
