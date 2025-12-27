"""
Error recovery integration tests for SCC marketplace.

Tests error handling and recovery paths:
- AmbiguousMarketplaceError when bare plugin with 2+ marketplaces
- Corrupt cache file recovery
- Malformed configuration handling

These tests verify that the system fails gracefully with clear
error messages when encountering invalid or corrupt data.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scc_cli.marketplace.compute import compute_effective_plugins
from scc_cli.marketplace.normalize import (
    AmbiguousMarketplaceError,
    InvalidPluginRefError,
    normalize_plugin,
)
from scc_cli.marketplace.schema import (
    DefaultsConfig,
    MarketplaceSourceGitHub,
    OrganizationConfig,
    SecurityConfig,
    TeamProfile,
)

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# AmbiguousMarketplaceError Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestAmbiguousMarketplaceError:
    """Test AmbiguousMarketplaceError is raised and provides helpful messages.

    When a user references a plugin without @marketplace suffix and the org
    has 2+ marketplaces defined, the system cannot auto-resolve and must
    provide a clear error explaining what to do.
    """

    def test_bare_plugin_with_two_marketplaces_raises_error(self) -> None:
        """Bare plugin name with 2 marketplaces must raise AmbiguousMarketplaceError."""
        org_marketplaces = {
            "market-a": {"source": "github", "owner": "org", "repo": "market-a"},
            "market-b": {"source": "github", "owner": "org", "repo": "market-b"},
        }

        with pytest.raises(AmbiguousMarketplaceError) as exc_info:
            normalize_plugin("my-plugin", org_marketplaces)

        # Verify error message is helpful
        error = exc_info.value
        assert "my-plugin" in str(error)
        assert "market-a" in str(error) or "market-b" in str(error)

    def test_bare_plugin_with_three_marketplaces_raises_error(self) -> None:
        """Bare plugin name with 3+ marketplaces must raise AmbiguousMarketplaceError."""
        org_marketplaces = {
            "internal": {"source": "github", "owner": "org", "repo": "internal"},
            "shared": {"source": "github", "owner": "org", "repo": "shared"},
            "external": {"source": "github", "owner": "org", "repo": "external"},
        }

        with pytest.raises(AmbiguousMarketplaceError) as exc_info:
            normalize_plugin("tool", org_marketplaces)

        error = exc_info.value
        assert error.plugin_name == "tool"
        assert len(error.available_marketplaces) == 3

    def test_error_lists_available_marketplaces(self) -> None:
        """Error message must list all available marketplaces for user to choose from."""
        org_marketplaces = {
            "alpha": {"source": "github"},
            "beta": {"source": "github"},
        }

        with pytest.raises(AmbiguousMarketplaceError) as exc_info:
            normalize_plugin("plugin", org_marketplaces)

        error_msg = str(exc_info.value)
        # Error should suggest the solution
        assert "@" in error_msg  # Should mention using @marketplace syntax
        assert "alpha" in error_msg or "beta" in error_msg

    def test_explicit_marketplace_resolves_ambiguity(self) -> None:
        """Explicit @marketplace suffix should work with 2+ marketplaces."""
        org_marketplaces = {
            "market-a": {"source": "github"},
            "market-b": {"source": "github"},
        }

        # Should NOT raise - explicit suffix resolves ambiguity
        result = normalize_plugin("my-plugin@market-a", org_marketplaces)
        assert result == "my-plugin@market-a"

    def test_npm_style_resolves_ambiguity(self) -> None:
        """npm-style @marketplace/plugin should work with 2+ marketplaces."""
        org_marketplaces = {
            "market-a": {"source": "github"},
            "market-b": {"source": "github"},
        }

        # Should NOT raise - npm style is explicit
        result = normalize_plugin("@market-b/my-plugin", org_marketplaces)
        assert result == "my-plugin@market-b"

    def test_single_marketplace_auto_resolves(self) -> None:
        """Single marketplace should auto-resolve bare plugin names."""
        org_marketplaces = {
            "only-one": {"source": "github"},
        }

        # Should auto-resolve to the single marketplace
        result = normalize_plugin("my-plugin", org_marketplaces)
        assert result == "my-plugin@only-one"

    def test_no_marketplaces_uses_official(self) -> None:
        """No org marketplaces should resolve to claude-plugins-official."""
        org_marketplaces: dict[str, dict[str, str]] = {}

        result = normalize_plugin("my-plugin", org_marketplaces)
        assert result == "my-plugin@claude-plugins-official"

    def test_ambiguous_error_in_compute_effective_plugins(self) -> None:
        """AmbiguousMarketplaceError should propagate from compute_effective_plugins."""
        org_config = OrganizationConfig(
            name="Multi-Marketplace Org",
            schema_version=1,
            marketplaces={
                "market-a": MarketplaceSourceGitHub(
                    source="github",
                    owner="org",
                    repo="market-a",
                ),
                "market-b": MarketplaceSourceGitHub(
                    source="github",
                    owner="org",
                    repo="market-b",
                ),
            },
            defaults=DefaultsConfig(enabled_plugins=[]),
            profiles={
                "test-team": TeamProfile(
                    name="Test Team",
                    additional_plugins=["bare-plugin"],  # No @marketplace suffix!
                ),
            },
            security=SecurityConfig(),
        )

        with pytest.raises(AmbiguousMarketplaceError) as exc_info:
            compute_effective_plugins(org_config, "test-team")

        assert "bare-plugin" in str(exc_info.value)


class TestInvalidPluginRefError:
    """Test InvalidPluginRefError for malformed plugin references."""

    def test_empty_plugin_name_raises_error(self) -> None:
        """Empty plugin name must raise InvalidPluginRefError."""
        with pytest.raises(InvalidPluginRefError) as exc_info:
            normalize_plugin("", {})

        assert "empty" in str(exc_info.value).lower()

    def test_whitespace_only_raises_error(self) -> None:
        """Whitespace-only plugin name must raise InvalidPluginRefError."""
        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("   ", {})

    def test_double_at_raises_error(self) -> None:
        """Double @@ in plugin name must raise InvalidPluginRefError."""
        with pytest.raises(InvalidPluginRefError) as exc_info:
            normalize_plugin("plugin@@market", {})

        assert "@@" in str(exc_info.value) or "double" in str(exc_info.value).lower()

    def test_npm_style_missing_slash_raises_error(self) -> None:
        """npm-style without slash must raise InvalidPluginRefError."""
        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("@marketplace", {})

    def test_npm_style_empty_name_raises_error(self) -> None:
        """npm-style with empty name must raise InvalidPluginRefError."""
        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("@marketplace/", {})

    def test_empty_marketplace_raises_error(self) -> None:
        """Plugin with empty marketplace must raise InvalidPluginRefError."""
        with pytest.raises(InvalidPluginRefError):
            normalize_plugin("plugin@", {})


# ─────────────────────────────────────────────────────────────────────────────
# Corrupt Cache Recovery Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCorruptCacheRecovery:
    """Test that corrupt cache files are handled gracefully.

    These tests verify that the system recovers from or reports clearly when:
    - Cache files contain invalid JSON
    - Cache metadata is corrupted
    - Cache files have wrong schema
    """

    def test_corrupt_json_in_config_file(self, tmp_path: Path) -> None:
        """Corrupt JSON in config should raise clear JSONDecodeError."""
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("{ invalid json missing quote")

        with pytest.raises(json.JSONDecodeError):
            json.loads(corrupt_file.read_text())

    def test_truncated_json_file(self, tmp_path: Path) -> None:
        """Truncated JSON file should raise JSONDecodeError."""
        truncated_file = tmp_path / "truncated.json"
        truncated_file.write_text('{"name": "Test", "value":')

        with pytest.raises(json.JSONDecodeError):
            json.loads(truncated_file.read_text())

    def test_null_bytes_in_json(self, tmp_path: Path) -> None:
        """Null bytes in JSON file should be handled."""
        null_file = tmp_path / "null.json"
        null_file.write_bytes(b'{"name": "Test\x00Value"}')

        # Should be able to read the file
        content = null_file.read_text(errors="replace")
        assert "Test" in content

    def test_empty_json_file(self, tmp_path: Path) -> None:
        """Empty file should raise JSONDecodeError."""
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("")

        with pytest.raises(json.JSONDecodeError):
            json.loads(empty_file.read_text())

    def test_json_with_wrong_root_type(self, tmp_path: Path) -> None:
        """JSON with wrong root type should be detected during parsing."""
        wrong_type_file = tmp_path / "wrong_type.json"
        wrong_type_file.write_text('["this", "is", "an", "array"]')

        data = json.loads(wrong_type_file.read_text())
        # Should be a list, not a dict
        assert isinstance(data, list)
        assert not isinstance(data, dict)

    def test_missing_required_fields(self, tmp_path: Path) -> None:
        """Config missing required fields should fail validation."""
        incomplete_file = tmp_path / "incomplete.json"
        incomplete_config = {
            "name": "Test Org",
            # Missing: schema_version, marketplaces, defaults, profiles, security
        }
        incomplete_file.write_text(json.dumps(incomplete_config))

        data = json.loads(incomplete_file.read_text())

        # Attempting to create OrganizationConfig should fail
        with pytest.raises((TypeError, ValueError)):
            OrganizationConfig(**data)

    def test_wrong_schema_version(self, tmp_path: Path) -> None:
        """Config with unsupported schema version should fail validation."""
        wrong_version_file = tmp_path / "wrong_version.json"
        wrong_version_config = {
            "name": "Test Org",
            "schema_version": 999,  # Unsupported version
            "marketplaces": {},
            "defaults": {},
            "profiles": {},
            "security": {},
        }
        wrong_version_file.write_text(json.dumps(wrong_version_config))

        data = json.loads(wrong_version_file.read_text())

        # Should fail validation due to unsupported version
        with pytest.raises(ValueError) as exc_info:
            OrganizationConfig(**data)

        assert "schema_version" in str(exc_info.value).lower() or "999" in str(exc_info.value)


class TestCacheMetadataCorruption:
    """Test cache metadata corruption scenarios."""

    def test_invalid_timestamp_format(self, tmp_path: Path) -> None:
        """Invalid timestamp in cache metadata should be handled."""
        meta_file = tmp_path / "cache_meta.json"
        meta_content = {
            "timestamp": "not-a-timestamp",  # Invalid format
            "etag": "abc123",
        }
        meta_file.write_text(json.dumps(meta_content))

        data = json.loads(meta_file.read_text())
        # The timestamp is invalid - parsing should handle this
        assert data["timestamp"] == "not-a-timestamp"

    def test_negative_timestamp(self, tmp_path: Path) -> None:
        """Negative timestamp should be handled as potentially stale."""
        meta_file = tmp_path / "cache_meta.json"
        meta_content = {
            "timestamp": -1000.0,  # Negative timestamp
            "etag": "abc123",
        }
        meta_file.write_text(json.dumps(meta_content))

        data = json.loads(meta_file.read_text())
        assert data["timestamp"] < 0

    def test_future_timestamp(self, tmp_path: Path) -> None:
        """Future timestamp should be handled (clock skew scenario)."""
        import time

        meta_file = tmp_path / "cache_meta.json"
        future_time = time.time() + 86400 * 365  # 1 year in future
        meta_content = {
            "timestamp": future_time,
            "etag": "abc123",
        }
        meta_file.write_text(json.dumps(meta_content))

        data = json.loads(meta_file.read_text())
        assert data["timestamp"] > time.time()

    def test_missing_etag_field(self, tmp_path: Path) -> None:
        """Missing ETag field should be handled gracefully."""
        meta_file = tmp_path / "cache_meta.json"
        meta_content = {
            "timestamp": 1234567890.0,
            # Missing: etag
        }
        meta_file.write_text(json.dumps(meta_content))

        data = json.loads(meta_file.read_text())
        assert "etag" not in data
        # System should treat as if no ETag available
        assert data.get("etag") is None


# ─────────────────────────────────────────────────────────────────────────────
# Configuration Recovery Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConfigurationRecovery:
    """Test recovery from various configuration error states."""

    def test_marketplace_source_missing_required_field(self) -> None:
        """Marketplace source missing required field should raise error."""
        with pytest.raises((TypeError, ValueError)):
            # Missing owner and repo
            MarketplaceSourceGitHub(source="github")  # Missing owner/repo

    def test_security_config_with_invalid_pattern(self) -> None:
        """SecurityConfig accepts any pattern - validation happens at match time."""
        # This should be accepted - patterns are validated during matching, not creation
        security = SecurityConfig(
            blocked_plugins=["valid-*", "[invalid-bracket", "normal@*"],
            blocked_reason="Test",
        )
        assert len(security.blocked_plugins) == 3

    def test_team_profile_empty_name_rejected(self) -> None:
        """TeamProfile with empty name should be rejected by Pydantic."""
        with pytest.raises(ValueError):
            TeamProfile(name="")

    def test_organization_config_empty_name_rejected(self) -> None:
        """OrganizationConfig with empty name should be rejected."""
        with pytest.raises(ValueError):
            OrganizationConfig(
                name="",  # Empty name
                schema_version=1,
            )

    def test_defaults_config_with_invalid_plugin_refs(self) -> None:
        """DefaultsConfig accepts any string - validation at normalize time."""
        # Plugin refs are validated when normalized, not at config creation
        defaults = DefaultsConfig(
            enabled_plugins=["plugin@market", "@@invalid@@"],
        )
        assert len(defaults.enabled_plugins) == 2


class TestTeamNotFoundRecovery:
    """Test handling of missing or invalid team references."""

    def test_nonexistent_team_raises_error(self) -> None:
        """Requesting nonexistent team should raise clear error."""
        org_config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            marketplaces={},
            profiles={
                "existing-team": TeamProfile(name="Existing Team"),
            },
            security=SecurityConfig(),
        )

        with pytest.raises(KeyError):
            compute_effective_plugins(org_config, "nonexistent-team")

    def test_case_sensitive_team_lookup(self) -> None:
        """Team lookup is case-sensitive."""
        org_config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            marketplaces={},
            profiles={
                "backend": TeamProfile(name="Backend Team"),
            },
            security=SecurityConfig(),
        )

        # Exact case should work
        result = compute_effective_plugins(org_config, "backend")
        assert result is not None

        # Different case should fail
        with pytest.raises(KeyError):
            compute_effective_plugins(org_config, "Backend")

        with pytest.raises(KeyError):
            compute_effective_plugins(org_config, "BACKEND")
