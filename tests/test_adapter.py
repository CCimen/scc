"""Tests for marketplace adapter (external -> internal format translation)."""

from __future__ import annotations

import copy

from scc_cli.marketplace.adapter import translate_org_config
from scc_cli.marketplace.schema import OrganizationConfig


class TestTranslateOrgConfigOrganizationFlattening:
    """Test organization object flattening."""

    def test_flattens_organization_name(self) -> None:
        """Organization.name should be moved to root level name."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Acme Corp", "id": "acme"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["name"] == "Acme Corp"
        assert "organization" not in internal

    def test_organization_id_is_discarded(self) -> None:
        """Organization.id is not used in Pydantic model."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Acme", "id": "acme-corp-123"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert "id" not in internal
        assert "organization" not in internal

    def test_missing_organization_uses_empty_dict(self) -> None:
        """If organization is missing, don't crash."""
        external = {
            "schema_version": "1.0.0",
            "profiles": {},
        }
        internal = translate_org_config(external)

        # name won't be added if organization is missing
        assert "name" not in internal
        assert "organization" not in internal

    def test_existing_name_takes_precedence(self) -> None:
        """If name already exists at root, don't overwrite it."""
        external = {
            "schema_version": "1.0.0",
            "name": "Already Set",
            "organization": {"name": "Should Not Overwrite"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["name"] == "Already Set"


class TestTranslateOrgConfigVersionConversion:
    """Test schema_version conversion."""

    def test_converts_semver_to_integer(self) -> None:
        """schema_version: '1.0.0' -> 1."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["schema_version"] == 1

    def test_converts_higher_version(self) -> None:
        """schema_version: '2.5.3' -> 2."""
        external = {
            "schema_version": "2.5.3",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["schema_version"] == 2

    def test_handles_v_prefix(self) -> None:
        """schema_version: 'v1.0.0' -> 1 (common user mistake)."""
        external = {
            "schema_version": "v1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["schema_version"] == 1

    def test_handles_uppercase_v_prefix(self) -> None:
        """schema_version: 'V1.0.0' -> 1."""
        external = {
            "schema_version": "V1.2.3",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["schema_version"] == 1

    def test_handles_simple_string_version(self) -> None:
        """schema_version: '1' -> 1."""
        external = {
            "schema_version": "1",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["schema_version"] == 1

    def test_preserves_integer_version(self) -> None:
        """Integer schema_version should pass through unchanged."""
        external = {
            "schema_version": 1,
            "name": "Test",
            "profiles": {},
        }
        internal = translate_org_config(external)

        assert internal["schema_version"] == 1

    def test_invalid_version_preserved_for_pydantic(self) -> None:
        """Invalid version strings are left for Pydantic to catch."""
        external = {
            "schema_version": "invalid",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
        }
        internal = translate_org_config(external)

        # Invalid string should remain (let Pydantic handle the error)
        assert internal["schema_version"] == "invalid"


class TestTranslateOrgConfigFieldPreservation:
    """Test that other fields are preserved unchanged."""

    def test_preserves_profiles(self) -> None:
        """Profiles dict should pass through unchanged."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {
                "backend": {"additional_plugins": ["tool@mp"]},
                "frontend": {"description": "Frontend team"},
            },
        }
        internal = translate_org_config(external)

        assert internal["profiles"] == external["profiles"]

    def test_preserves_defaults(self) -> None:
        """Defaults section should pass through unchanged."""
        defaults = {
            "enabled_plugins": ["default-tool@mp"],
            "allowed_plugins": ["*"],
        }
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
            "defaults": defaults,
        }
        internal = translate_org_config(external)

        assert internal["defaults"] == defaults

    def test_preserves_security(self) -> None:
        """Security section should pass through unchanged."""
        security = {
            "blocked_plugins": ["risky-*"],
            "allow_stdio_mcp": False,
        }
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
            "security": security,
        }
        internal = translate_org_config(external)

        assert internal["security"] == security

    def test_preserves_marketplaces(self) -> None:
        """Marketplaces section should pass through unchanged."""
        marketplaces = {
            "internal": {"source": "github", "owner": "acme", "repo": "plugins"},
        }
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
            "marketplaces": marketplaces,
        }
        internal = translate_org_config(external)

        assert internal["marketplaces"] == marketplaces


class TestTranslateOrgConfigCacheSafety:
    """Test that translation doesn't mutate the original dict."""

    def test_does_not_mutate_original(self) -> None:
        """Translation should use deepcopy to prevent cache poisoning."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {"team": {"additional_plugins": ["plugin@mp"]}},
        }
        original = copy.deepcopy(external)

        _ = translate_org_config(external)

        # Original should be unchanged
        assert external == original
        assert "organization" in external
        assert external["schema_version"] == "1.0.0"

    def test_nested_dict_mutation_safety(self) -> None:
        """Mutating internal dict shouldn't affect original."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {"team": {"additional_plugins": ["plugin@mp"]}},
        }
        internal = translate_org_config(external)

        # Mutate internal
        internal["profiles"]["team"]["additional_plugins"].append("new-plugin@mp")

        # Original should be unchanged
        assert external["profiles"]["team"]["additional_plugins"] == ["plugin@mp"]


class TestTranslateOrgConfigIdempotency:
    """Test that translation is idempotent (can run multiple times)."""

    def test_idempotent_on_internal_format(self) -> None:
        """Translating internal format should be a no-op."""
        internal = {
            "schema_version": 1,
            "name": "Already Internal",
            "profiles": {},
        }
        result = translate_org_config(internal)

        assert result["schema_version"] == 1
        assert result["name"] == "Already Internal"

    def test_double_translation_is_safe(self) -> None:
        """Translating twice should give same result."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {},
        }
        first = translate_org_config(external)
        second = translate_org_config(first)

        assert first == second


class TestTranslateOrgConfigFullRoundTrip:
    """Test full external -> translate -> Pydantic validation."""

    def test_full_external_to_pydantic(self) -> None:
        """Complete external config should successfully validate."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "profiles": {
                "backend": {
                    "name": "Backend Team",
                    "description": "Backend team",
                    "additional_plugins": ["api-tools@internal"],
                },
            },
            "defaults": {
                "enabled_plugins": ["core@internal"],
            },
            "security": {
                "blocked_plugins": ["risky-*"],
            },
            "marketplaces": {},
        }

        internal = translate_org_config(external)
        org_config = OrganizationConfig.model_validate(internal)

        assert org_config.name == "Test Org"
        assert org_config.schema_version == 1
        assert "backend" in org_config.profiles

    def test_minimal_external_to_pydantic(self) -> None:
        """Minimal external config should successfully validate."""
        external = {
            "schema_version": "1.0.0",
            "organization": {"name": "Minimal Org", "id": "min"},
        }

        internal = translate_org_config(external)
        org_config = OrganizationConfig.model_validate(internal)

        assert org_config.name == "Minimal Org"
        assert org_config.schema_version == 1
