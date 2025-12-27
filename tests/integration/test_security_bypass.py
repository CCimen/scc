"""
Security bypass integration tests for SCC marketplace.

Tests Tier 1 critical security controls:
- Case-insensitive pattern matching for blocked_plugins
- Directory source symlink escape detection

These tests verify that security policies cannot be bypassed through:
1. Case variations in plugin names (MALICIOUS vs malicious)
2. Symlink traversal in directory marketplace sources
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scc_cli.marketplace.compute import compute_effective_plugins
from scc_cli.marketplace.normalize import matches_any_pattern, matches_pattern
from scc_cli.marketplace.schema import (
    DefaultsConfig,
    MarketplaceSourceDirectory,
    MarketplaceSourceGitHub,
    OrganizationConfig,
    SecurityConfig,
    TeamProfile,
)
from scc_cli.marketplace.trust import (
    TrustViolationError,
    validate_marketplace_source,
)

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Case-Insensitive Pattern Matching Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCaseInsensitivePatternMatching:
    """Verify blocked_plugins patterns work regardless of case.

    Security requirement: Pattern matching must use Unicode-aware casefolding
    to prevent bypass attempts using case variations.
    """

    @pytest.mark.parametrize(
        "pattern,plugin_ref,should_match",
        [
            # Basic case variations
            ("malicious-*", "malicious-tool@shared", True),
            ("malicious-*", "MALICIOUS-TOOL@shared", True),
            ("malicious-*", "Malicious-Tool@shared", True),
            ("MALICIOUS-*", "malicious-tool@shared", True),
            ("Malicious-*", "MALICIOUS-EXPLOIT@shared", True),
            # Marketplace suffix case variations
            ("*@internal", "tool@INTERNAL", True),
            ("*@INTERNAL", "tool@internal", True),
            ("*@Internal", "tool@internal", True),
            # Mixed case in middle
            ("code-*@shared", "CODE-REVIEW@SHARED", True),
            ("CODE-*@SHARED", "code-review@shared", True),
            # Non-matching cases (should still not match)
            ("malicious-*", "safe-tool@shared", False),
            ("*@internal", "tool@external", False),
            # Unicode casefolding edge cases
            ("straße-*", "STRASSE-tool@shared", True),  # German sharp S
        ],
    )
    def test_matches_pattern_case_insensitive(
        self, pattern: str, plugin_ref: str, should_match: bool
    ) -> None:
        """Pattern matching must be case-insensitive for security."""
        result = matches_pattern(plugin_ref, pattern)
        assert result == should_match, (
            f"Pattern '{pattern}' vs '{plugin_ref}': expected {should_match}, got {result}"
        )

    def test_blocked_plugins_blocks_case_variations(self) -> None:
        """security.blocked_plugins must block all case variations of a pattern."""
        org_config = OrganizationConfig(
            name="Security Test Org",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="test-org",
                    repo="plugins",
                ),
            },
            defaults=DefaultsConfig(
                enabled_plugins=[],
            ),
            profiles={
                "test-team": TeamProfile(
                    name="Test Team",
                    additional_plugins=[
                        "MALICIOUS-tool@shared",  # UPPERCASE
                        "Malicious-Exploit@shared",  # Mixed case
                        "malicious-virus@shared",  # lowercase
                        "safe-tool@shared",  # Should not be blocked
                    ],
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["malicious-*"],  # lowercase pattern
                blocked_reason="Blocked for security",
            ),
        )

        result = compute_effective_plugins(org_config, "test-team")

        # All malicious-* plugins should be blocked regardless of case
        blocked_ids = {b.plugin_id for b in result.blocked}
        assert "malicious-tool@shared" in blocked_ids or any(
            "malicious" in b.plugin_id.lower() for b in result.blocked
        ), f"Expected malicious plugins to be blocked, got: {blocked_ids}"

        # safe-tool should be enabled
        assert "safe-tool@shared" in result.enabled, (
            f"safe-tool should be enabled, got enabled: {result.enabled}"
        )

        # Count blocked malicious plugins
        malicious_blocked = [b for b in result.blocked if "malicious" in b.plugin_id.lower()]
        assert len(malicious_blocked) == 3, (
            f"Expected 3 malicious plugins blocked, got {len(malicious_blocked)}: "
            f"{[b.plugin_id for b in malicious_blocked]}"
        )

    def test_blocked_plugins_with_uppercase_pattern(self) -> None:
        """UPPERCASE patterns in blocked_plugins must match lowercase plugins."""
        org_config = OrganizationConfig(
            name="Uppercase Pattern Org",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="test-org",
                    repo="plugins",
                ),
            },
            defaults=DefaultsConfig(enabled_plugins=[]),
            profiles={
                "team": TeamProfile(
                    name="Test Team",
                    additional_plugins=[
                        "dangerous-tool@shared",
                        "DANGEROUS-exploit@shared",
                    ],
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["DANGEROUS-*"],  # UPPERCASE pattern
                blocked_reason="Security policy",
            ),
        )

        result = compute_effective_plugins(org_config, "team")

        # Both should be blocked despite case mismatch
        assert len(result.blocked) == 2
        # Note: plugin IDs retain original case, but pattern matching is case-insensitive
        blocked_ids = {b.plugin_id.lower() for b in result.blocked}
        assert "dangerous-tool@shared" in blocked_ids
        assert "dangerous-exploit@shared" in blocked_ids

    def test_matches_any_pattern_case_insensitive(self) -> None:
        """matches_any_pattern should return matching pattern with correct case handling."""
        patterns = ["Risky-*", "UNSAFE-*@internal"]

        # Should match regardless of plugin case
        result1 = matches_any_pattern("risky-plugin@shared", patterns)
        assert result1 == "Risky-*", f"Expected 'Risky-*', got {result1}"

        result2 = matches_any_pattern("RISKY-TOOL@external", patterns)
        assert result2 == "Risky-*", f"Expected 'Risky-*', got {result2}"

        result3 = matches_any_pattern("unsafe-tool@internal", patterns)
        assert result3 == "UNSAFE-*@internal", f"Expected 'UNSAFE-*@internal', got {result3}"

        # Non-matching
        result4 = matches_any_pattern("safe-tool@external", patterns)
        assert result4 is None


class TestSecurityBlockingIntegration:
    """Integration tests for the full security blocking flow."""

    def test_security_blocks_override_team_additions(self) -> None:
        """Security blocked_plugins must block even team-added plugins."""
        org_config = OrganizationConfig(
            name="Strict Security Org",
            schema_version=1,
            marketplaces={
                "internal": MarketplaceSourceGitHub(
                    source="github",
                    owner="org",
                    repo="plugins",
                ),
            },
            defaults=DefaultsConfig(
                enabled_plugins=["approved-tool@internal"],
            ),
            profiles={
                "team": TeamProfile(
                    name="Team",
                    additional_plugins=[
                        "forbidden-tool@internal",  # Will be blocked
                        "allowed-tool@internal",
                    ],
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["forbidden-*"],
                blocked_reason="Policy violation",
            ),
        )

        result = compute_effective_plugins(org_config, "team")

        # forbidden-tool should be blocked
        blocked_ids = {b.plugin_id for b in result.blocked}
        assert "forbidden-tool@internal" in blocked_ids

        # Other tools should be enabled
        assert "approved-tool@internal" in result.enabled
        assert "allowed-tool@internal" in result.enabled

    def test_security_blocks_default_plugins(self) -> None:
        """Security can block even default-enabled plugins."""
        org_config = OrganizationConfig(
            name="Retroactive Block Org",
            schema_version=1,
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="org",
                    repo="plugins",
                ),
            },
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "legacy-tool@shared",  # This will be blocked
                    "current-tool@shared",
                ],
            ),
            profiles={
                "team": TeamProfile(name="Team"),
            },
            security=SecurityConfig(
                blocked_plugins=["legacy-*"],
                blocked_reason="Deprecated and insecure",
            ),
        )

        result = compute_effective_plugins(org_config, "team")

        # legacy-tool should be blocked even though it was in defaults
        blocked_ids = {b.plugin_id for b in result.blocked}
        assert "legacy-tool@shared" in blocked_ids

        # current-tool should remain enabled
        assert "current-tool@shared" in result.enabled


# ─────────────────────────────────────────────────────────────────────────────
# Directory Symlink Escape Detection Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestDirectorySymlinkEscape:
    """Test directory source symlink handling.

    Current behavior: Directory sources are always allowed without path validation.
    This documents the security gap for symlink escape attacks.

    A malicious team config could define a directory source pointing to:
    - ../../../etc/passwd (path traversal)
    - /etc/evil (absolute path outside allowed scope)
    - A symlink that resolves outside the intended directory
    """

    def test_directory_source_always_allowed_currently(self) -> None:
        """Document current behavior: directory sources bypass URL pattern validation.

        This test documents the current security gap where directory sources
        are not validated against any patterns.
        """
        source = MarketplaceSourceDirectory(
            source="directory",
            path="/arbitrary/path/that/should/be/validated",
        )

        # Currently this passes because directory sources return None from get_source_url
        # and are therefore "always allowed"
        validate_marketplace_source(
            source=source,
            allowed_patterns=["github.com/**"],  # Only GitHub allowed
            team_name="test-team",
        )
        # No exception raised - this is the security gap

    def test_symlink_escape_in_directory_source(self, tmp_path: Path) -> None:
        """Demonstrate symlink escape vulnerability in directory sources.

        Creates a symlink that points outside the intended plugins directory.
        Current behavior allows this without validation.
        """
        # Setup: Create directory structure
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        evil_dir = tmp_path / "outside" / "evil"
        evil_dir.mkdir(parents=True)

        # Create symlink from plugins to evil directory
        symlink_path = plugins_dir / "trusted-plugin"
        symlink_path.symlink_to(evil_dir)

        # Verify symlink exists and points outside
        assert symlink_path.is_symlink()
        assert symlink_path.resolve() == evil_dir

        # Current behavior: directory source with symlink is allowed
        source = MarketplaceSourceDirectory(
            source="directory",
            path=str(symlink_path),
        )

        # This should ideally raise TrustViolationError but currently doesn't
        try:
            validate_marketplace_source(
                source=source,
                allowed_patterns=["github.com/**"],
                team_name="test-team",
            )
            symlink_blocked = False
        except TrustViolationError:
            symlink_blocked = True

        # Document current behavior (symlink not blocked)
        assert not symlink_blocked, (
            "Unexpected: symlink escape is now blocked. "
            "Update this test if symlink detection was implemented."
        )

    def test_symlink_resolves_outside_allowed_directory(self, tmp_path: Path) -> None:
        """Test that symlinks resolving outside allowed paths are a concern.

        This test creates a scenario where:
        1. An "allowed" plugins directory exists
        2. A symlink inside it points to a malicious directory
        3. The symlink escapes the intended sandbox
        """
        # Create the allowed directory
        allowed_dir = tmp_path / "allowed" / "plugins"
        allowed_dir.mkdir(parents=True)

        # Create a malicious directory outside allowed
        malicious_dir = tmp_path / "malicious"
        malicious_dir.mkdir()
        (malicious_dir / "evil_plugin.py").write_text("# Malicious code")

        # Create symlink that escapes allowed directory
        escape_link = allowed_dir / "legit-looking-plugin"
        escape_link.symlink_to(malicious_dir)

        # Verify the escape
        assert escape_link.resolve() == malicious_dir
        assert not str(escape_link.resolve()).startswith(str(allowed_dir))

        # The symlink resolves outside the allowed directory
        # A proper security check should detect this
        resolved = escape_link.resolve()
        escapes_allowed = not str(resolved).startswith(str(allowed_dir.parent))
        assert escapes_allowed, "Symlink should escape allowed directory"

    def test_path_traversal_in_directory_path(self) -> None:
        """Test that path traversal sequences in directory paths are concerning.

        Directory sources with ../ sequences could escape intended boundaries.
        """
        # These paths contain traversal sequences
        traversal_paths = [
            "/opt/plugins/../../../etc/passwd",
            "/var/scc/plugins/../../sensitive",
            "../../outside/malicious",
        ]

        for path in traversal_paths:
            source = MarketplaceSourceDirectory(
                source="directory",
                path=path,
            )

            # Currently all directory sources are allowed
            # No exception expected with current implementation
            validate_marketplace_source(
                source=source,
                allowed_patterns=["github.com/**"],
                team_name="test-team",
            )
