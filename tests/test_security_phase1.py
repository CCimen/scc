"""Phase 1 Security Tests for SCC v2.

TDD tests for Phase 1 security features:
- Case-insensitive blocking with casefold()
- Implicit :latest image normalization
- stdio MCP feature gate and path validation

Reference: SCC v2 Validation Plan (zesty-marinating-swan.md)
"""

from __future__ import annotations

from typing import Any

import pytest

from scc_cli import profiles

# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def org_config_with_blocks() -> dict[str, Any]:
    """Org config with blocked patterns for testing."""
    return {
        "schema_version": "1.0.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "security": {
            "blocked_plugins": ["Malicious-*", "evil-*"],
            "blocked_mcp_servers": ["untrusted-*"],
            "blocked_base_images": ["*:latest", "docker.io/*"],
        },
        "defaults": {
            "allowed_plugins": ["approved-plugin"],
        },
        "delegation": {
            "teams": {"allow_additional_plugins": ["*"]},
            "projects": {"inherit_team_delegation": True},
        },
        "profiles": {
            "test-team": {
                "description": "Test team",
                "delegation": {"allow_project_overrides": True},
            },
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for case-insensitive matching with casefold()
# ═══════════════════════════════════════════════════════════════════════════════


class TestCaseInsensitiveBlocking:
    """Tests for case-insensitive pattern matching using casefold()."""

    def test_blocked_check_is_case_insensitive(self):
        """blocked_plugins: ['Malicious-*'] should block 'malicious-tool'.

        Pattern is uppercase, item is lowercase - should still match.
        """
        patterns = ["Malicious-*"]
        result = profiles.matches_blocked("malicious-tool", patterns)
        assert result is not None, "Should match case-insensitively"
        assert result == "Malicious-*"

    def test_lowercase_pattern_matches_uppercase_item(self):
        """blocked_plugins: ['evil-*'] should block 'EVIL-TOOL'."""
        patterns = ["evil-*"]
        result = profiles.matches_blocked("EVIL-TOOL", patterns)
        assert result is not None, "Should match case-insensitively"

    def test_mixed_case_matching(self):
        """Pattern and item with mixed case should match."""
        patterns = ["MaLiCiOuS-*"]
        result = profiles.matches_blocked("mAlIcIoUs-ToOl", patterns)
        assert result is not None, "Mixed case should match"

    def test_casefold_handles_german_eszett(self):
        """casefold() should handle German ß → ss conversion.

        This is the key reason to use casefold() over lower().
        """
        # ß casefolded becomes "ss"
        patterns = ["straße-*"]
        result = profiles.matches_blocked("STRASSE-TOOL", patterns)
        assert result is not None, "ß should casefold to ss and match"

    def test_exact_match_is_case_insensitive(self):
        """Exact matches (no wildcards) should also be case-insensitive."""
        patterns = ["BadPlugin"]
        result = profiles.matches_blocked("badplugin", patterns)
        assert result is not None, "Exact match should be case-insensitive"

    def test_whitespace_trimmed(self):
        """Leading/trailing whitespace should be trimmed."""
        patterns = ["  evil-*  "]
        result = profiles.matches_blocked("  evil-tool  ", patterns)
        assert result is not None, "Whitespace should be trimmed"

    def test_non_matching_is_none(self):
        """Non-matching items should return None."""
        patterns = ["Malicious-*"]
        result = profiles.matches_blocked("safe-tool", patterns)
        assert result is None

    def test_security_blocks_apply_after_merge(self, org_config_with_blocks, tmp_path):
        """Plugin added at project layer, blocked by org → in blocked_items.

        This is an integration test ensuring the full flow works.
        """
        # Create project config that tries to add a blocked plugin
        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_plugins:
  - malicious-tool
""")

        effective = profiles.compute_effective_config(
            org_config=org_config_with_blocks,
            team_name="test-team",
            workspace_path=tmp_path,
        )

        # Should NOT be in plugins
        assert "malicious-tool" not in effective.plugins

        # Should be in blocked_items
        blocked_names = [b.item for b in effective.blocked_items]
        assert "malicious-tool" in blocked_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for implicit :latest normalization
# ═══════════════════════════════════════════════════════════════════════════════


class TestImageNormalization:
    """Tests for Docker base image normalization."""

    def test_image_implicit_latest_blocked(self):
        """Image "ubuntu" (no tag) should be normalized to ubuntu:latest.

        Given: blocked_base_images: ["*:latest"]
        When: Image "ubuntu" (no tag) is used
        Then: Image appears in blocked_items (normalized to ubuntu:latest)
        """
        # This test will fail until normalize_image_for_policy is implemented
        ref = profiles.normalize_image_for_policy("ubuntu")
        assert ref == "ubuntu:latest", "Untagged image should get :latest"

    def test_image_digest_not_forced_latest(self):
        """Image with digest should NOT have :latest appended.

        Given: blocked_base_images: ["*:latest"]
        When: Image "nginx@sha256:abc123..." is used
        Then: Image is NOT blocked (digest overrides tag)
        """
        ref = profiles.normalize_image_for_policy("nginx@sha256:abc123")
        assert ":latest" not in ref, "Digest images should not get :latest"
        assert "nginx@sha256:abc123" in ref.lower()

    def test_image_explicit_tag_not_latest(self):
        """Image with explicit tag should NOT have :latest appended.

        Given: blocked_base_images: ["*:latest"]
        When: Image "python:3.11" is used
        Then: Image is NOT blocked (explicit tag)
        """
        ref = profiles.normalize_image_for_policy("python:3.11")
        assert ref == "python:3.11", "Explicit tag should be preserved"

    def test_normalization_is_case_insensitive(self):
        """Normalized images should be casefolded for matching."""
        ref = profiles.normalize_image_for_policy("Ubuntu")
        assert ref == "ubuntu:latest", "Should be lowercase"

    def test_empty_string_handled(self):
        """Empty string should return empty string."""
        ref = profiles.normalize_image_for_policy("")
        assert ref == ""

    def test_whitespace_trimmed(self):
        """Whitespace should be trimmed."""
        ref = profiles.normalize_image_for_policy("  ubuntu  ")
        assert ref == "ubuntu:latest"

    def test_registry_with_port_handled(self):
        """registry:5000/ns/img should normalize correctly."""
        ref = profiles.normalize_image_for_policy("registry:5000/ns/img")
        assert ref == "registry:5000/ns/img:latest"

    def test_nested_path_with_tag(self):
        """ghcr.io/owner/repo:v1 should preserve tag."""
        ref = profiles.normalize_image_for_policy("ghcr.io/owner/repo:v1")
        assert ref == "ghcr.io/owner/repo:v1"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for stdio MCP feature gate
# ═══════════════════════════════════════════════════════════════════════════════


class TestStdioFeatureGate:
    """Tests for stdio MCP server feature gate."""

    def test_stdio_disabled_by_default(self):
        """org config without allow_stdio_mcp → stdio servers blocked.

        Given: org config has no security.allow_stdio_mcp setting
        When: stdio MCP server is configured
        Then: Server appears in blocked_items with reason "stdio MCP disabled by org policy"
        """
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            # Note: no security.allow_stdio_mcp
            "profiles": {
                "test-team": {
                    "additional_mcp_servers": [
                        {"name": "local-tool", "type": "stdio", "command": "/usr/bin/tool"}
                    ],
                },
            },
        }

        result = profiles.validate_stdio_server(
            server={"name": "local-tool", "type": "stdio", "command": "/usr/bin/tool"},
            org_config=org_config,
        )

        assert result.blocked is True
        assert "disabled" in result.reason.lower()

    def test_stdio_allowed_when_enabled(self):
        """stdio servers allowed when allow_stdio_mcp is True."""
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "security": {"allow_stdio_mcp": True},
        }

        result = profiles.validate_stdio_server(
            server={"name": "local-tool", "type": "stdio", "command": "/usr/bin/tool"},
            org_config=org_config,
        )

        assert result.blocked is False


class TestStdioPathValidation:
    """Tests for stdio command path validation."""

    def test_stdio_rejects_relative_path(self):
        """Relative paths should be blocked.

        Given: security.allow_stdio_mcp: true
        When: stdio command is "./local-script"
        Then: Server blocked with "stdio command must be absolute path"
        """
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "security": {"allow_stdio_mcp": True},
        }

        result = profiles.validate_stdio_server(
            server={"name": "tool", "type": "stdio", "command": "./local-script"},
            org_config=org_config,
        )

        assert result.blocked is True
        assert "absolute" in result.reason.lower()

    def test_stdio_prefix_commonpath_blocks_traversal(self, tmp_path):
        """Path traversal attempts should be blocked.

        Given: allowed_stdio_prefixes: ["/usr/local/bin/"]
        When: Command is "/usr/local/bin/../../bin/evil" (path traversal)
        Then: Server blocked (realpath resolves to /usr/bin/evil, outside prefix)

        Note: The path must go UP twice (../../) to escape /usr/local/bin:
        - /usr/local/bin/../bin/evil → /usr/local/bin/evil (still under prefix!)
        - /usr/local/bin/../../bin/evil → /usr/bin/evil (escapes prefix!)
        """
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "security": {
                "allow_stdio_mcp": True,
                "allowed_stdio_prefixes": ["/usr/local/bin/"],
            },
        }

        result = profiles.validate_stdio_server(
            server={
                "name": "evil",
                "type": "stdio",
                "command": "/usr/local/bin/../../bin/evil",
            },
            org_config=org_config,
        )

        assert result.blocked is True
        assert "prefix" in result.reason.lower()

    def test_stdio_prefix_allows_valid_path(self, tmp_path):
        """Valid paths under prefix should be allowed.

        Given: allowed_stdio_prefixes: ["/usr/local/bin/"]
        When: Command is "/usr/local/bin/approved-tool"
        Then: Server is allowed
        """
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "security": {
                "allow_stdio_mcp": True,
                "allowed_stdio_prefixes": ["/usr/local/bin/"],
            },
        }

        # Create test file (on macOS /usr/local/bin may not exist in CI)
        test_bin = tmp_path / "bin"
        test_bin.mkdir()
        test_tool = test_bin / "approved-tool"
        test_tool.touch()
        test_tool.chmod(0o755)

        result = profiles.validate_stdio_server(
            server={
                "name": "good",
                "type": "stdio",
                "command": str(test_tool),
            },
            org_config={
                **org_config,
                "security": {
                    "allow_stdio_mcp": True,
                    "allowed_stdio_prefixes": [str(test_bin)],
                },
            },
        )

        assert result.blocked is False

    def test_stdio_no_prefixes_allows_any_absolute(self, tmp_path):
        """When no prefixes configured, any absolute path is allowed."""
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "security": {"allow_stdio_mcp": True},
            # Note: no allowed_stdio_prefixes
        }

        result = profiles.validate_stdio_server(
            server={
                "name": "tool",
                "type": "stdio",
                "command": "/any/absolute/path/tool",
            },
            org_config=org_config,
        )

        assert result.blocked is False

    def test_stdio_warns_on_missing_file(self, tmp_path):
        """Missing file should generate warning (not block).

        Host-side checks produce warnings, not blocks, because
        the command runs in a container with different filesystem.
        """
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "security": {"allow_stdio_mcp": True},
        }

        result = profiles.validate_stdio_server(
            server={
                "name": "tool",
                "type": "stdio",
                "command": "/nonexistent/path/tool",
            },
            org_config=org_config,
        )

        # Should NOT block - just warn
        assert result.blocked is False
        assert len(result.warnings) > 0
        assert "not found" in result.warnings[0].lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for blocked_items vs denied_additions classification
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockedVsDeniedClassification:
    """Tests for proper classification of blocked_items vs denied_additions."""

    def test_blocked_items_are_security_violations(self, org_config_with_blocks, tmp_path):
        """Security blocks → blocked_items (not denied_additions).

        Given: blocked_plugins: ["evil-*"]
        When: Project tries to enable "evil-tool"
        Then: Appears in blocked_items (not denied_additions)
        """
        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_plugins:
  - evil-tool
""")

        effective = profiles.compute_effective_config(
            org_config=org_config_with_blocks,
            team_name="test-team",
            workspace_path=tmp_path,
        )

        blocked_names = [b.item for b in effective.blocked_items]
        denied_names = [d.item for d in effective.denied_additions]

        assert "evil-tool" in blocked_names
        assert "evil-tool" not in denied_names

    def test_denied_additions_are_delegation_failures(self, tmp_path):
        """Delegation failures → denied_additions (not blocked_items).

        Given: Team does not have delegation for plugins
        When: Project tries to add a new plugin
        Then: Appears in denied_additions (not blocked_items)
        """
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "security": {},  # No blocked patterns
            "delegation": {
                "teams": {},  # No delegation granted
            },
            "profiles": {
                "test-team": {"description": "Test team"},
            },
        }

        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_plugins:
  - new-plugin
""")

        effective = profiles.compute_effective_config(
            org_config=org_config,
            team_name="test-team",
            workspace_path=tmp_path,
        )

        blocked_names = [b.item for b in effective.blocked_items]
        denied_names = [d.item for d in effective.denied_additions]

        # Not blocked (no security pattern matched)
        assert "new-plugin" not in blocked_names
        # Denied due to lack of delegation
        assert "new-plugin" in denied_names
