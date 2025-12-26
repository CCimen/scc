"""
Unit tests for marketplace normalization utilities.

Tests cover:
- normalize_plugin(): Convert various plugin reference formats to canonical form
- matches_pattern(): Glob pattern matching for plugin filtering

TDD: These tests are written BEFORE implementation.
"""

import pytest


class TestNormalizePluginNameAtMarketplace:
    """Tests for 'name@marketplace' format parsing."""

    def test_simple_name_at_marketplace(self) -> None:
        """Standard name@marketplace format returns as-is."""
        from scc_cli.marketplace.normalize import normalize_plugin

        result = normalize_plugin("code-review@internal-plugins", {})
        assert result == "code-review@internal-plugins"

    def test_complex_plugin_name(self) -> None:
        """Plugin names can contain hyphens and numbers."""
        from scc_cli.marketplace.normalize import normalize_plugin

        result = normalize_plugin("my-plugin-v2@org-marketplace", {})
        assert result == "my-plugin-v2@org-marketplace"

    def test_preserves_marketplace_name(self) -> None:
        """Marketplace name is preserved exactly."""
        from scc_cli.marketplace.normalize import normalize_plugin

        result = normalize_plugin("tool@My-Marketplace-123", {})
        assert result == "tool@My-Marketplace-123"


class TestNormalizePluginAtMarketplaceName:
    """Tests for '@marketplace/name' (npm-style) format parsing."""

    def test_npm_style_format(self) -> None:
        """@marketplace/name converts to name@marketplace."""
        from scc_cli.marketplace.normalize import normalize_plugin

        result = normalize_plugin("@internal-plugins/code-review", {})
        assert result == "code-review@internal-plugins"

    def test_npm_style_with_complex_name(self) -> None:
        """npm-style with complex plugin name."""
        from scc_cli.marketplace.normalize import normalize_plugin

        result = normalize_plugin("@my-marketplace/advanced-tool-v3", {})
        assert result == "advanced-tool-v3@my-marketplace"


class TestNormalizePluginAutoResolve:
    """Tests for auto-resolution when marketplace not specified."""

    def test_zero_org_marketplaces_resolves_to_official(self) -> None:
        """With 0 org marketplaces, resolve to claude-plugins-official."""
        from scc_cli.marketplace.normalize import normalize_plugin

        result = normalize_plugin("code-review", {})
        assert result == "code-review@claude-plugins-official"

    def test_one_org_marketplace_auto_resolves(self) -> None:
        """With 1 org marketplace, auto-resolve to it."""
        from scc_cli.marketplace.normalize import normalize_plugin

        org_marketplaces = {"internal": {"source": "github", "owner": "org", "repo": "plugins"}}
        result = normalize_plugin("code-review", org_marketplaces)
        assert result == "code-review@internal"

    def test_two_org_marketplaces_requires_explicit(self) -> None:
        """With 2+ org marketplaces, explicit qualifier required."""
        from scc_cli.marketplace.normalize import (
            AmbiguousMarketplaceError,
            normalize_plugin,
        )

        org_marketplaces = {
            "internal": {"source": "github", "owner": "org", "repo": "plugins"},
            "external": {"source": "github", "owner": "other", "repo": "tools"},
        }
        with pytest.raises(AmbiguousMarketplaceError) as exc_info:
            normalize_plugin("code-review", org_marketplaces)

        assert "code-review" in str(exc_info.value)
        assert "internal" in str(exc_info.value) or "external" in str(exc_info.value)


class TestNormalizePluginValidation:
    """Tests for plugin reference validation."""

    def test_invalid_empty_name(self) -> None:
        """Empty plugin name is invalid."""
        from scc_cli.marketplace.normalize import InvalidPluginRefError, normalize_plugin

        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("", {})

    def test_invalid_empty_marketplace(self) -> None:
        """Empty marketplace in name@marketplace is invalid."""
        from scc_cli.marketplace.normalize import InvalidPluginRefError, normalize_plugin

        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("plugin@", {})

    def test_invalid_empty_name_in_explicit_format(self) -> None:
        """Empty name in @marketplace/name is invalid."""
        from scc_cli.marketplace.normalize import InvalidPluginRefError, normalize_plugin

        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("@marketplace/", {})

    def test_invalid_double_at(self) -> None:
        """Double @ in reference is invalid."""
        from scc_cli.marketplace.normalize import InvalidPluginRefError, normalize_plugin

        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("name@@marketplace", {})

    def test_whitespace_only_is_invalid(self) -> None:
        """Whitespace-only reference is invalid."""
        from scc_cli.marketplace.normalize import InvalidPluginRefError, normalize_plugin

        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("   ", {})


