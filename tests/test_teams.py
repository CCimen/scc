"""Tests for teams module."""

import pytest

from scc_cli import teams


# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_config():
    """Create a sample config with marketplace and profiles."""
    return {
        "marketplace": {
            "name": "sundsvall",
            "repo": "sundsvall/claude-plugins-marketplace",
        },
        "profiles": {
            "base": {
                "description": "Default profile - no team plugin",
                "plugin": None,
            },
            "ai-teamet": {
                "description": "AI platform development (Svelte, Python, DDD)",
                "plugin": "ai-teamet",
            },
            "team-evolution": {
                "description": ".NET/C# Metakatalogen development",
                "plugin": "team-evolution",
            },
            "draken": {
                "description": "Ärendehanteringssystem development",
                "plugin": "draken",
            },
        },
    }


@pytest.fixture
def minimal_config():
    """Create a minimal config with only required fields."""
    return {
        "profiles": {
            "test-team": {
                "description": "Test team",
                "plugin": "test-plugin",
            },
        },
    }


@pytest.fixture
def empty_config():
    """Create an empty config."""
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list_teams
# ═══════════════════════════════════════════════════════════════════════════════


class TestListTeams:
    """Tests for list_teams function."""

    def test_list_teams_returns_all_teams(self, sample_config):
        """list_teams should return all teams from config."""
        result = teams.list_teams(sample_config)
        assert len(result) == 4
        team_names = [t["name"] for t in result]
        assert "base" in team_names
        assert "ai-teamet" in team_names
        assert "team-evolution" in team_names
        assert "draken" in team_names

    def test_list_teams_includes_description(self, sample_config):
        """list_teams should include team descriptions."""
        result = teams.list_teams(sample_config)
        ai_team = next(t for t in result if t["name"] == "ai-teamet")
        assert ai_team["description"] == "AI platform development (Svelte, Python, DDD)"

    def test_list_teams_includes_plugin_name(self, sample_config):
        """list_teams should include plugin name."""
        result = teams.list_teams(sample_config)
        ai_team = next(t for t in result if t["name"] == "ai-teamet")
        assert ai_team["plugin"] == "ai-teamet"

    def test_list_teams_handles_no_plugin(self, sample_config):
        """list_teams should handle teams with no plugin."""
        result = teams.list_teams(sample_config)
        base_team = next(t for t in result if t["name"] == "base")
        assert base_team["plugin"] is None

    def test_list_teams_empty_config(self, empty_config):
        """list_teams should return empty list for empty config."""
        result = teams.list_teams(empty_config)
        assert result == []

    def test_list_teams_no_profiles_key(self):
        """list_teams should handle config without profiles key."""
        result = teams.list_teams({"other": "data"})
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_team_details
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetTeamDetails:
    """Tests for get_team_details function."""

    def test_get_team_details_existing_team(self, sample_config):
        """get_team_details should return full details for existing team."""
        result = teams.get_team_details("ai-teamet", sample_config)
        assert result is not None
        assert result["name"] == "ai-teamet"
        assert result["description"] == "AI platform development (Svelte, Python, DDD)"
        assert result["plugin"] == "ai-teamet"
        assert result["marketplace"] == "sundsvall"
        assert result["marketplace_repo"] == "sundsvall/claude-plugins-marketplace"

    def test_get_team_details_nonexistent_team(self, sample_config):
        """get_team_details should return None for nonexistent team."""
        result = teams.get_team_details("nonexistent", sample_config)
        assert result is None

    def test_get_team_details_base_team(self, sample_config):
        """get_team_details should handle base team with no plugin."""
        result = teams.get_team_details("base", sample_config)
        assert result is not None
        assert result["name"] == "base"
        assert result["plugin"] is None

    def test_get_team_details_empty_config(self, empty_config):
        """get_team_details should return None for empty config."""
        result = teams.get_team_details("any-team", empty_config)
        assert result is None

    def test_get_team_details_missing_marketplace(self, minimal_config):
        """get_team_details should handle missing marketplace config."""
        result = teams.get_team_details("test-team", minimal_config)
        assert result is not None
        assert result["marketplace"] is None
        assert result["marketplace_repo"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_team_sandbox_settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetTeamSandboxSettings:
    """Tests for get_team_sandbox_settings function."""

    def test_sandbox_settings_structure(self, sample_config):
        """get_team_sandbox_settings should return correct structure."""
        result = teams.get_team_sandbox_settings("ai-teamet", sample_config)
        assert "extraKnownMarketplaces" in result
        assert "enabledPlugins" in result

    def test_sandbox_settings_marketplace_config(self, sample_config):
        """get_team_sandbox_settings should configure marketplace correctly."""
        result = teams.get_team_sandbox_settings("ai-teamet", sample_config)
        marketplace = result["extraKnownMarketplaces"]["sundsvall"]
        assert marketplace["source"]["source"] == "github"
        assert marketplace["source"]["repo"] == "sundsvall/claude-plugins-marketplace"

    def test_sandbox_settings_enabled_plugins(self, sample_config):
        """get_team_sandbox_settings should set enabledPlugins correctly."""
        result = teams.get_team_sandbox_settings("ai-teamet", sample_config)
        assert result["enabledPlugins"] == ["ai-teamet@sundsvall"]

    def test_sandbox_settings_different_team(self, sample_config):
        """get_team_sandbox_settings should work for different teams."""
        result = teams.get_team_sandbox_settings("team-evolution", sample_config)
        assert result["enabledPlugins"] == ["team-evolution@sundsvall"]

    def test_sandbox_settings_no_plugin_returns_empty(self, sample_config):
        """get_team_sandbox_settings should return empty dict for base profile."""
        result = teams.get_team_sandbox_settings("base", sample_config)
        assert result == {}

    def test_sandbox_settings_nonexistent_team_returns_empty(self, sample_config):
        """get_team_sandbox_settings should return empty dict for nonexistent team."""
        result = teams.get_team_sandbox_settings("nonexistent", sample_config)
        assert result == {}

    def test_sandbox_settings_default_marketplace_values(self, minimal_config):
        """get_team_sandbox_settings should use defaults for missing marketplace."""
        result = teams.get_team_sandbox_settings("test-team", minimal_config)
        # Should use default values when marketplace config is missing
        assert "extraKnownMarketplaces" in result
        marketplace = result["extraKnownMarketplaces"]["sundsvall"]
        assert marketplace["source"]["repo"] == "sundsvall/claude-plugins-marketplace"

    def test_sandbox_settings_custom_marketplace(self):
        """get_team_sandbox_settings should support custom marketplace config."""
        custom_config = {
            "marketplace": {
                "name": "custom-marketplace",
                "repo": "org/custom-plugins",
            },
            "profiles": {
                "test-team": {
                    "description": "Test",
                    "plugin": "my-plugin",
                },
            },
        }
        result = teams.get_team_sandbox_settings("test-team", custom_config)
        assert "custom-marketplace" in result["extraKnownMarketplaces"]
        assert result["enabledPlugins"] == ["my-plugin@custom-marketplace"]
        marketplace = result["extraKnownMarketplaces"]["custom-marketplace"]
        assert marketplace["source"]["repo"] == "org/custom-plugins"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_team_plugin_id
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetTeamPluginId:
    """Tests for get_team_plugin_id function."""

    def test_plugin_id_format(self, sample_config):
        """get_team_plugin_id should return correctly formatted ID."""
        result = teams.get_team_plugin_id("ai-teamet", sample_config)
        assert result == "ai-teamet@sundsvall"

    def test_plugin_id_different_teams(self, sample_config):
        """get_team_plugin_id should work for different teams."""
        assert teams.get_team_plugin_id("team-evolution", sample_config) == "team-evolution@sundsvall"
        assert teams.get_team_plugin_id("draken", sample_config) == "draken@sundsvall"

    def test_plugin_id_no_plugin_returns_none(self, sample_config):
        """get_team_plugin_id should return None for base profile."""
        result = teams.get_team_plugin_id("base", sample_config)
        assert result is None

    def test_plugin_id_nonexistent_team_returns_none(self, sample_config):
        """get_team_plugin_id should return None for nonexistent team."""
        result = teams.get_team_plugin_id("nonexistent", sample_config)
        assert result is None

    def test_plugin_id_custom_marketplace(self):
        """get_team_plugin_id should use custom marketplace name."""
        custom_config = {
            "marketplace": {
                "name": "custom-mkt",
                "repo": "org/plugins",
            },
            "profiles": {
                "test-team": {
                    "plugin": "test-plugin",
                },
            },
        }
        result = teams.get_team_plugin_id("test-team", custom_config)
        assert result == "test-plugin@custom-mkt"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for validate_team_profile
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateTeamProfile:
    """Tests for validate_team_profile function."""

    def test_validate_valid_team(self, sample_config):
        """validate_team_profile should return valid=True for valid team."""
        result = teams.validate_team_profile("ai-teamet", sample_config)
        assert result["valid"] is True
        assert result["team"] == "ai-teamet"
        assert result["plugin"] == "ai-teamet"
        assert result["errors"] == []

    def test_validate_nonexistent_team(self, sample_config):
        """validate_team_profile should return valid=False for nonexistent team."""
        result = teams.validate_team_profile("nonexistent", sample_config)
        assert result["valid"] is False
        assert "not found" in result["errors"][0]

    def test_validate_base_team_no_warning(self, sample_config):
        """validate_team_profile should not warn for base team without plugin."""
        result = teams.validate_team_profile("base", sample_config)
        assert result["valid"] is True
        assert len(result["warnings"]) == 0  # base is explicitly allowed to have no plugin

    def test_validate_team_without_plugin_warns(self):
        """validate_team_profile should warn for non-base team without plugin."""
        config = {
            "marketplace": {"repo": "org/plugins"},
            "profiles": {
                "empty-team": {
                    "description": "Team with no plugin",
                    "plugin": None,
                },
            },
        }
        result = teams.validate_team_profile("empty-team", config)
        assert result["valid"] is True  # Still valid, just a warning
        assert any("no plugin configured" in w for w in result["warnings"])

    def test_validate_missing_marketplace_repo_warns(self):
        """validate_team_profile should warn for missing marketplace repo."""
        config = {
            "marketplace": {},  # No repo
            "profiles": {
                "test-team": {
                    "plugin": "test-plugin",
                },
            },
        }
        result = teams.validate_team_profile("test-team", config)
        assert result["valid"] is True
        assert any("No marketplace repo" in w for w in result["warnings"])

    def test_validate_result_structure(self, sample_config):
        """validate_team_profile should return correct structure."""
        result = teams.validate_team_profile("ai-teamet", sample_config)
        assert "valid" in result
        assert "team" in result
        assert "plugin" in result
        assert "errors" in result
        assert "warnings" in result

    def test_validate_all_teams(self, sample_config):
        """validate_team_profile should work for all configured teams."""
        for team_name in sample_config["profiles"]:
            result = teams.validate_team_profile(team_name, sample_config)
            # All configured teams should be valid
            assert result["valid"] is True
            assert result["team"] == team_name


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for config loading integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigIntegration:
    """Tests for teams functions using config loading."""

    def test_sandbox_settings_loads_config_when_none(self, temp_config_dir):
        """get_team_sandbox_settings should load config when cfg is None."""
        from scc_cli import config

        # Save a config with the team
        test_config = {
            "marketplace": {
                "name": "sundsvall",
                "repo": "sundsvall/claude-plugins-marketplace",
            },
            "profiles": {
                "ai-teamet": {
                    "description": "AI team",
                    "plugin": "ai-teamet",
                },
            },
        }
        config.save_config(test_config)

        # Call without passing cfg
        result = teams.get_team_sandbox_settings("ai-teamet")
        assert result["enabledPlugins"] == ["ai-teamet@sundsvall"]

    def test_plugin_id_loads_config_when_none(self, temp_config_dir):
        """get_team_plugin_id should load config when cfg is None."""
        from scc_cli import config

        test_config = {
            "marketplace": {"name": "sundsvall"},
            "profiles": {
                "test-team": {"plugin": "test-plugin"},
            },
        }
        config.save_config(test_config)

        result = teams.get_team_plugin_id("test-team")
        assert result == "test-plugin@sundsvall"

    def test_validate_loads_config_when_none(self, temp_config_dir):
        """validate_team_profile should load config when cfg is None."""
        from scc_cli import config

        test_config = {
            "marketplace": {"name": "sundsvall", "repo": "org/plugins"},
            "profiles": {
                "test-team": {"plugin": "test-plugin"},
            },
        }
        config.save_config(test_config)

        result = teams.validate_team_profile("test-team")
        assert result["valid"] is True
        assert result["plugin"] == "test-plugin"
