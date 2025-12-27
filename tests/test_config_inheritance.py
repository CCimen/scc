"""Tests for config inheritance (v2 schema) and effective config computation.

Tests schema validation, delegation logic, merge behavior, and blocking rules.
TDD: These tests are written first, before implementation.
"""

import pytest

from scc_cli import validate

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures - V2 Schema
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def valid_v2_org_config():
    """Create a valid v2 organization config with all features."""
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Sundsvall Municipality",
            "id": "sundsvall",
        },
        "security": {
            "blocked_plugins": ["known-malicious-*", "deprecated-tool"],
            "blocked_mcp_servers": ["*.untrusted.com", "evil.example.org"],
            "blocked_base_images": ["*:latest", "ubuntu:*"],
        },
        "defaults": {
            "allowed_plugins": ["github-copilot", "internal-docs"],
            "allowed_mcp_servers": ["*.sundsvall.se"],
            "network_policy": "corp-proxy-only",
            "session": {
                "timeout_hours": 8,
                "auto_resume": True,
            },
        },
        "delegation": {
            "teams": {
                "allow_additional_plugins": ["*"],
                "allow_additional_mcp_servers": ["urban-planning", "finance"],
                "allow_network_override": [],
            },
            "projects": {
                "inherit_team_delegation": True,
            },
        },
        "profiles": {
            "urban-planning": {
                "description": "Urban planning and GIS team",
                "additional_plugins": ["gis-tools"],
                "additional_mcp_servers": [
                    {
                        "name": "gis-internal",
                        "type": "sse",
                        "url": "https://gis.sundsvall.se/mcp",
                    }
                ],
                "delegation": {
                    "allow_project_overrides": True,
                },
            },
            "finance": {
                "description": "Finance team",
                "additional_plugins": ["excel-tools"],
                "delegation": {
                    "allow_project_overrides": False,
                },
            },
        },
        "stats": {
            "enabled": True,
            "user_identity_mode": "hash",
            "retention_days": 90,
        },
    }


