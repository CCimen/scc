"""Tests for teams module."""

from __future__ import annotations

import pytest

from scc_cli import teams
from scc_cli.teams import TeamInfo


@pytest.fixture
def sample_org_config() -> dict[str, object]:
    """Create a sample org config with profiles and marketplaces."""
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Test Organization",
            "id": "test-org",
        },
        "marketplaces": {
            "internal": {
                "source": "git",
                "url": "https://gitlab.company.com/devops/claude-plugins.git",
                "branch": "main",
                "path": "/",
            },
            "public": {
                "source": "github",
                "owner": "company",
                "repo": "public-plugins",
            },
        },
        "delegation": {
            "teams": {
                "allow_additional_plugins": ["platform", "api"],
            },
        },
        "profiles": {
            "platform": {
                "description": "Platform team (Python, FastAPI)",
                "additional_plugins": ["platform@internal"],
            },
            "api": {
                "description": "API team (Java, Spring Boot)",
                "additional_plugins": ["api@public", "core@internal"],
            },
            "base": {
                "description": "Base profile - no plugins",
                "additional_plugins": [],
            },
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list_teams
# ═══════════════════════════════════════════════════════════════════════════════


class TestListTeams:
    """Tests for list_teams function."""

    def test_list_teams_returns_empty_without_org_config(self):
        """list_teams should return empty list when org_config is missing."""
        assert teams.list_teams(None) == []

    def test_list_teams_returns_all_teams(self, sample_org_config):
        """list_teams should return all teams from org_config."""
        result = teams.list_teams(sample_org_config)
        assert len(result) == 3
        team_names = [team["name"] for team in result]
        assert "platform" in team_names
        assert "api" in team_names
        assert "base" in team_names

    def test_list_teams_includes_description_and_plugins(self, sample_org_config):
        """list_teams should include team description and plugins list."""
        result = teams.list_teams(sample_org_config)
        platform = next(team for team in result if team["name"] == "platform")
        assert platform["description"] == "Platform team (Python, FastAPI)"
        assert platform["plugins"] == ["platform@internal"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_team_details
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetTeamDetails:
    """Tests for get_team_details function."""

    def test_get_team_details_returns_none_without_org_config(self):
        """get_team_details should return None when org_config is missing."""
        assert teams.get_team_details("platform", None) is None

    def test_get_team_details_existing_team(self, sample_org_config):
        """get_team_details should return full details for existing team."""
        result = teams.get_team_details("platform", sample_org_config)
        assert result is not None
        assert result["name"] == "platform"
        assert result["description"] == "Platform team (Python, FastAPI)"
        assert result["plugins"] == ["platform@internal"]
        assert result["marketplace"] == "internal"
        assert result["marketplace_type"] == "git"
        assert result["marketplace_repo"] == "https://gitlab.company.com/devops/claude-plugins.git"

    def test_get_team_details_multiple_marketplaces(self, sample_org_config):
        """get_team_details should summarize multiple marketplace names."""
        result = teams.get_team_details("api", sample_org_config)
        assert result is not None
        assert result["marketplace"] == "internal, public"
        assert result["marketplace_type"] is None
        assert result["marketplace_repo"] is None

    def test_get_team_details_base_team(self, sample_org_config):
        """get_team_details should handle teams with no plugins."""
        result = teams.get_team_details("base", sample_org_config)
        assert result is not None
        assert result["plugins"] == []
        assert result["marketplace"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for validate_team_profile
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateTeamProfile:
    """Tests for validate_team_profile function."""

    def test_validate_requires_org_config(self):
        """validate_team_profile should return error when org_config is missing."""
        result = teams.validate_team_profile("platform", None)
        assert result["valid"] is False
        assert any("organization" in error for error in result["errors"])

    def test_validate_nonexistent_team(self, sample_org_config):
        """validate_team_profile should return valid=False for missing team."""
        result = teams.validate_team_profile("missing", sample_org_config)
        assert result["valid"] is False
        assert any("not found" in error for error in result["errors"])

    def test_validate_marketplace_not_found_warning(self):
        """validate_team_profile should warn when marketplace not found in org_config."""
        org_config = {
            "marketplaces": {},
            "profiles": {
                "test-team": {"additional_plugins": ["test-plugin@missing-marketplace"]},
            },
        }
        result = teams.validate_team_profile("test-team", org_config)
        assert result["valid"] is True
        assert any("not found" in warning for warning in result["warnings"])

    def test_validate_no_plugins_warns(self):
        """validate_team_profile should warn for non-base teams with no plugins."""
        org_config = {
            "profiles": {
                "empty-team": {"additional_plugins": []},
            },
        }
        result = teams.validate_team_profile("empty-team", org_config)
        assert result["valid"] is True
        assert any("no plugins configured" in warning for warning in result["warnings"])

    def test_validate_base_no_warning(self, sample_org_config):
        """validate_team_profile should not warn for base profile without plugins."""
        result = teams.validate_team_profile("base", sample_org_config)
        assert result["valid"] is True
        assert not any("no plugins" in warning.lower() for warning in result["warnings"])


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for TeamInfo dataclass
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamInfoDataclass:
    """Tests for TeamInfo dataclass attributes and defaults."""

    def test_teaminfo_required_field(self) -> None:
        """TeamInfo requires name field."""
        team = TeamInfo(name="platform")
        assert team.name == "platform"

    def test_teaminfo_optional_fields_have_defaults(self) -> None:
        """TeamInfo optional fields have sensible defaults."""
        team = TeamInfo(name="platform")
        assert team.description == ""
        assert team.plugins == []
        assert team.marketplace is None
        assert team.marketplace_type is None
        assert team.marketplace_repo is None
        assert team.credential_status is None

    def test_teaminfo_all_fields(self) -> None:
        """TeamInfo accepts all fields."""
        team = TeamInfo(
            name="platform",
            description="Platform team",
            plugins=["platform-plugin"],
            marketplace="internal",
            marketplace_type="gitlab",
            marketplace_repo="org/plugins",
            credential_status="valid",
        )
        assert team.name == "platform"
        assert team.description == "Platform team"
        assert team.plugins == ["platform-plugin"]
        assert team.marketplace == "internal"
        assert team.marketplace_type == "gitlab"
        assert team.marketplace_repo == "org/plugins"
        assert team.credential_status == "valid"


class TestTeamInfoFromDict:
    """Tests for TeamInfo.from_dict() class method."""

    def test_from_dict_minimal(self) -> None:
        """from_dict creates TeamInfo with minimal dict."""
        data = {"name": "platform"}
        team = TeamInfo.from_dict(data)
        assert team.name == "platform"
        assert team.description == ""
        assert team.plugins == []

    def test_from_dict_full(self) -> None:
        """from_dict creates TeamInfo with all fields."""
        data = {
            "name": "platform",
            "description": "Platform team",
            "plugins": ["platform-plugin"],
            "marketplace": "internal",
            "marketplace_type": "gitlab",
            "marketplace_repo": "org/plugins",
            "credential_status": "expired",
        }
        team = TeamInfo.from_dict(data)
        assert team.name == "platform"
        assert team.description == "Platform team"
        assert team.plugins == ["platform-plugin"]
        assert team.marketplace == "internal"
        assert team.marketplace_type == "gitlab"
        assert team.marketplace_repo == "org/plugins"
        assert team.credential_status == "expired"

    def test_from_dict_missing_name_uses_unknown(self) -> None:
        """from_dict uses 'unknown' for missing name."""
        data: dict = {}
        team = TeamInfo.from_dict(data)
        assert team.name == "unknown"

    def test_from_dict_ignores_extra_fields(self) -> None:
        """from_dict ignores unknown fields in dict."""
        data = {"name": "platform", "unknown_field": "value", "extra": 123}
        team = TeamInfo.from_dict(data)
        assert team.name == "platform"