class TestNormalizePluginEdgeCases:
    """Tests for edge cases in plugin normalization."""

    def test_plugin_with_at_in_name(self) -> None:
        """Plugin name can contain @ if properly formatted."""
        from scc_cli.marketplace.normalize import normalize_plugin

        # The first @ after a non-@ prefix is the separator
        result = normalize_plugin("email-tools@internal", {})
        assert result == "email-tools@internal"

    def test_implicit_marketplace_not_counted(self) -> None:
        """Implicit marketplaces don't count toward ambiguity check."""
        from scc_cli.marketplace.normalize import normalize_plugin

        # Even though claude-plugins-official exists implicitly,
        # with 1 org marketplace, auto-resolve works
        org_marketplaces = {"internal": {"source": "github", "owner": "org", "repo": "plugins"}}
        result = normalize_plugin("tool", org_marketplaces)
        assert result == "tool@internal"

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        from scc_cli.marketplace.normalize import normalize_plugin

        result = normalize_plugin("  code-review@internal  ", {})
        assert result == "code-review@internal"


class TestMatchesPattern:
    """Tests for glob pattern matching."""

    def test_exact_match(self) -> None:
        """Exact string matches."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("code-review@internal", "code-review@internal") is True

    def test_wildcard_star(self) -> None:
        """Asterisk matches any sequence."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("code-review@internal", "*@internal") is True
        assert matches_pattern("any-tool@internal", "*@internal") is True
        assert matches_pattern("tool@other", "*@internal") is False

    def test_wildcard_question(self) -> None:
        """Question mark matches single character."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("tool-v1@internal", "tool-v?@internal") is True
        assert matches_pattern("tool-v12@internal", "tool-v?@internal") is False

    def test_double_star_recursive(self) -> None:
        """Double star matches across segments."""
        from scc_cli.marketplace.normalize import matches_pattern

        # Match any plugin from any marketplace
        assert matches_pattern("tool@marketplace", "**") is True
        # Match pattern in marketplace
        assert matches_pattern("tool@my-org", "*@my-*") is True

    def test_no_match(self) -> None:
        """Non-matching patterns return False."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("code-review@internal", "other@internal") is False
        assert matches_pattern("code-review@internal", "code-review@other") is False

    def test_case_insensitive(self) -> None:
        """Pattern matching is case-insensitive per ARCHITECTURE.md and GOVERNANCE.md.

        Uses Unicode-aware casefolding to prevent bypass attempts via case variation.
        """
        from scc_cli.marketplace.normalize import matches_pattern

        # All case variations should match
        assert matches_pattern("Tool@Internal", "tool@internal") is True
        assert matches_pattern("Tool@Internal", "Tool@Internal") is True
        assert matches_pattern("tool@internal", "TOOL@INTERNAL") is True
        assert matches_pattern("MALICIOUS-tool@shared", "malicious-*") is True

    def test_special_characters(self) -> None:
        """Handles special characters in names."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("my-plugin_v2.0@org", "my-plugin_v2.0@org") is True
        assert matches_pattern("my-plugin_v2.0@org", "*_v?.?@*") is True


class TestMatchesPatternEdgeCases:
    """Edge cases for pattern matching."""

    def test_empty_plugin(self) -> None:
        """Empty plugin string doesn't match patterns."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("", "*") is False

    def test_empty_pattern(self) -> None:
        """Empty pattern doesn't match anything."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("tool@marketplace", "") is False

    def test_marketplace_wildcard(self) -> None:
        """Wildcard in marketplace position."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("code-review@internal-plugins", "code-review@*") is True
        assert matches_pattern("code-review@any-marketplace", "code-review@*") is True

    def test_name_wildcard(self) -> None:
        """Wildcard in name position."""
        from scc_cli.marketplace.normalize import matches_pattern

        assert matches_pattern("any-tool@internal", "*-tool@internal") is True
        assert matches_pattern("another-tool@internal", "*-tool@internal") is True


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: URL Pattern Matching Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestNormalizeUrlForMatching:
    """Tests for URL normalization for pattern matching."""

    def test_https_url_strips_protocol(self) -> None:
        """HTTPS URLs have protocol stripped."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("https://github.com/sundsvall/plugins")
        assert result == "github.com/sundsvall/plugins"

    def test_http_url_strips_protocol(self) -> None:
        """HTTP URLs have protocol stripped."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("http://internal.example.se/repo")
        assert result == "internal.example.se/repo"

    def test_git_ssh_url_converts(self) -> None:
        """git@host:path format converts to host/path, .git suffix removed."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("git@github.com:sundsvall/plugins.git")
        assert result == "github.com/sundsvall/plugins"

    def test_lowercases_host(self) -> None:
        """Host portion is lowercased."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("https://GitHub.COM/Sundsvall/Plugins")
        assert result == "github.com/Sundsvall/Plugins"

    def test_preserves_path_case(self) -> None:
        """Path case is preserved (important for repo names)."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("https://github.com/MyOrg/MyRepo")
        assert result == "github.com/MyOrg/MyRepo"

    def test_removes_trailing_dotgit(self) -> None:
        """Trailing .git is removed for consistency."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("https://github.com/org/repo.git")
        assert result == "github.com/org/repo"

    def test_handles_port_in_url(self) -> None:
        """URLs with ports are handled correctly."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("https://gitlab.internal.se:8443/team/repo")
        assert result == "gitlab.internal.se:8443/team/repo"

    def test_empty_url_returns_empty(self) -> None:
        """Empty URL returns empty string."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("")
        assert result == ""

    def test_host_only_url_lowercased(self) -> None:
        """URL with just hostname (no path) is lowercased."""
        from scc_cli.marketplace.normalize import normalize_url_for_matching

        result = normalize_url_for_matching("https://GitHub.COM")
        assert result == "github.com"