@pytest.fixture
def minimal_v2_org_config():
    """Create a minimal valid v2 config with only required fields."""
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Minimal Org",
            "id": "minimal-org",
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for V2 Schema Loading
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadBundledSchemaV1:
    """Tests for loading v1 schema."""

    def test_load_bundled_schema_v1(self):
        """Should load v1 schema from package resources."""
        schema = validate.load_bundled_schema("v1")
        assert schema["$id"] == "https://scc-cli.dev/schemas/org-v1.json"
        assert "organization" in schema["properties"]
        assert "security" in schema["properties"]
        assert "delegation" in schema["properties"]
        assert "stats" in schema["properties"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for V2 Schema Validation - Security Block
# ═══════════════════════════════════════════════════════════════════════════════


class TestV2SchemaSecurityValidation:
    """Tests for security block validation in v2 schema."""

    def test_validate_valid_security_block(self, valid_v2_org_config):
        """Valid security block should pass validation."""
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_security_blocked_plugins_must_be_array(self, valid_v2_org_config):
        """Security blocked_plugins must be an array."""
        valid_v2_org_config["security"]["blocked_plugins"] = "not-an-array"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1
        assert any("blocked_plugins" in e for e in errors)

    def test_validate_security_blocked_plugins_items_must_be_strings(self, valid_v2_org_config):
        """Security blocked_plugins items must be strings."""
        valid_v2_org_config["security"]["blocked_plugins"] = [123, True]
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_security_blocked_mcp_servers_must_be_array(self, valid_v2_org_config):
        """Security blocked_mcp_servers must be an array."""
        valid_v2_org_config["security"]["blocked_mcp_servers"] = "not-an-array"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_security_blocked_base_images_must_be_array(self, valid_v2_org_config):
        """Security blocked_base_images must be an array."""
        valid_v2_org_config["security"]["blocked_base_images"] = "not-an-array"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for V2 Schema Validation - Defaults Block
# ═══════════════════════════════════════════════════════════════════════════════


class TestV2SchemaDefaultsValidation:
    """Tests for defaults block validation in v2 schema."""

    def test_validate_valid_defaults_block(self, valid_v2_org_config):
        """Valid defaults block should pass validation."""
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_defaults_session_timeout_positive(self, valid_v2_org_config):
        """Session timeout_hours must be positive."""
        valid_v2_org_config["defaults"]["session"]["timeout_hours"] = 0
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_defaults_session_timeout_reasonable_max(self, valid_v2_org_config):
        """Session timeout_hours must be reasonable (max 24 hours)."""
        valid_v2_org_config["defaults"]["session"]["timeout_hours"] = 100
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_defaults_network_policy_enum(self, valid_v2_org_config):
        """Network policy must be valid enum value."""
        valid_v2_org_config["defaults"]["network_policy"] = "invalid-policy"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1
        assert any("network_policy" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for V2 Schema Validation - Delegation Block
# ═══════════════════════════════════════════════════════════════════════════════


class TestV2SchemaDelegationValidation:
    """Tests for delegation block validation in v2 schema."""

    def test_validate_valid_delegation_block(self, valid_v2_org_config):
        """Valid delegation block should pass validation."""
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_delegation_teams_plugins_must_be_array(self, valid_v2_org_config):
        """Team delegation allow_additional_plugins must be an array."""
        valid_v2_org_config["delegation"]["teams"]["allow_additional_plugins"] = "not-an-array"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_delegation_projects_inherit_must_be_bool(self, valid_v2_org_config):
        """Project delegation inherit_team_delegation must be boolean."""
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = "yes"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for V2 Schema Validation - Profiles Block
# ═══════════════════════════════════════════════════════════════════════════════


class TestV2SchemaProfilesValidation:
    """Tests for profiles block validation in v2 schema."""

    def test_validate_valid_profile_with_delegation(self, valid_v2_org_config):
        """Valid profile with delegation should pass validation."""
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_profile_delegation_must_be_boolean(self, valid_v2_org_config):
        """Profile delegation.allow_project_overrides must be boolean."""
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = "yes"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_profile_additional_plugins_must_be_array(self, valid_v2_org_config):
        """Profile additional_plugins must be an array."""
        valid_v2_org_config["profiles"]["urban-planning"]["additional_plugins"] = "gis-tools"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_profile_mcp_server_requires_name_type_url(self, valid_v2_org_config):
        """MCP server must have name, type, and url."""
        valid_v2_org_config["profiles"]["urban-planning"]["additional_mcp_servers"] = [
            {"name": "missing-type-and-url"}
        ]
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_profile_mcp_server_type_enum(self, valid_v2_org_config):
        """MCP server type must be valid enum."""
        valid_v2_org_config["profiles"]["urban-planning"]["additional_mcp_servers"] = [
            {"name": "test", "type": "invalid-type", "url": "https://example.com"}
        ]
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for V2 Schema Validation - Stats Block
# ═══════════════════════════════════════════════════════════════════════════════


class TestV2SchemaStatsValidation:
    """Tests for stats block validation in v2 schema."""

    def test_validate_valid_stats_block(self, valid_v2_org_config):
        """Valid stats block should pass validation."""
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_stats_enabled_must_be_boolean(self, valid_v2_org_config):
        """Stats enabled must be boolean."""
        valid_v2_org_config["stats"]["enabled"] = "yes"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_stats_user_identity_mode_enum(self, valid_v2_org_config):
        """Stats user_identity_mode must be valid enum."""
        valid_v2_org_config["stats"]["user_identity_mode"] = "invalid-mode"
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1

    def test_validate_stats_retention_days_positive(self, valid_v2_org_config):
        """Stats retention_days must be positive."""
        valid_v2_org_config["stats"]["retention_days"] = 0
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert len(errors) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for V2 Schema Validation - Edge Cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestV2SchemaEdgeCases:
    """Tests for edge cases and minimal configs."""

    def test_validate_minimal_v2_config(self, minimal_v2_org_config):
        """Minimal v2 config should be valid."""
        errors = validate.validate_org_config(minimal_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_empty_security_block_is_valid(self, minimal_v2_org_config):
        """Empty security block should be valid (uses defaults)."""
        minimal_v2_org_config["security"] = {}
        errors = validate.validate_org_config(minimal_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_empty_delegation_block_is_valid(self, minimal_v2_org_config):
        """Empty delegation block should be valid (uses defaults)."""
        minimal_v2_org_config["delegation"] = {}
        errors = validate.validate_org_config(minimal_v2_org_config, schema_version="v1")
        assert errors == []

    def test_validate_empty_stats_block_is_valid(self, minimal_v2_org_config):
        """Empty stats block should be valid (uses defaults)."""
        minimal_v2_org_config["stats"] = {}
        errors = validate.validate_org_config(minimal_v2_org_config, schema_version="v1")
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Schema Version Detection
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaVersionDetection:
    """Tests for detecting and handling schema versions."""

    def test_detect_schema_version_v1(self):
        """Should detect v1 schema from schema_version field."""
        config = {"schema_version": "1.5.0"}
        version = validate.detect_schema_version(config)
        assert version == "v1"

    def test_detect_schema_version_missing_defaults_to_v1(self):
        """Missing schema_version should default to v1."""
        config = {"organization": {"name": "Test", "id": "test"}}
        version = validate.detect_schema_version(config)
        assert version == "v1"

    def test_detect_schema_version_invalid_format(self):
        """Invalid schema_version format should raise error."""
        config = {"schema_version": "invalid"}
        with pytest.raises(ValueError):
            validate.detect_schema_version(config)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Delegation Hierarchy
# ═══════════════════════════════════════════════════════════════════════════════


class TestDelegationHierarchy:
    """Tests for delegation hierarchy: org controls whether teams can delegate.

    Key rule: If org-level `inherit_team_delegation: false`, then team-level
    `allow_project_overrides` should be ignored (treated as false).
    """

    def test_org_disabled_inheritance_ignores_team_delegation(self, valid_v2_org_config):
        """When org disables inheritance, team delegation should be ignored."""
        # Org says teams cannot delegate to projects
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = False
        # Team says it wants to delegate
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        # Config should still be valid - this is a business logic rule, not schema
        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert errors == []
        # Note: The actual enforcement of this rule happens in compute_effective_config()

    def test_org_enabled_inheritance_respects_team_delegation(self, valid_v2_org_config):
        """When org enables inheritance, team delegation should be respected."""
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = False

        errors = validate.validate_org_config(valid_v2_org_config, schema_version="v1")
        assert errors == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for compute_effective_config() - Core Merge Logic
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def project_config():
    """Sample project config (.scc.yaml content)."""
    return {
        "additional_plugins": ["project-specific-tool"],
        "additional_mcp_servers": [
            {"name": "project-api", "type": "sse", "url": "https://api.internal/mcp"}
        ],
        "session": {"timeout_hours": 4},
    }


class TestComputeEffectiveConfigBasicMerge:
    """Tests for basic config merging: org defaults → team → project."""

    def test_org_defaults_only(self, valid_v2_org_config):
        """With no team or project, should return org defaults."""
        from scc_cli.profiles import compute_effective_config

        result = compute_effective_config(
            org_config=valid_v2_org_config, team_name=None, project_config=None
        )

        # Should have org defaults
        assert "github-copilot" in result.plugins
        assert "internal-docs" in result.plugins
        assert result.network_policy == "corp-proxy-only"
        assert result.session_config.timeout_hours == 8
        assert result.session_config.auto_resume is True

    def test_team_extends_org_defaults(self, valid_v2_org_config):
        """Team profile should extend org defaults, not replace."""
        from scc_cli.profiles import compute_effective_config

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=None,
        )

        # Should have org defaults PLUS team additions
        assert "github-copilot" in result.plugins  # from org
        assert "internal-docs" in result.plugins  # from org
        assert "gis-tools" in result.plugins  # from team

        # Should have team's MCP server
        mcp_names = [s.name for s in result.mcp_servers]
        assert "gis-internal" in mcp_names

    def test_project_extends_team_when_delegated(self, valid_v2_org_config, project_config):
        """Project should extend team config when delegation allows."""
        from scc_cli.profiles import compute_effective_config

        # Ensure delegation is enabled
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        # Should have all three layers
        assert "github-copilot" in result.plugins  # from org
        assert "gis-tools" in result.plugins  # from team
        assert "project-specific-tool" in result.plugins  # from project

        # Session should use project override
        assert result.session_config.timeout_hours == 4

    def test_minimal_config_uses_defaults(self, minimal_v2_org_config):
        """Minimal config should use sensible defaults."""
        from scc_cli.profiles import compute_effective_config

        result = compute_effective_config(
            org_config=minimal_v2_org_config, team_name=None, project_config=None
        )

        # Should have empty but valid result
        assert result.plugins == set()
        assert result.mcp_servers == []
        # Default network policy when not specified
        assert result.network_policy is None or result.network_policy == ""


class TestComputeEffectiveConfigDelegation:
    """Tests for delegation hierarchy enforcement.

    KEY RULE (from user clarification):
    - org-level inherit_team_delegation = master switch "can teams delegate at all?"
    - team-level allow_project_overrides = per-team "does this team delegate?"
    - If org says inherit_team_delegation: false, team setting should be IGNORED.
    """

    def test_org_disables_delegation_ignores_team_setting(
        self, valid_v2_org_config, project_config
    ):
        """When org disables inheritance, project additions should be rejected.

        FLAG: This is the critical delegation hierarchy rule.
        Even if team says allow_project_overrides: true, org's inherit_team_delegation: false
        should prevent project from adding anything.
        """
        from scc_cli.profiles import compute_effective_config

        # Org says: NO delegation to projects (master switch OFF)
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = False
        # Team says: I want to delegate (should be IGNORED)
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        # Project additions should NOT be included
        assert "project-specific-tool" not in result.plugins

        # Should have denied addition in tracking
        denied = [d for d in result.denied_additions if d.item == "project-specific-tool"]
        assert len(denied) == 1
        assert (
            "org disabled" in denied[0].reason.lower() or "inherit_team" in denied[0].reason.lower()
        )

    def test_org_enables_but_team_disables_delegation(self, valid_v2_org_config, project_config):
        """When org enables but team disables, project additions should be rejected."""
        from scc_cli.profiles import compute_effective_config

        # Org says: delegation CAN happen (master switch ON)
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        # Team says: I don't want to delegate (team-level OFF)
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = False

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        # Project additions should NOT be included
        assert "project-specific-tool" not in result.plugins

        # Tracking should show team denied it
        denied = [d for d in result.denied_additions if d.item == "project-specific-tool"]
        assert len(denied) == 1
        assert "team" in denied[0].reason.lower()

    def test_both_org_and_team_enable_delegation(self, valid_v2_org_config, project_config):
        """When both org and team enable, project additions should be allowed."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        # Project additions SHOULD be included
        assert "project-specific-tool" in result.plugins

    def test_team_not_in_allowed_list_rejects_additions(self, valid_v2_org_config):
        """Team trying to add plugins not in org's allowed list should be rejected."""
        from scc_cli.profiles import compute_effective_config

        # Org allows only specific teams to add MCP servers
        valid_v2_org_config["delegation"]["teams"]["allow_additional_mcp_servers"] = [
            "finance"
        ]  # urban-planning NOT in list

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=None,
        )

        # Team's MCP server should be denied
        mcp_names = [s.name for s in result.mcp_servers]
        assert "gis-internal" not in mcp_names

        # Should have denial tracked
        denied = [d for d in result.denied_additions if d.item == "gis-internal"]
        assert len(denied) == 1


class TestComputeEffectiveConfigSecurityBlocks:
    """Tests for security boundaries - blocked items are NEVER allowed."""

    def test_blocked_plugin_rejected_from_org_defaults(self, valid_v2_org_config):
        """Plugin in org defaults that matches blocked pattern should be rejected."""
        from scc_cli.profiles import compute_effective_config

        # Add a blocked plugin pattern
        valid_v2_org_config["security"]["blocked_plugins"] = ["internal-*"]
        # Org defaults include "internal-docs" which matches
        valid_v2_org_config["defaults"]["allowed_plugins"] = [
            "github-copilot",
            "internal-docs",
        ]

        result = compute_effective_config(
            org_config=valid_v2_org_config, team_name=None, project_config=None
        )

        # internal-docs should be blocked
        assert "internal-docs" not in result.plugins
        assert "github-copilot" in result.plugins

        # Should have blocked item tracked
        blocked = [b for b in result.blocked_items if b.item == "internal-docs"]
        assert len(blocked) == 1
        assert blocked[0].blocked_by == "internal-*"

    def test_blocked_plugin_rejected_from_team(self, valid_v2_org_config):
        """Plugin from team profile matching blocked pattern should be rejected."""
        from scc_cli.profiles import compute_effective_config

        # Block all gis-* plugins
        valid_v2_org_config["security"]["blocked_plugins"] = ["gis-*"]

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=None,
        )

        # gis-tools from team should be blocked
        assert "gis-tools" not in result.plugins

    def test_blocked_plugin_rejected_from_project(self, valid_v2_org_config, project_config):
        """Plugin from project matching blocked pattern should be rejected."""
        from scc_cli.profiles import compute_effective_config

        # Enable delegation
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        # Block project's plugin
        valid_v2_org_config["security"]["blocked_plugins"] = ["project-*"]

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        # Project plugin should be blocked
        assert "project-specific-tool" not in result.plugins

    def test_blocked_mcp_server_rejected(self, valid_v2_org_config):
        """MCP server matching blocked pattern should be rejected."""
        from scc_cli.profiles import compute_effective_config

        # Block all sundsvall.se MCP servers
        valid_v2_org_config["security"]["blocked_mcp_servers"] = ["*.sundsvall.se"]

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=None,
        )

        # gis-internal (gis.sundsvall.se) should be blocked
        mcp_names = [s.name for s in result.mcp_servers]
        assert "gis-internal" not in mcp_names

    def test_security_blocks_cannot_be_overridden(self, valid_v2_org_config):
        """Security blocks apply regardless of delegation settings."""
        from scc_cli.profiles import compute_effective_config

        # Max delegation enabled
        valid_v2_org_config["delegation"]["teams"]["allow_additional_plugins"] = ["*"]
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True

        # But blocked is blocked
        valid_v2_org_config["security"]["blocked_plugins"] = ["gis-*"]

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=None,
        )

        # Still blocked
        assert "gis-tools" not in result.plugins


