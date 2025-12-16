"""Tests for config module."""

from sundsvalls_claude.config import deep_merge


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
        from sundsvalls_claude import config

        test_config = {"version": "1.0.0", "custom": {"key": "value"}}
        config.save_config(test_config)

        loaded = config.load_config()
        assert loaded["custom"]["key"] == "value"

    def test_load_config_returns_defaults_when_missing(self, temp_config_dir):
        """load_config should return defaults when file doesn't exist."""
        from sundsvalls_claude import config

        loaded = config.load_config()
        assert "version" in loaded
        assert "organization" in loaded

    def test_load_config_handles_malformed_json(self, temp_config_dir):
        """load_config should return defaults for malformed JSON."""
        from sundsvalls_claude import config

        # Write invalid JSON
        config_file = temp_config_dir / "config.json"
        config_file.write_text("{invalid json}")

        loaded = config.load_config()
        assert "version" in loaded  # Should return defaults