class TestFnmatchWithGlobstar:
    """Tests for fnmatch extended with globstar (**) support."""

    def test_single_star_matches_segment(self) -> None:
        """Single star matches within segment (no /)."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("github.com/org/repo", "github.com/*/repo") is True
        assert fnmatch_with_globstar("github.com/other/repo", "github.com/*/repo") is True
        # Single star doesn't cross segments
        assert fnmatch_with_globstar("github.com/a/b/repo", "github.com/*/repo") is False

    def test_double_star_matches_zero_segments(self) -> None:
        """Double star can match zero segments."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("github.com/repo", "github.com/**/repo") is True

    def test_double_star_matches_one_segment(self) -> None:
        """Double star matches single segment."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("github.com/org/repo", "github.com/**/repo") is True

    def test_double_star_matches_multiple_segments(self) -> None:
        """Double star matches multiple segments with slashes."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("github.com/a/b/c/repo", "github.com/**/repo") is True
        assert fnmatch_with_globstar("github.com/x/y/z/repo", "github.com/**/repo") is True

    def test_double_star_at_end(self) -> None:
        """Double star at end matches everything."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("github.com/org/repo", "github.com/**") is True
        assert fnmatch_with_globstar("github.com/a/b/c/d", "github.com/**") is True

    def test_double_star_at_start(self) -> None:
        """Double star at start matches any prefix."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("github.com/org/repo", "**/repo") is True
        assert fnmatch_with_globstar("any/path/here/repo", "**/repo") is True

    def test_mixed_stars(self) -> None:
        """Mix of single and double stars."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        # Match: github.com/<anything>/<any-nested>/plugins
        pattern = "github.com/*-team/**/plugins"
        assert fnmatch_with_globstar("github.com/backend-team/v1/plugins", pattern) is True
        assert fnmatch_with_globstar("github.com/frontend-team/plugins", pattern) is True
        assert fnmatch_with_globstar("github.com/other/v1/plugins", pattern) is False

    def test_double_star_middle(self) -> None:
        """Double star in middle of pattern."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        pattern = "github.com/sundsvall-*/**/plugins"
        assert (
            fnmatch_with_globstar("github.com/sundsvall-backend/team/v1/plugins", pattern) is True
        )
        assert fnmatch_with_globstar("github.com/sundsvall-frontend/plugins", pattern) is True
        assert fnmatch_with_globstar("github.com/other-org/plugins", pattern) is False

    def test_no_globstar_behaves_like_fnmatch(self) -> None:
        """Without **, behaves like standard fnmatch."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("github.com/org/repo", "github.com/org/repo") is True
        assert fnmatch_with_globstar("github.com/org/repo", "github.com/*/repo") is True
        assert fnmatch_with_globstar("github.com/org/repo", "*.com/org/*") is True

    def test_empty_inputs(self) -> None:
        """Empty inputs return False."""
        from scc_cli.marketplace.normalize import fnmatch_with_globstar

        assert fnmatch_with_globstar("", "**") is False
        assert fnmatch_with_globstar("text", "") is False


class TestMatchesUrlPattern:
    """Tests for URL pattern matching combining normalization and globstar."""

    def test_github_https_url_matches_pattern(self) -> None:
        """GitHub HTTPS URL matches pattern."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        url = "https://github.com/sundsvall/plugins"
        pattern = "github.com/sundsvall/**"
        assert matches_url_pattern(url, pattern) is True

    def test_github_ssh_url_matches_pattern(self) -> None:
        """GitHub SSH URL matches same pattern as HTTPS."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        url = "git@github.com:sundsvall/plugins.git"
        pattern = "github.com/sundsvall/**"
        assert matches_url_pattern(url, pattern) is True

    def test_gitlab_url_matches_pattern(self) -> None:
        """GitLab URL matches pattern."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        url = "https://gitlab.sundsvall.se/teams/backend/plugins"
        pattern = "gitlab.sundsvall.se/**/plugins"
        assert matches_url_pattern(url, pattern) is True

    def test_pattern_with_org_wildcard(self) -> None:
        """Pattern with org wildcard matches multiple orgs."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        pattern = "github.com/sundsvall-*/**"
        assert matches_url_pattern("https://github.com/sundsvall-backend/plugins", pattern) is True
        assert matches_url_pattern("https://github.com/sundsvall-frontend/tools", pattern) is True
        assert matches_url_pattern("https://github.com/other-org/plugins", pattern) is False

    def test_no_match_different_host(self) -> None:
        """Different host doesn't match."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        url = "https://gitlab.com/org/repo"
        pattern = "github.com/**"
        assert matches_url_pattern(url, pattern) is False

    def test_case_insensitive_host(self) -> None:
        """Host matching is case-insensitive."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        url = "https://GITHUB.COM/org/repo"
        pattern = "github.com/**"
        assert matches_url_pattern(url, pattern) is True

    def test_empty_url_no_match(self) -> None:
        """Empty URL doesn't match any pattern."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        assert matches_url_pattern("", "github.com/**") is False

    def test_empty_pattern_no_match(self) -> None:
        """Empty pattern doesn't match any URL."""
        from scc_cli.marketplace.normalize import matches_url_pattern

        assert matches_url_pattern("https://github.com/org/repo", "") is False