class TestComputeEffectiveConfigGlobPatterns:
    """Tests for glob pattern matching with fnmatch."""

    def test_wildcard_star_matches_multiple_chars(self, valid_v2_org_config):
        """Pattern * should match any characters."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["security"]["blocked_plugins"] = ["test-*-plugin"]
        valid_v2_org_config["defaults"]["allowed_plugins"] = [
            "test-abc-plugin",
            "test-xyz-plugin",
            "other-plugin",
        ]

        result = compute_effective_config(
            org_config=valid_v2_org_config, team_name=None, project_config=None
        )

        assert "test-abc-plugin" not in result.plugins
        assert "test-xyz-plugin" not in result.plugins
        assert "other-plugin" in result.plugins

    def test_wildcard_question_matches_single_char(self, valid_v2_org_config):
        """Pattern ? should match exactly one character."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["security"]["blocked_plugins"] = ["test-?-plugin"]
        valid_v2_org_config["defaults"]["allowed_plugins"] = [
            "test-a-plugin",
            "test-ab-plugin",
            "other-plugin",
        ]

        result = compute_effective_config(
            org_config=valid_v2_org_config, team_name=None, project_config=None
        )

        assert "test-a-plugin" not in result.plugins  # Matches ?
        assert "test-ab-plugin" in result.plugins  # Two chars, doesn't match ?
        assert "other-plugin" in result.plugins

    def test_domain_wildcard_pattern(self, valid_v2_org_config):
        """Domain patterns like *.domain.com should work."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["security"]["blocked_mcp_servers"] = ["*.evil.com"]
        valid_v2_org_config["profiles"]["urban-planning"]["additional_mcp_servers"] = [
            {"name": "bad-server", "type": "sse", "url": "https://api.evil.com/mcp"},
            {"name": "good-server", "type": "sse", "url": "https://api.good.com/mcp"},
        ]

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=None,
        )

        mcp_names = [s.name for s in result.mcp_servers]
        assert "bad-server" not in mcp_names
        assert "good-server" in mcp_names

    def test_exact_match_pattern(self, valid_v2_org_config):
        """Exact patterns (no wildcards) should match exactly."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["security"]["blocked_plugins"] = ["exact-plugin"]
        valid_v2_org_config["defaults"]["allowed_plugins"] = [
            "exact-plugin",
            "exact-plugin-extended",
            "other-exact-plugin",
        ]

        result = compute_effective_config(
            org_config=valid_v2_org_config, team_name=None, project_config=None
        )

        assert "exact-plugin" not in result.plugins
        assert "exact-plugin-extended" in result.plugins  # Not blocked
        assert "other-exact-plugin" in result.plugins  # Not blocked


