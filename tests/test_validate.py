"""Tests for validate module.

Tests schema validation for organization configs with offline-capable bundled schema.
"""

import pytest

from scc_cli import validate

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def valid_org_config():
    """Create a valid organization config matching v1 schema."""
    return {
        "schema_version": "1.0.0",
        "min_cli_version": "1.0.0",
        "organization": {
            "name": "Test Organization",
            "id": "test-org",
            "contact": "devops@test.org",
        },
        "security": {
            "blocked_plugins": ["malicious-*"],
            "blocked_mcp_servers": ["*.untrusted.com"],
            "blocked_base_images": ["*:latest"],
        },
        "profiles": {
            "backend": {
                "description": "Backend team",
                "additional_plugins": ["backend-tools"],
            },
            "frontend": {
                "description": "Frontend team",
                "additional_plugins": ["frontend-tools"],
            },
        },
        "defaults": {
            "allowed_plugins": ["core-*"],
            "network_policy": "unrestricted",
        },
    }


@pytest.fixture
def minimal_org_config():
    """Create a minimal valid organization config."""
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Minimal Org",
            "id": "minimal-org",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for load_bundled_schema
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadBundledSchema:
    """Tests for load_bundled_schema function."""

    def test_load_bundled_schema_v1(self):
        """Should load v1 schema from package resources."""
        schema = validate.load_bundled_schema("v1")
        assert schema["$id"] == "https://scc-cli.dev/schemas/org-v1.json"
        assert "organization" in schema["properties"]

    def test_load_bundled_schema_default_version(self):
        """Should default to v1 schema."""
        schema = validate.load_bundled_schema()
        assert "organization" in schema["properties"]

    def test_load_bundled_schema_invalid_version(self):
        """Should raise error for unknown schema version."""
        with pytest.raises(FileNotFoundError):
            validate.load_bundled_schema("v99")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for validate_org_config
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateOrgConfig:
    """Tests for validate_org_config function."""

    def test_validate_valid_config(self, valid_org_config):
        """Valid config should return empty error list."""
        errors = validate.validate_org_config(valid_org_config)
        assert errors == []

    def test_validate_minimal_config(self, minimal_org_config):
        """Minimal config should be valid."""
        errors = validate.validate_org_config(minimal_org_config)
        assert errors == []

    def test_validate_missing_organization(self):
        """Missing organization should return error."""
        config = {"schema_version": "1.0.0"}
        errors = validate.validate_org_config(config)
        assert len(errors) >= 1
        assert any("organization" in e.lower() for e in errors)

    def test_validate_missing_org_name(self):
        """Missing organization.name should return error."""
        config = {"organization": {"id": "test-org"}}
        errors = validate.validate_org_config(config)
        assert len(errors) >= 1
        assert any("name" in e.lower() for e in errors)

    def test_validate_missing_org_id(self):
        """Missing organization.id should return error."""
        config = {"organization": {"name": "Test"}}
        errors = validate.validate_org_config(config)
        assert len(errors) >= 1
        assert any("id" in e.lower() for e in errors)

    def test_validate_invalid_org_id_format(self):
        """Organization.id with invalid characters should return error."""
        config = {"organization": {"name": "Test", "id": "Test Org!"}}
        errors = validate.validate_org_config(config)
        assert len(errors) >= 1

    def test_validate_invalid_schema_version_format(self):
        """Invalid schema_version format should return error."""
        config = {
            "schema_version": "invalid",
            "organization": {"name": "Test", "id": "test"},
        }
        errors = validate.validate_org_config(config)
        assert len(errors) >= 1
        assert any("schema_version" in e for e in errors)

    def test_validate_invalid_network_policy(self, valid_org_config):
        """Invalid network_policy value should return error."""
        valid_org_config["defaults"]["network_policy"] = "invalid-policy"
        errors = validate.validate_org_config(valid_org_config)
        assert len(errors) >= 1

    def test_validate_invalid_blocked_plugins_type(self, valid_org_config):
        """Invalid blocked_plugins type should return error."""
        valid_org_config["security"]["blocked_plugins"] = "not-a-list"
        errors = validate.validate_org_config(valid_org_config)
        assert len(errors) >= 1

    def test_validate_error_includes_path(self):
        """Validation errors should include path to error location."""
        config = {
            "organization": {"name": "Test", "id": "test"},
            "defaults": {"network_policy": "invalid-value"},
        }
        errors = validate.validate_org_config(config)
        # Should include path like "defaults/network_policy"
        assert any("defaults" in e.lower() or "network_policy" in e.lower() for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_schema_version
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckSchemaVersion:
    """Tests for check_schema_version function."""

    def test_compatible_same_version(self):
        """Same major version should be compatible."""
        compatible, message = validate.check_schema_version("1.0.0", "1.0.0")
        assert compatible is True
        assert message is None

    def test_compatible_minor_upgrade(self):
        """Higher minor version should be compatible with warning."""
        compatible, message = validate.check_schema_version("1.5.0", "1.2.0")
        assert compatible is True
        # May include warning about newer config

    def test_compatible_patch_upgrade(self):
        """Higher patch version should be compatible."""
        compatible, message = validate.check_schema_version("1.0.5", "1.0.0")
        assert compatible is True

    def test_incompatible_major_upgrade(self):
        """Higher major version should be incompatible."""
        compatible, message = validate.check_schema_version("2.0.0", "1.0.0")
        assert compatible is False
        assert message is not None
        assert "upgrade" in message.lower()

    def test_compatible_cli_higher_version(self):
        """CLI higher than config should be compatible."""
        compatible, message = validate.check_schema_version("1.0.0", "1.5.0")
        assert compatible is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_min_cli_version
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckMinCliVersion:
    """Tests for check_min_cli_version function."""

    def test_cli_meets_requirement(self):
        """CLI at or above min version should pass."""
        ok, message = validate.check_min_cli_version("1.0.0", "1.5.0")
        assert ok is True
        assert message is None

    def test_cli_exactly_meets_requirement(self):
        """CLI exactly at min version should pass."""
        ok, message = validate.check_min_cli_version("1.5.0", "1.5.0")
        assert ok is True

    def test_cli_below_requirement(self):
        """CLI below min version should fail."""
        ok, message = validate.check_min_cli_version("2.0.0", "1.5.0")
        assert ok is False
        assert message is not None
        assert "upgrade" in message.lower() or "2.0.0" in message

    def test_minor_version_comparison(self):
        """Minor version should be compared correctly."""
        ok, _ = validate.check_min_cli_version("1.5.0", "1.4.0")
        assert ok is False

        ok, _ = validate.check_min_cli_version("1.5.0", "1.6.0")
        assert ok is True

    def test_patch_version_comparison(self):
        """Patch version should be compared correctly."""
        ok, _ = validate.check_min_cli_version("1.5.5", "1.5.4")
        assert ok is False

        ok, _ = validate.check_min_cli_version("1.5.5", "1.5.6")
        assert ok is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for parse_semver helper
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseSemver:
    """Tests for parse_semver helper function."""

    def test_parse_standard_version(self):
        """Should parse standard semver correctly."""
        major, minor, patch = validate.parse_semver("1.2.3")
        assert major == 1
        assert minor == 2
        assert patch == 3

    def test_parse_zero_version(self):
        """Should handle zero values."""
        major, minor, patch = validate.parse_semver("0.0.0")
        assert major == 0
        assert minor == 0
        assert patch == 0

    def test_parse_large_version(self):
        """Should handle large version numbers."""
        major, minor, patch = validate.parse_semver("10.200.3000")
        assert major == 10
        assert minor == 200
        assert patch == 3000

    def test_parse_invalid_format(self):
        """Should raise error for invalid format."""
        with pytest.raises(ValueError):
            validate.parse_semver("invalid")

    def test_parse_two_parts(self):
        """Should raise error for incomplete version."""
        with pytest.raises(ValueError):
            validate.parse_semver("1.2")
