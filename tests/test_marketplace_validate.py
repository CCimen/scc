"""
Unit tests for marketplace org config validation.

Tests cover:
- load_marketplace_schema(): Loading bundled marketplace schema
- validate_marketplace_org_config(): Schema validation
- check_marketplace_names(): Implicit marketplace shadowing check
- validate_marketplace_org_config_full(): Combined validation
"""


class TestLoadMarketplaceSchema:
    """Tests for load_marketplace_schema function."""

    def test_loads_marketplace_schema(self) -> None:
        """Should load marketplace org config schema from package resources."""
        from scc_cli.validate import load_marketplace_schema

        schema = load_marketplace_schema()
        assert "$schema" in schema or "$id" in schema
        assert "properties" in schema
        assert "marketplaces" in schema["properties"]

    def test_schema_has_required_fields(self) -> None:
        """Schema should define name and schema_version as required."""
        from scc_cli.validate import load_marketplace_schema

        schema = load_marketplace_schema()
        required = schema.get("required", [])
        assert "name" in required
        assert "schema_version" in required


class TestValidateMarketplaceOrgConfig:
    """Tests for validate_marketplace_org_config function."""

    def test_valid_minimal_config(self) -> None:
        """Minimal valid config should return empty error list."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "name": "Test Organization",
            "schema_version": 1,
        }
        errors = validate_marketplace_org_config(config)
        assert errors == []

    def test_valid_config_with_github_marketplace(self) -> None:
        """Config with GitHub marketplace should be valid."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "name": "Sundsvall Municipality",
            "schema_version": 1,
            "marketplaces": {
                "internal": {
                    "source": "github",
                    "owner": "sundsvall",
                    "repo": "claude-plugins",
                }
            },
        }
        errors = validate_marketplace_org_config(config)
        assert errors == []

    def test_valid_config_with_directory_marketplace(self) -> None:
        """Config with directory marketplace should be valid."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "name": "Test Org",
            "schema_version": 1,
            "marketplaces": {
                "local": {
                    "source": "directory",
                    "path": "/opt/plugins",
                }
            },
        }
        errors = validate_marketplace_org_config(config)
        assert errors == []

    def test_valid_config_with_profiles(self) -> None:
        """Config with profiles should be valid."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "name": "Test Org",
            "schema_version": 1,
            "profiles": {
                "backend": {
                    "name": "Backend Team",
                    "additional_plugins": ["api-tools@internal"],
                }
            },
        }
        errors = validate_marketplace_org_config(config)
        assert errors == []

    def test_missing_name_is_invalid(self) -> None:
        """Config without name should return error."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "schema_version": 1,
        }
        errors = validate_marketplace_org_config(config)
        assert len(errors) > 0
        assert any("name" in e for e in errors)

    def test_missing_schema_version_is_invalid(self) -> None:
        """Config without schema_version should return error."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "name": "Test Org",
        }
        errors = validate_marketplace_org_config(config)
        assert len(errors) > 0
        assert any("schema_version" in e for e in errors)

    def test_invalid_schema_version_type(self) -> None:
        """Schema version must be integer."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "name": "Test Org",
            "schema_version": "1",  # Should be int, not string
        }
        errors = validate_marketplace_org_config(config)
        assert len(errors) > 0
        assert any("schema_version" in e for e in errors)

    def test_invalid_marketplace_source_type(self) -> None:
        """Invalid source type should return error."""
        from scc_cli.validate import validate_marketplace_org_config

        config = {
            "name": "Test Org",
            "schema_version": 1,
            "marketplaces": {
                "bad": {
                    "source": "unknown",  # Invalid source type
                    "url": "https://example.com",
                }
            },
        }
        errors = validate_marketplace_org_config(config)
        assert len(errors) > 0


class TestCheckMarketplaceNames:
    """Tests for check_marketplace_names function."""

    def test_no_shadowing_with_empty_marketplaces(self) -> None:
        """Empty marketplaces should return no errors."""
        from scc_cli.validate import check_marketplace_names

        errors = check_marketplace_names({})
        assert errors == []

    def test_no_shadowing_with_custom_names(self) -> None:
        """Custom marketplace names should not shadow implict marketplaces."""
        from scc_cli.validate import check_marketplace_names

        org_marketplaces = {
            "internal": {"source": "github", "owner": "org", "repo": "plugins"},
            "external": {"source": "directory", "path": "/opt/plugins"},
        }
        errors = check_marketplace_names(org_marketplaces)
        assert errors == []

    def test_shadowing_claude_plugins_official(self) -> None:
        """Shadowing 'claude-plugins-official' should return error."""
        from scc_cli.validate import check_marketplace_names

        org_marketplaces = {
            "claude-plugins-official": {
                "source": "github",
                "owner": "fake",
                "repo": "fake",
            }
        }
        errors = check_marketplace_names(org_marketplaces)
        assert len(errors) == 1
        assert "claude-plugins-official" in errors[0]
        assert "shadows" in errors[0].lower()

    def test_shadowing_with_multiple_marketplaces(self) -> None:
        """Multiple valid marketplaces with one shadowing should return one error."""
        from scc_cli.validate import check_marketplace_names

        org_marketplaces = {
            "internal": {"source": "directory", "path": "/a"},
            "claude-plugins-official": {"source": "directory", "path": "/b"},
            "external": {"source": "directory", "path": "/c"},
        }
        errors = check_marketplace_names(org_marketplaces)
        assert len(errors) == 1
        assert "claude-plugins-official" in errors[0]

    def test_custom_implicit_marketplaces(self) -> None:
        """Should respect custom implicit marketplaces set."""
        from scc_cli.validate import check_marketplace_names

        custom_implicit = frozenset({"custom-implicit"})
        org_marketplaces = {"custom-implicit": {"source": "directory", "path": "/a"}}
        errors = check_marketplace_names(org_marketplaces, custom_implicit)
        assert len(errors) == 1
        assert "custom-implicit" in errors[0]


class TestValidateMarketplaceOrgConfigFull:
    """Tests for validate_marketplace_org_config_full function."""

    def test_valid_config_passes_all_checks(self) -> None:
        """Valid config should pass both schema and semantic checks."""
        from scc_cli.validate import validate_marketplace_org_config_full

        config = {
            "name": "Test Org",
            "schema_version": 1,
            "marketplaces": {
                "internal": {
                    "source": "github",
                    "owner": "sundsvall",
                    "repo": "plugins",
                }
            },
        }
        errors = validate_marketplace_org_config_full(config)
        assert errors == []

    def test_invalid_schema_returns_errors(self) -> None:
        """Invalid schema should return schema errors."""
        from scc_cli.validate import validate_marketplace_org_config_full

        config = {
            "schema_version": 1,
            # Missing name
        }
        errors = validate_marketplace_org_config_full(config)
        assert len(errors) > 0
        assert any("name" in e for e in errors)

    def test_shadowing_returns_errors(self) -> None:
        """Shadowing implicit marketplace should return semantic error."""
        from scc_cli.validate import validate_marketplace_org_config_full

        config = {
            "name": "Test Org",
            "schema_version": 1,
            "marketplaces": {
                "claude-plugins-official": {
                    "source": "directory",
                    "path": "/fake",
                }
            },
        }
        errors = validate_marketplace_org_config_full(config)
        assert len(errors) == 1
        assert "claude-plugins-official" in errors[0]

    def test_combined_errors_returned(self) -> None:
        """Both schema and semantic errors should be combined."""
        from scc_cli.validate import validate_marketplace_org_config_full

        config = {
            # Missing name (schema error)
            "schema_version": 1,
            "marketplaces": {
                "claude-plugins-official": {  # Shadowing (semantic error)
                    "source": "directory",
                    "path": "/fake",
                }
            },
        }
        errors = validate_marketplace_org_config_full(config)
        assert len(errors) >= 2
        # Should have both schema error and semantic error
        has_schema_error = any("name" in e for e in errors)
        has_semantic_error = any("shadows" in e.lower() for e in errors)
        assert has_schema_error
        assert has_semantic_error