class TestComputeEffectiveConfigDecisionTracking:
    """Tests for decision tracking (for scc config explain)."""

    def test_decisions_track_plugin_sources(self, valid_v2_org_config, project_config):
        """Decisions should track where each plugin came from."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        # Check that decisions track sources
        # Should have decisions for plugins from different sources
        sources = [d.source for d in result.decisions]
        assert any("org" in s.lower() or "default" in s.lower() for s in sources)
        assert any("team" in s.lower() or "urban-planning" in s.lower() for s in sources)
        assert any("project" in s.lower() for s in sources)

    def test_blocked_items_tracked_with_pattern(self, valid_v2_org_config):
        """Blocked items should show which pattern blocked them."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["security"]["blocked_plugins"] = ["gis-*"]

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=None,
        )

        # Find the blocked item
        blocked = [b for b in result.blocked_items if b.item == "gis-tools"]
        assert len(blocked) == 1
        assert blocked[0].blocked_by == "gis-*"
        assert "security" in blocked[0].source.lower()

    def test_denied_additions_tracked_with_reason(self, valid_v2_org_config, project_config):
        """Denied additions should explain why they were denied."""
        from scc_cli.profiles import compute_effective_config

        # Disable delegation at org level
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = False

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        # Check denied additions
        denied = [d for d in result.denied_additions if d.item == "project-specific-tool"]
        assert len(denied) == 1
        assert denied[0].requested_by == "project"
        # Reason should mention org or delegation
        assert "org" in denied[0].reason.lower() or "delegation" in denied[0].reason.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Project Config Reader (.scc.yaml)
