"""Tests for org_templates module.

TDD tests for organization config template loading and rendering.
"""

from __future__ import annotations

import json

import pytest

from scc_cli.org_templates import (
    TemplateInfo,
    TemplateNotFoundError,
    TemplateVars,
    get_template_info,
    list_templates,
    render_template,
    render_template_string,
    validate_template_name,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Template Registry Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestListTemplates:
    """Tests for list_templates function."""

    def test_returns_non_empty_list(self) -> None:
        """Should return a non-empty list of templates."""
        templates = list_templates()
        assert len(templates) >= 1

    def test_all_items_are_template_info(self) -> None:
        """Should return TemplateInfo instances."""
        templates = list_templates()
        for template in templates:
            assert isinstance(template, TemplateInfo)

    def test_minimal_template_exists(self) -> None:
        """Should include the minimal template."""
        templates = list_templates()
        names = [t.name for t in templates]
        assert "minimal" in names

    def test_teams_template_exists(self) -> None:
        """Should include the teams template."""
        templates = list_templates()
        names = [t.name for t in templates]
        assert "teams" in names

    def test_strict_template_exists(self) -> None:
        """Should include the strict template."""
        templates = list_templates()
        names = [t.name for t in templates]
        assert "strict" in names

    def test_reference_template_exists(self) -> None:
        """Should include the reference template."""
        templates = list_templates()
        names = [t.name for t in templates]
        assert "reference" in names


class TestGetTemplateInfo:
    """Tests for get_template_info function."""

    def test_returns_template_info_for_valid_name(self) -> None:
        """Should return TemplateInfo for valid name."""
        info = get_template_info("minimal")
        assert isinstance(info, TemplateInfo)
        assert info.name == "minimal"

    def test_raises_for_unknown_template(self) -> None:
        """Should raise TemplateNotFoundError for unknown name."""
        with pytest.raises(TemplateNotFoundError) as exc_info:
            get_template_info("nonexistent-template")

        assert "nonexistent-template" in str(exc_info.value)
        assert "minimal" in str(exc_info.value)  # Should list available

    def test_template_info_has_description(self) -> None:
        """Template info should have description."""
        info = get_template_info("minimal")
        assert info.description
        assert len(info.description) > 0

    def test_template_info_has_level(self) -> None:
        """Template info should have level."""
        info = get_template_info("minimal")
        assert info.level
        assert info.level in ("beginner", "intermediate", "advanced", "reference")


class TestValidateTemplateName:
    """Tests for validate_template_name function."""

    def test_valid_name_does_not_raise(self) -> None:
        """Should not raise for valid template names."""
        validate_template_name("minimal")  # Should not raise
        validate_template_name("teams")
        validate_template_name("strict")
        validate_template_name("reference")

    def test_invalid_name_raises_with_available_list(self) -> None:
        """Should raise with list of available templates."""
        with pytest.raises(TemplateNotFoundError) as exc_info:
            validate_template_name("unknown-template")

        error = exc_info.value
        assert error.name == "unknown-template"
        assert "minimal" in error.available


# ═══════════════════════════════════════════════════════════════════════════════
# Template Rendering Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRenderTemplate:
    """Tests for render_template function."""

    def test_renders_minimal_template(self) -> None:
        """Should render minimal template as dict."""
        result = render_template("minimal")
        assert isinstance(result, dict)

    def test_applies_org_name_substitution(self) -> None:
        """Should substitute ORG_NAME placeholder."""
        vars = TemplateVars(org_name="acme-corp")
        result = render_template("minimal", vars)

        # Check org name appears somewhere in the result
        json_str = json.dumps(result)
        assert "acme-corp" in json_str

    def test_applies_org_domain_substitution(self) -> None:
        """Should substitute ORG_DOMAIN placeholder."""
        vars = TemplateVars(org_domain="acme.com")
        result = render_template("minimal", vars)

        json_str = json.dumps(result)
        assert "acme.com" in json_str

    def test_applies_schema_version_substitution(self) -> None:
        """Should substitute SCHEMA_VERSION placeholder."""
        vars = TemplateVars(schema_version="1.5.0")
        result = render_template("minimal", vars)

        assert result.get("schema_version") == "1.5.0"

    def test_applies_min_cli_version_substitution(self) -> None:
        """Should substitute MIN_CLI_VERSION placeholder."""
        vars = TemplateVars(min_cli_version="2.0.0")
        result = render_template("minimal", vars)

        assert result.get("min_cli_version") == "2.0.0"

    def test_default_vars_produce_valid_output(self) -> None:
        """Should use default vars when none provided."""
        result = render_template("minimal")

        # Should have organization section
        assert "organization" in result

    def test_raises_for_unknown_template(self) -> None:
        """Should raise TemplateNotFoundError for unknown template."""
        with pytest.raises(TemplateNotFoundError):
            render_template("nonexistent")


class TestRenderTemplateString:
    """Tests for render_template_string function."""

    def test_returns_valid_json_string(self) -> None:
        """Should return valid JSON string."""
        output = render_template_string("minimal")
        parsed = json.loads(output)  # Should not raise
        assert isinstance(parsed, dict)

    def test_applies_custom_indent(self) -> None:
        """Should apply custom indentation."""
        output = render_template_string("minimal", indent=4)
        # With indent=4, should have 4-space indentation
        assert "    " in output

    def test_applies_substitutions(self) -> None:
        """Should apply variable substitutions."""
        vars = TemplateVars(org_name="test-org")
        output = render_template_string("minimal", vars)

        assert "test-org" in output


# ═══════════════════════════════════════════════════════════════════════════════
# Template Content Validation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTemplateContentValidation:
    """Tests that rendered templates are valid org configs."""

    def test_minimal_has_required_fields(self) -> None:
        """Minimal template should have required organization field."""
        result = render_template("minimal")
        assert "organization" in result
        assert "name" in result["organization"]
        assert "id" in result["organization"]

    def test_teams_has_profiles(self) -> None:
        """Teams template should have profiles section."""
        result = render_template("teams")
        assert "profiles" in result
        assert len(result["profiles"]) >= 1

    def test_strict_has_security_settings(self) -> None:
        """Strict template should have restrictive defaults."""
        result = render_template("strict")
        # Strict configs typically have explicit settings
        assert "organization" in result

    def test_reference_has_all_sections(self) -> None:
        """Reference template should demonstrate all available fields."""
        result = render_template("reference")
        # Reference should be comprehensive
        assert "organization" in result
        assert "profiles" in result


class TestTemplateVars:
    """Tests for TemplateVars dataclass."""

    def test_default_values(self) -> None:
        """Should have sensible default values."""
        vars = TemplateVars()
        assert vars.org_name == "my-org"
        assert vars.org_domain == "example.com"
        assert vars.schema_version == "1.0.0"
        assert vars.min_cli_version == "1.2.0"

    def test_custom_values(self) -> None:
        """Should accept custom values."""
        vars = TemplateVars(
            org_name="acme",
            org_domain="acme.com",
            schema_version="2.0.0",
            min_cli_version="3.0.0",
        )
        assert vars.org_name == "acme"
        assert vars.org_domain == "acme.com"
        assert vars.schema_version == "2.0.0"
        assert vars.min_cli_version == "3.0.0"