class TestMatchesAnyUrlPattern:
    """Tests for matching URL against multiple patterns."""

    def test_matches_first_pattern(self) -> None:
        """Returns first matching pattern."""
        from scc_cli.marketplace.normalize import matches_any_url_pattern

        url = "https://github.com/sundsvall/plugins"
        patterns = ["github.com/sundsvall/**", "gitlab.com/**"]
        result = matches_any_url_pattern(url, patterns)
        assert result == "github.com/sundsvall/**"

    def test_matches_second_pattern(self) -> None:
        """Returns pattern if first doesn't match."""
        from scc_cli.marketplace.normalize import matches_any_url_pattern

        url = "https://gitlab.com/org/repo"
        patterns = ["github.com/**", "gitlab.com/**"]
        result = matches_any_url_pattern(url, patterns)
        assert result == "gitlab.com/**"

    def test_no_match_returns_none(self) -> None:
        """Returns None if no patterns match."""
        from scc_cli.marketplace.normalize import matches_any_url_pattern

        url = "https://bitbucket.org/team/repo"
        patterns = ["github.com/**", "gitlab.com/**"]
        result = matches_any_url_pattern(url, patterns)
        assert result is None

    def test_empty_patterns_returns_none(self) -> None:
        """Empty pattern list returns None."""
        from scc_cli.marketplace.normalize import matches_any_url_pattern

        url = "https://github.com/org/repo"
        result = matches_any_url_pattern(url, [])
        assert result is None


class TestGetSourceUrl:
    """Tests for extracting URL from MarketplaceSource types."""

    def test_github_source_returns_full_url(self) -> None:
        """GitHub source returns https://github.com/owner/repo format."""
        from scc_cli.marketplace.normalize import get_source_url
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        source = MarketplaceSourceGitHub(source="github", owner="sundsvall", repo="plugins")
        result = get_source_url(source)
        assert result == "https://github.com/sundsvall/plugins"

    def test_git_source_returns_url_directly(self) -> None:
        """Git source returns the URL as provided."""
        from scc_cli.marketplace.normalize import get_source_url
        from scc_cli.marketplace.schema import MarketplaceSourceGit

        source = MarketplaceSourceGit(source="git", url="https://gitlab.example.se/ai/plugins.git")
        result = get_source_url(source)
        assert result == "https://gitlab.example.se/ai/plugins.git"

    def test_url_source_returns_url_directly(self) -> None:
        """URL source returns the URL as provided."""
        from scc_cli.marketplace.normalize import get_source_url
        from scc_cli.marketplace.schema import MarketplaceSourceURL

        source = MarketplaceSourceURL(source="url", url="https://plugins.example.com/v1")
        result = get_source_url(source)
        assert result == "https://plugins.example.com/v1"

    def test_directory_source_returns_path(self) -> None:
        """Directory source returns the local path."""
        from scc_cli.marketplace.normalize import get_source_url
        from scc_cli.marketplace.schema import MarketplaceSourceDirectory

        source = MarketplaceSourceDirectory(source="directory", path="/opt/plugins")
        result = get_source_url(source)
        assert result == "/opt/plugins"

    def test_git_ssh_url_returns_as_is(self) -> None:
        """Git SSH URL is returned without transformation."""
        from scc_cli.marketplace.normalize import get_source_url
        from scc_cli.marketplace.schema import MarketplaceSourceGit

        source = MarketplaceSourceGit(source="git", url="git@github.com:org/repo.git")
        result = get_source_url(source)
        assert result == "git@github.com:org/repo.git"