# ═══════════════════════════════════════════════════════════════════════════════


class TestReadProjectConfig:
    """Tests for reading .scc.yaml project configuration files.

    TDD: These tests define the expected behavior of read_project_config().
    The function should:
    - Read .scc.yaml from a given directory
    - Return parsed YAML as dict
    - Return None when file doesn't exist
    - Raise ValueError for invalid YAML
    """

    def test_read_project_config_valid_yaml(self, tmp_path):
        """Should read and parse valid .scc.yaml file."""
        from scc_cli.config import read_project_config

        # Create a valid .scc.yaml file
        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins:
  - "project-specific-tool"
  - "another-tool"

additional_mcp_servers:
  - name: "project-api"
    type: "sse"
    url: "https://api.internal/mcp"

session:
  timeout_hours: 4
""")

        result = read_project_config(tmp_path)

        assert result is not None
        assert "additional_plugins" in result
        assert "project-specific-tool" in result["additional_plugins"]
        assert "another-tool" in result["additional_plugins"]
        assert len(result["additional_mcp_servers"]) == 1
        assert result["additional_mcp_servers"][0]["name"] == "project-api"
        assert result["session"]["timeout_hours"] == 4

    def test_read_project_config_file_missing_returns_none(self, tmp_path):
        """Should return None when .scc.yaml doesn't exist."""
        from scc_cli.config import read_project_config

        result = read_project_config(tmp_path)

        assert result is None

    def test_read_project_config_empty_file_returns_none(self, tmp_path):
        """Should return None for empty .scc.yaml file."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("")

        result = read_project_config(tmp_path)

        assert result is None

    def test_read_project_config_invalid_yaml_raises_error(self, tmp_path):
        """Should raise ValueError for malformed YAML."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins:
  - valid item
  invalid: indentation: here
  broken yaml [
""")

        with pytest.raises(ValueError) as exc_info:
            read_project_config(tmp_path)

        assert "invalid" in str(exc_info.value).lower() or "yaml" in str(exc_info.value).lower()

    def test_read_project_config_minimal_valid(self, tmp_path):
        """Should accept minimal valid project config."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins:
  - "single-plugin"
""")

        result = read_project_config(tmp_path)

        assert result is not None
        assert result["additional_plugins"] == ["single-plugin"]

    def test_read_project_config_accepts_string_path(self, tmp_path):
        """Should accept string path in addition to Path object."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins:
  - "test-plugin"
""")

        # Pass string path instead of Path object
        result = read_project_config(str(tmp_path))

        assert result is not None
        assert "test-plugin" in result["additional_plugins"]

    def test_read_project_config_session_only(self, tmp_path):
        """Should read config with only session settings."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
session:
  timeout_hours: 2
  auto_resume: false
""")

        result = read_project_config(tmp_path)

        assert result is not None
        assert result["session"]["timeout_hours"] == 2
        assert result["session"]["auto_resume"] is False

    def test_read_project_config_mcp_servers_only(self, tmp_path):
        """Should read config with only MCP servers."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_mcp_servers:
  - name: "local-api"
    type: "stdio"
    command: "npx"
    args:
      - "-y"
      - "@local/mcp-server"
""")

        result = read_project_config(tmp_path)

        assert result is not None
        assert len(result["additional_mcp_servers"]) == 1
        server = result["additional_mcp_servers"][0]
        assert server["name"] == "local-api"
        assert server["type"] == "stdio"
        assert server["command"] == "npx"
        assert "-y" in server["args"]


class TestReadProjectConfigValidation:
    """Tests for project config schema validation.

    TDD: These tests ensure project config adheres to expected schema.
    Invalid types or unexpected fields should be caught.
    """

    def test_read_project_config_plugins_must_be_list(self, tmp_path):
        """Should raise error if additional_plugins is not a list."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins: "not-a-list"
""")

        with pytest.raises(ValueError) as exc_info:
            read_project_config(tmp_path)

        assert "additional_plugins" in str(exc_info.value) or "list" in str(exc_info.value).lower()

    def test_read_project_config_mcp_servers_must_be_list(self, tmp_path):
        """Should raise error if additional_mcp_servers is not a list."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_mcp_servers: "not-a-list"
""")

        with pytest.raises(ValueError) as exc_info:
            read_project_config(tmp_path)

        assert "mcp_servers" in str(exc_info.value).lower() or "list" in str(exc_info.value).lower()

    def test_read_project_config_session_must_be_dict(self, tmp_path):
        """Should raise error if session is not a dict."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
session: "not-a-dict"
""")

        with pytest.raises(ValueError) as exc_info:
            read_project_config(tmp_path)

        assert "session" in str(exc_info.value) or "dict" in str(exc_info.value).lower()

    def test_read_project_config_timeout_hours_must_be_integer(self, tmp_path):
        """Should raise error if timeout_hours is not an integer."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
session:
  timeout_hours: "not-a-number"
""")

        with pytest.raises(ValueError) as exc_info:
            read_project_config(tmp_path)

        assert "timeout_hours" in str(exc_info.value) or "integer" in str(exc_info.value).lower()

    def test_read_project_config_allows_unknown_fields(self, tmp_path):
        """Should allow unknown fields for forward compatibility."""
        from scc_cli.config import read_project_config

        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins:
  - "test-plugin"
future_field: "some value"
another_unknown:
  nested: true
""")

        # Should NOT raise - unknown fields are ignored for forward compatibility
        result = read_project_config(tmp_path)

        assert result is not None
        assert "test-plugin" in result["additional_plugins"]


