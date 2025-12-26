"""Tests for marketplace trust validation module (Phase 2: Federation).

Covers:
- TrustViolationError and SecurityViolationError exceptions
- validate_marketplace_source() for URL pattern validation
- validate_team_config_trust() for two-layer trust enforcement
"""

from __future__ import annotations

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Exception Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTrustViolationError:
    """Tests for TrustViolationError exception."""

    def test_has_team_name(self) -> None:
        """Exception stores the team that violated trust."""
        from scc_cli.marketplace.trust import TrustViolationError

        err = TrustViolationError(
            team_name="backend",
            violation="Marketplace not in allowed patterns",
        )
        assert err.team_name == "backend"

    def test_has_violation_description(self) -> None:
        """Exception stores what was violated."""
        from scc_cli.marketplace.trust import TrustViolationError

        err = TrustViolationError(
            team_name="backend",
            violation="Team defines marketplace without allow_additional_marketplaces",
        )
        assert "allow_additional_marketplaces" in err.violation

    def test_str_includes_team_and_violation(self) -> None:
        """String representation includes both team and violation."""
        from scc_cli.marketplace.trust import TrustViolationError

        err = TrustViolationError(
            team_name="frontend",
            violation="Marketplace source doesn't match allowed patterns",
        )
        msg = str(err)
        assert "frontend" in msg
        assert "allowed patterns" in msg

    def test_is_value_error(self) -> None:
        """Exception inherits from ValueError for consistency."""
        from scc_cli.marketplace.trust import TrustViolationError

        err = TrustViolationError(team_name="x", violation="y")
        assert isinstance(err, ValueError)


class TestSecurityViolationError:
    """Tests for SecurityViolationError exception."""

    def test_has_plugin_and_reason(self) -> None:
        """Exception stores blocked plugin and reason."""
        from scc_cli.marketplace.trust import SecurityViolationError

        err = SecurityViolationError(
            plugin_ref="risky-tool@external",
            reason="Blocked by organization security policy",
        )
        assert err.plugin_ref == "risky-tool@external"
        assert "security policy" in err.reason

    def test_str_includes_plugin_and_reason(self) -> None:
        """String representation is user-friendly."""
        from scc_cli.marketplace.trust import SecurityViolationError

        err = SecurityViolationError(
            plugin_ref="debug@test",
            reason="Matched security.blocked_plugins pattern '*@test'",
        )
        msg = str(err)
        assert "debug@test" in msg
        assert "blocked" in msg.lower()

    def test_is_value_error(self) -> None:
        """Exception inherits from ValueError."""
        from scc_cli.marketplace.trust import SecurityViolationError

        err = SecurityViolationError(plugin_ref="x", reason="y")
        assert isinstance(err, ValueError)


# ─────────────────────────────────────────────────────────────────────────────
# Marketplace Source Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateMarketplaceSource:
    """Tests for validate_marketplace_source function."""

    def test_github_source_matches_pattern(self) -> None:
        """GitHub marketplace source matching allowed pattern passes."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub
        from scc_cli.marketplace.trust import validate_marketplace_source

        source = MarketplaceSourceGitHub(
            source="github",
            owner="sundsvall",
            repo="plugins",
        )
        patterns = ["github.com/sundsvall/**"]

        # Should not raise
        validate_marketplace_source(source, patterns, "backend")

    def test_github_source_no_match_raises(self) -> None:
        """GitHub source not matching patterns raises TrustViolationError."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub
        from scc_cli.marketplace.trust import TrustViolationError, validate_marketplace_source

        source = MarketplaceSourceGitHub(
            source="github",
            owner="external-org",
            repo="plugins",
        )
        patterns = ["github.com/sundsvall/**"]

        with pytest.raises(TrustViolationError) as exc:
            validate_marketplace_source(source, patterns, "backend")

        assert "backend" in str(exc.value)
        assert "external-org" in str(exc.value) or "github.com" in str(exc.value)

    def test_git_source_matches_pattern(self) -> None:
        """Git marketplace source matching allowed pattern passes."""
        from scc_cli.marketplace.schema import MarketplaceSourceGit
        from scc_cli.marketplace.trust import validate_marketplace_source

        source = MarketplaceSourceGit(
            source="git",
            url="https://gitlab.sundsvall.se/ai/plugins.git",
        )
        patterns = ["gitlab.sundsvall.se/**"]

        # Should not raise
        validate_marketplace_source(source, patterns, "backend")

    def test_url_source_matches_pattern(self) -> None:
        """URL marketplace source matching allowed pattern passes."""
        from scc_cli.marketplace.schema import MarketplaceSourceURL
        from scc_cli.marketplace.trust import validate_marketplace_source

        source = MarketplaceSourceURL(
            source="url",
            url="https://plugins.sundsvall.se/marketplace.json",
        )
        patterns = ["plugins.sundsvall.se/**"]

        # Should not raise
        validate_marketplace_source(source, patterns, "backend")

    def test_directory_source_always_allowed(self) -> None:
        """Directory source is org-local, always passes validation."""
        from scc_cli.marketplace.schema import MarketplaceSourceDirectory
        from scc_cli.marketplace.trust import validate_marketplace_source

        source = MarketplaceSourceDirectory(
            source="directory",
            path="/opt/local/plugins",
        )
        # Empty patterns - directory should still pass
        validate_marketplace_source(source, [], "backend")

    def test_empty_patterns_rejects_remote_sources(self) -> None:
        """Empty patterns list rejects all remote sources."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub
        from scc_cli.marketplace.trust import TrustViolationError, validate_marketplace_source

        source = MarketplaceSourceGitHub(
            source="github",
            owner="any",
            repo="repo",
        )

        with pytest.raises(TrustViolationError):
            validate_marketplace_source(source, [], "backend")

    def test_multiple_patterns_any_match_passes(self) -> None:
        """Source matching any of multiple patterns passes."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub
        from scc_cli.marketplace.trust import validate_marketplace_source

        source = MarketplaceSourceGitHub(
            source="github",
            owner="sundsvall-frontend",
            repo="ui-plugins",
        )
        patterns = [
            "github.com/sundsvall-backend/**",
            "github.com/sundsvall-frontend/**",
            "gitlab.internal.se/**",
        ]

        # Should match second pattern
        validate_marketplace_source(source, patterns, "frontend")


