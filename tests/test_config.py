"""Tests for config module.

These tests verify backward compatibility with the original test expectations,
updated for the current architecture where org config is fetched remotely.

For comprehensive tests including XDG paths and migration, see test_config_new.py.
"""

from scc_cli.config import deep_merge


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_empty_override_returns_base(self):
        """Empty override should not modify base."""
        base = {"a": 1, "b": {"c": 2}}
        result = deep_merge(base.copy(), {})
        assert result == {"a": 1, "b": {"c": 2}}

    def test_simple_override(self):
        """Simple keys should be overridden."""
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        """Nested dicts should be merged recursively."""
        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"c": 3}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 1, "c": 3}}

    def test_new_keys_added(self):
        """New keys in override should be added."""
        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 2}

    def test_nested_new_keys(self):
        """New nested keys should be added."""
        base = {"a": {"b": 1}}
        override = {"a": {"c": 2}, "d": 3}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 1, "c": 2}, "d": 3}

    def test_override_dict_with_non_dict(self):
        """Non-dict should override dict."""
        base = {"a": {"b": 1}}
        override = {"a": "string"}
        result = deep_merge(base, override)
        assert result == {"a": "string"}

    def test_override_non_dict_with_dict(self):
        """Dict should override non-dict."""
        base = {"a": "string"}
        override = {"a": {"b": 1}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 1}}


class TestLoadSaveConfig:
    """Tests for config loading and saving."""

    def test_save_and_load_config(self, temp_config_dir):
        """Config should round-trip through save/load."""
        from scc_cli import config

        test_config = {"config_version": "1.0.0", "custom": {"key": "value"}}
        config.save_config(test_config)

        loaded = config.load_config()
        assert loaded["custom"]["key"] == "value"

    def test_load_config_returns_defaults_when_missing(self, temp_config_dir):
        """load_config should return defaults when file doesn't exist."""
        from scc_cli import config

        loaded = config.load_config()
        # config_version is in defaults, not "version" or "profiles"
        assert "config_version" in loaded
        assert loaded["config_version"] == "1.0.0"

    def test_load_config_handles_malformed_json(self, temp_config_dir):
        """load_config should return defaults for malformed JSON."""
        from scc_cli import config

        # Write invalid JSON
        config_file = temp_config_dir / "config.json"
        config_file.write_text("{invalid json}")

        loaded = config.load_config()
        # Should return defaults with config_version
        assert "config_version" in loaded


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Remote Organization Config Architecture
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrganizationHelpers:
    """Tests for organization configuration helpers (remote org config)."""

    def test_is_organization_configured_with_org_source(self, temp_config_dir):
        """is_organization_configured should return True when org source URL is set."""
        from scc_cli import config

        # Create user config with organization_source URL
        user_config = {
            "organization_source": {
                "url": "https://gitlab.example.org/org/config.json",
                "auth": "env:GITLAB_TOKEN",
            }
        }
        config.save_config(user_config)

        assert config.is_organization_configured() is True

    def test_is_organization_configured_returns_false_when_empty(self, temp_config_dir):
        """is_organization_configured should return False when nothing configured."""
        from scc_cli import config

        assert config.is_organization_configured() is False

    def test_is_organization_configured_returns_false_without_url(self, temp_config_dir):
        """is_organization_configured should return False when org source has no URL."""
        from scc_cli import config

        # Create user config with empty organization_source
        user_config = {"organization_source": {}}
        config.save_config(user_config)

        assert config.is_organization_configured() is False

    def test_get_organization_name_returns_none(self, temp_config_dir):
        """get_organization_name should return None (org name comes from remote)."""
        from scc_cli import config

        # Org name comes from remote config, not local
        assert config.get_organization_name() is None

    def test_save_org_config_is_noop(self, temp_config_dir):
        """save_org_config should be a no-op (backward compatibility)."""
        from scc_cli import config

        # This should not raise and should be a no-op
        config.save_org_config({"organization": {"name": "Test"}})

        # No organization.json file should be created
        org_file = temp_config_dir / "organization.json"
        assert not org_file.exists()

    def test_load_org_config_returns_none(self, temp_config_dir):
        """load_org_config should return None (org config is remote)."""
        from scc_cli import config

        # Org config is fetched remotely, not stored locally
        assert config.load_org_config() is None

    def test_list_available_teams_returns_empty(self, temp_config_dir):
        """list_available_teams should return empty list (teams from remote)."""
        from scc_cli import config

        # Teams come from remote org config
        assert config.list_available_teams() == []

    def test_get_team_config_returns_none(self, temp_config_dir):
        """get_team_config should return None (teams from remote)."""
        from scc_cli import config

        # Team config comes from remote org config
        assert config.get_team_config("any-team") is None