class TestProjectConfigIntegration:
    """Tests for project config integration with compute_effective_config.

    TDD: These tests verify the full integration path.
    """

    def test_compute_effective_config_loads_project_from_path(self, valid_v2_org_config, tmp_path):
        """compute_effective_config should load project config from workspace path."""
        from scc_cli.profiles import compute_effective_config

        # Enable delegation
        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        # Create project config file
        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins:
  - "project-specific-tool"
session:
  timeout_hours: 3
""")

        # Pass workspace_path instead of project_config dict
        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            workspace_path=tmp_path,
        )

        # Should have project plugin
        assert "project-specific-tool" in result.plugins
        assert result.session_config.timeout_hours == 3

    def test_compute_effective_config_no_project_file_is_ok(self, valid_v2_org_config, tmp_path):
        """compute_effective_config should work when no .scc.yaml exists."""
        from scc_cli.profiles import compute_effective_config

        # No .scc.yaml file created

        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            workspace_path=tmp_path,
        )

        # Should have team plugin but no project plugin
        assert "gis-tools" in result.plugins

    def test_compute_effective_config_project_config_dict_still_works(
        self, valid_v2_org_config, project_config
    ):
        """Passing project_config dict directly should still work (backward compat)."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        # Pass dict directly (original interface)
        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,
        )

        assert "project-specific-tool" in result.plugins

    def test_compute_effective_config_workspace_path_overrides_project_config(
        self, valid_v2_org_config, project_config, tmp_path
    ):
        """When both workspace_path and project_config provided, workspace_path wins."""
        from scc_cli.profiles import compute_effective_config

        valid_v2_org_config["delegation"]["projects"]["inherit_team_delegation"] = True
        valid_v2_org_config["profiles"]["urban-planning"]["delegation"][
            "allow_project_overrides"
        ] = True

        # Create different project config in file
        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("""
additional_plugins:
  - "file-based-plugin"
""")

        # Pass both - workspace_path should take precedence
        result = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
            project_config=project_config,  # Has "project-specific-tool"
            workspace_path=tmp_path,  # Has "file-based-plugin"
        )

        # File-based config should win
        assert "file-based-plugin" in result.plugins
        assert "project-specific-tool" not in result.plugins