class TestGetSourceUrl:
    """Tests for get_source_url helper function."""

    def test_github_source_url(self) -> None:
        """GitHub source returns normalized URL."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub
        from scc_cli.marketplace.trust import get_source_url

        source = MarketplaceSourceGitHub(
            source="github",
            owner="sundsvall",
            repo="plugins",
        )
        url = get_source_url(source)
        assert url == "github.com/sundsvall/plugins"

    def test_git_source_url(self) -> None:
        """Git source returns normalized clone URL."""
        from scc_cli.marketplace.schema import MarketplaceSourceGit
        from scc_cli.marketplace.trust import get_source_url

        source = MarketplaceSourceGit(
            source="git",
            url="https://gitlab.example.se/team/plugins.git",
        )
        url = get_source_url(source)
        assert url == "gitlab.example.se/team/plugins"

    def test_url_source_url(self) -> None:
        """URL source returns normalized URL."""
        from scc_cli.marketplace.schema import MarketplaceSourceURL
        from scc_cli.marketplace.trust import get_source_url

        source = MarketplaceSourceURL(
            source="url",
            url="https://plugins.example.se/manifest.json",
        )
        url = get_source_url(source)
        assert url == "plugins.example.se/manifest.json"

    def test_directory_source_returns_none(self) -> None:
        """Directory source returns None (local, no URL)."""
        from scc_cli.marketplace.schema import MarketplaceSourceDirectory
        from scc_cli.marketplace.trust import get_source_url

        source = MarketplaceSourceDirectory(
            source="directory",
            path="/local/path",
        )
        url = get_source_url(source)
        assert url is None


# ─────────────────────────────────────────────────────────────────────────────
# Team Config Trust Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateTeamConfigTrust:
    """Tests for validate_team_config_trust function."""

    def test_no_marketplaces_no_validation_needed(self) -> None:
        """Team with no marketplaces passes validation."""
        from scc_cli.marketplace.schema import TeamConfig, TrustGrant
        from scc_cli.marketplace.trust import validate_team_config_trust

        team_config = TeamConfig(
            schema_version=1,
            enabled_plugins=["tool@shared"],
            marketplaces={},
        )
        trust = TrustGrant()

        # Should not raise
        validate_team_config_trust(team_config, trust, "backend", {})

    def test_marketplaces_without_allow_raises(self) -> None:
        """Team with marketplaces but allow_additional_marketplaces=False raises."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub, TeamConfig, TrustGrant
        from scc_cli.marketplace.trust import TrustViolationError, validate_team_config_trust

        team_config = TeamConfig(
            schema_version=1,
            marketplaces={
                "team-mp": MarketplaceSourceGitHub(
                    source="github",
                    owner="team",
                    repo="plugins",
                ),
            },
        )
        trust = TrustGrant(allow_additional_marketplaces=False)

        with pytest.raises(TrustViolationError) as exc:
            validate_team_config_trust(team_config, trust, "backend", {})

        assert (
            "allow_additional_marketplaces" in str(exc.value).lower()
            or "not allowed" in str(exc.value).lower()
        )

    def test_marketplaces_with_allow_and_pattern_match_passes(self) -> None:
        """Team with allowed marketplaces matching patterns passes."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub, TeamConfig, TrustGrant
        from scc_cli.marketplace.trust import validate_team_config_trust

        team_config = TeamConfig(
            schema_version=1,
            marketplaces={
                "team-mp": MarketplaceSourceGitHub(
                    source="github",
                    owner="sundsvall",
                    repo="team-plugins",
                ),
            },
        )
        trust = TrustGrant(
            allow_additional_marketplaces=True,
            marketplace_source_patterns=["github.com/sundsvall/**"],
        )

        # Should not raise
        validate_team_config_trust(team_config, trust, "backend", {})

    def test_marketplace_name_collision_with_org_raises(self) -> None:
        """Team marketplace name colliding with org marketplace raises."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub, TeamConfig, TrustGrant
        from scc_cli.marketplace.trust import TrustViolationError, validate_team_config_trust

        team_config = TeamConfig(
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(  # Same name as org marketplace
                    source="github",
                    owner="team",
                    repo="plugins",
                ),
            },
        )
        trust = TrustGrant(
            allow_additional_marketplaces=True,
            marketplace_source_patterns=["github.com/**"],
        )
        org_marketplaces = {"shared": {}}  # Org already has 'shared'

        with pytest.raises(TrustViolationError) as exc:
            validate_team_config_trust(team_config, trust, "backend", org_marketplaces)

        assert "shared" in str(exc.value)
        assert "conflict" in str(exc.value).lower() or "collision" in str(exc.value).lower()

    def test_marketplace_name_collision_with_implicit_raises(self) -> None:
        """Team marketplace name colliding with implicit marketplace raises."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub, TeamConfig, TrustGrant
        from scc_cli.marketplace.trust import TrustViolationError, validate_team_config_trust

        team_config = TeamConfig(
            schema_version=1,
            marketplaces={
                "claude-plugins-official": MarketplaceSourceGitHub(
                    source="github",
                    owner="team",
                    repo="fake-official",
                ),
            },
        )
        trust = TrustGrant(
            allow_additional_marketplaces=True,
            marketplace_source_patterns=["github.com/**"],
        )

        with pytest.raises(TrustViolationError) as exc:
            validate_team_config_trust(team_config, trust, "backend", {})

        assert "claude-plugins-official" in str(exc.value)

    def test_multiple_valid_marketplaces_pass(self) -> None:
        """Team with multiple valid marketplaces passes."""
        from scc_cli.marketplace.schema import (
            MarketplaceSourceGit,
            MarketplaceSourceGitHub,
            TeamConfig,
            TrustGrant,
        )
        from scc_cli.marketplace.trust import validate_team_config_trust

        team_config = TeamConfig(
            schema_version=1,
            marketplaces={
                "github-mp": MarketplaceSourceGitHub(
                    source="github",
                    owner="sundsvall",
                    repo="plugins",
                ),
                "gitlab-mp": MarketplaceSourceGit(
                    source="git",
                    url="https://gitlab.sundsvall.se/ai/tools.git",
                ),
            },
        )
        trust = TrustGrant(
            allow_additional_marketplaces=True,
            marketplace_source_patterns=[
                "github.com/sundsvall/**",
                "gitlab.sundsvall.se/**",
            ],
        )

        # Should not raise
        validate_team_config_trust(team_config, trust, "backend", {})

    def test_one_invalid_marketplace_raises(self) -> None:
        """If any marketplace is invalid, validation fails."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub, TeamConfig, TrustGrant
        from scc_cli.marketplace.trust import TrustViolationError, validate_team_config_trust

        team_config = TeamConfig(
            schema_version=1,
            marketplaces={
                "valid-mp": MarketplaceSourceGitHub(
                    source="github",
                    owner="sundsvall",
                    repo="plugins",
                ),
                "invalid-mp": MarketplaceSourceGitHub(
                    source="github",
                    owner="external",
                    repo="bad-plugins",
                ),
            },
        )
        trust = TrustGrant(
            allow_additional_marketplaces=True,
            marketplace_source_patterns=["github.com/sundsvall/**"],
        )

        with pytest.raises(TrustViolationError) as exc:
            validate_team_config_trust(team_config, trust, "backend", {})

        assert "external" in str(exc.value) or "invalid-mp" in str(exc.value)
