"""Tests for config module.

These tests verify config utilities and remote org config helpers.
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

    def test_save_and_load_user_config(self, temp_config_dir):
        """User config should round-trip through save/load."""
        from scc_cli import config

        test_config = {"config_version": "1.0.0", "custom": {"key": "value"}}
        config.save_user_config(test_config)

        loaded = config.load_user_config()
        assert loaded["custom"]["key"] == "value"

    def test_load_user_config_returns_defaults_when_missing(self, temp_config_dir):
        """load_user_config should return defaults when file doesn't exist."""
        from scc_cli import config

        loaded = config.load_user_config()
        # config_version is in defaults, not "version" or "profiles"
        assert "config_version" in loaded
        assert loaded["config_version"] == "1.0.0"

    def test_load_user_config_handles_malformed_json(self, temp_config_dir):
        """load_user_config should raise ConfigError for malformed JSON."""
        import pytest

        from scc_cli import config
        from scc_cli.core.errors import ConfigError

        # Write invalid JSON
        config_file = temp_config_dir / "config.json"
        config_file.write_text("{invalid json}")

        # Should raise ConfigError with actionable guidance
        with pytest.raises(ConfigError) as exc_info:
            config.load_user_config()

        # Verify error has actionable guidance
        assert "Invalid JSON" in exc_info.value.user_message
        assert exc_info.value.suggested_action is not None


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
        config.save_user_config(user_config)

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
        config.save_user_config(user_config)

        assert config.is_organization_configured() is False