# ═══════════════════════════════════════════════════════════════════════════════
# Task 1.4: Launch Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestClaudeAdapterWithEffectiveConfig:
    """Tests for claude_adapter.py accepting EffectiveConfig."""

    def test_build_settings_from_effective_config_plugins(self, valid_v2_org_config):
        """build_settings_from_effective_config should include effective plugins."""
        from scc_cli.claude_adapter import build_settings_from_effective_config
        from scc_cli.profiles import compute_effective_config

        # Compute effective config
        effective = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
        )

        # Build Claude settings
        settings = build_settings_from_effective_config(
            effective_config=effective,
            org_id="sundsvall",
        )

        # Should have plugins in enabledPlugins
        assert "enabledPlugins" in settings
        # All effective plugins should be enabled
        enabled = settings["enabledPlugins"]
        # github-copilot from defaults + gis-tools from team
        assert any("github-copilot" in p for p in enabled)
        assert any("gis-tools" in p for p in enabled)

    def test_build_settings_from_effective_config_mcp_servers(self, valid_v2_org_config):
        """build_settings_from_effective_config should include MCP servers."""
        from scc_cli.claude_adapter import build_settings_from_effective_config
        from scc_cli.profiles import compute_effective_config

        effective = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
        )

        settings = build_settings_from_effective_config(
            effective_config=effective,
            org_id="sundsvall",
        )

        # Should have MCP servers configured
        assert "mcpServers" in settings
        mcp_servers = settings["mcpServers"]
        # gis-internal MCP server from team profile
        assert "gis-internal" in mcp_servers

    def test_build_settings_blocked_plugins_not_included(self, valid_v2_org_config):
        """Blocked plugins should not appear in Claude settings."""
        from scc_cli.claude_adapter import build_settings_from_effective_config
        from scc_cli.profiles import compute_effective_config

        # Block gis-tools
        valid_v2_org_config["security"]["blocked_plugins"].append("gis-tools")

        effective = compute_effective_config(
            org_config=valid_v2_org_config,
            team_name="urban-planning",
        )

        settings = build_settings_from_effective_config(
            effective_config=effective,
            org_id="sundsvall",
        )

        # gis-tools should NOT be in enabled plugins
        enabled = settings.get("enabledPlugins", [])
        assert not any("gis-tools" in p for p in enabled)
