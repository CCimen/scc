"""Tests for config module - XDG paths and migration.

Phase B.2: Update config.py with XDG paths and migration logic.

This module tests the new config architecture where:
- User config stores organization_source URL (not embedded org data)
- Org config is fetched remotely (see remote.py)
- Migration from ~/.config/scc-cli/ to ~/.config/scc/
"""

import json
from pathlib import Path

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_home(tmp_path, monkeypatch):
    """Create a temporary home directory with config paths."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    return home


@pytest.fixture
def new_config_dir(temp_home):
    """Get the new config directory path."""
    return temp_home / ".config" / "scc"


@pytest.fixture
def legacy_config_dir(temp_home):
    """Get the legacy config directory path."""
    return temp_home / ".config" / "scc-cli"


@pytest.fixture
def cache_dir(temp_home):
    """Get the cache directory path."""
    return temp_home / ".cache" / "scc"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Path Constants
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathConstants:
    """Tests for XDG path constants."""

    def test_config_dir_is_scc_not_scc_cli(self, temp_home):
        """Config dir should be ~/.config/scc/ not ~/.config/scc-cli/."""
        # Reload module to pick up patched Path.home
        import importlib

        from scc_cli import config

        importlib.reload(config)

        assert config.CONFIG_DIR == temp_home / ".config" / "scc"

    def test_legacy_config_dir_exists(self, temp_home):
        """Legacy config dir constant should exist for migration."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        assert hasattr(config, "LEGACY_CONFIG_DIR")
        assert config.LEGACY_CONFIG_DIR == temp_home / ".config" / "scc-cli"

    def test_cache_dir_is_xdg_compliant(self, temp_home):
        """Cache dir should be ~/.cache/scc/."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        assert config.CACHE_DIR == temp_home / ".cache" / "scc"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Migration
# ═══════════════════════════════════════════════════════════════════════════════


class TestMigration:
    """Tests for config migration from scc-cli to scc."""

    def test_migrate_when_only_legacy_exists(self, temp_home, legacy_config_dir, new_config_dir):
        """Should migrate from legacy to new when only legacy exists."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        # Create legacy config
        legacy_config_dir.mkdir(parents=True)
        legacy_config = {"version": "1.0.0", "selected_profile": "platform"}
        (legacy_config_dir / "config.json").write_text(json.dumps(legacy_config))

        result = config.migrate_config_if_needed()

        assert result is True
        assert new_config_dir.exists()
        assert (new_config_dir / "config.json").exists()

        # Verify content was copied
        migrated = json.loads((new_config_dir / "config.json").read_text())
        assert migrated["selected_profile"] == "platform"

    def test_migrate_preserves_legacy_directory(self, temp_home, legacy_config_dir, new_config_dir):
        """Migration should preserve legacy directory (not delete it)."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        # Create legacy config
        legacy_config_dir.mkdir(parents=True)
        (legacy_config_dir / "config.json").write_text('{"version": "1.0.0"}')

        config.migrate_config_if_needed()

        # Legacy should still exist
        assert legacy_config_dir.exists()
        assert (legacy_config_dir / "config.json").exists()

    def test_migrate_skips_when_new_exists(self, temp_home, legacy_config_dir, new_config_dir):
        """Should skip migration if new config dir already exists."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        # Create both dirs
        legacy_config_dir.mkdir(parents=True)
        (legacy_config_dir / "config.json").write_text('{"legacy": true}')
        new_config_dir.mkdir(parents=True)
        (new_config_dir / "config.json").write_text('{"new": true}')

        result = config.migrate_config_if_needed()

        assert result is False
        # New config should be unchanged
        new_content = json.loads((new_config_dir / "config.json").read_text())
        assert new_content.get("new") is True

    def test_migrate_returns_false_for_fresh_install(
        self, temp_home, legacy_config_dir, new_config_dir
    ):
        """Should return False and create new dir for fresh installs."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        # No legacy, no new - fresh install
        assert not legacy_config_dir.exists()
        assert not new_config_dir.exists()

        result = config.migrate_config_if_needed()

        assert result is False
        assert new_config_dir.exists()  # Should create new config dir

    def test_migrate_copies_all_files(self, temp_home, legacy_config_dir, new_config_dir):
        """Migration should copy all files from legacy directory."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        # Create legacy config with multiple files
        legacy_config_dir.mkdir(parents=True)
        (legacy_config_dir / "config.json").write_text('{"config": true}')
        (legacy_config_dir / "sessions.json").write_text('{"sessions": []}')

        config.migrate_config_if_needed()

        # Both files should be copied
        assert (new_config_dir / "config.json").exists()
        assert (new_config_dir / "sessions.json").exists()

    def test_migrate_is_idempotent(self, temp_home, legacy_config_dir, new_config_dir):
        """Multiple migration calls should be safe (idempotent)."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        # Create legacy config
        legacy_config_dir.mkdir(parents=True)
        (legacy_config_dir / "config.json").write_text('{"version": "1.0.0"}')

        # First migration
        result1 = config.migrate_config_if_needed()
        # Second migration
        result2 = config.migrate_config_if_needed()

        assert result1 is True  # Did migrate
        assert result2 is False  # Already migrated, skipped


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for User Config Loading
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadUserConfig:
    """Tests for load_user_config function."""

    def test_load_returns_defaults_when_missing(self, temp_home, new_config_dir):
        """Should return defaults when config file doesn't exist."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)

        user_config = config.load_user_config()

        assert isinstance(user_config, dict)
        assert "config_version" in user_config

    def test_load_returns_saved_config(self, temp_home, new_config_dir):
        """Should return saved config when file exists."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)
        saved_config = {
            "config_version": "1.0.0",
            "selected_profile": "platform",
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": "env:MY_TOKEN",
            },
        }
        (new_config_dir / "config.json").write_text(json.dumps(saved_config))

        loaded = config.load_user_config()

        assert loaded["selected_profile"] == "platform"
        assert loaded["organization_source"]["url"] == "https://example.org/config.json"

    def test_load_handles_corrupted_json(self, temp_home, new_config_dir):
        """Should return defaults for corrupted JSON."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)
        (new_config_dir / "config.json").write_text("{invalid json}")

        loaded = config.load_user_config()

        # Should return defaults, not crash
        assert isinstance(loaded, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for User Config Saving
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveUserConfig:
    """Tests for save_user_config function."""

    def test_save_creates_config_dir(self, temp_home, new_config_dir):
        """Should create config directory if it doesn't exist."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        assert not new_config_dir.exists()

        config.save_user_config({"config_version": "1.0.0"})

        assert new_config_dir.exists()
        assert (new_config_dir / "config.json").exists()

    def test_save_writes_valid_json(self, temp_home, new_config_dir):
        """Saved config should be valid JSON."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)

        test_config = {
            "config_version": "1.0.0",
            "organization_source": {"url": "https://example.org/config.json"},
        }
        config.save_user_config(test_config)

        # Should be parseable JSON
        content = (new_config_dir / "config.json").read_text()
        parsed = json.loads(content)
        assert parsed["organization_source"]["url"] == "https://example.org/config.json"

    def test_save_and_load_roundtrip(self, temp_home, new_config_dir):
        """Config should round-trip through save/load."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)

        original = {
            "config_version": "1.0.0",
            "selected_profile": "api",
            "organization_source": {
                "url": "https://gitlab.example.org/config.json",
                "auth": "env:GITLAB_TOKEN",
            },
            "hooks": {"enabled": True},
        }

        config.save_user_config(original)
        loaded = config.load_user_config()

        assert loaded["selected_profile"] == "api"
        assert loaded["organization_source"]["auth"] == "env:GITLAB_TOKEN"
        assert loaded["hooks"]["enabled"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Profile Selection
# ═══════════════════════════════════════════════════════════════════════════════


class TestProfileSelection:
    """Tests for get_selected_profile and set_selected_profile."""

    def test_get_selected_profile_returns_none_by_default(self, temp_home, new_config_dir):
        """Should return None when no profile is selected."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)

        result = config.get_selected_profile()

        assert result is None

    def test_get_selected_profile_returns_saved_value(self, temp_home, new_config_dir):
        """Should return saved profile name."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)
        (new_config_dir / "config.json").write_text(
            '{"config_version": "1.0.0", "selected_profile": "platform"}'
        )

        result = config.get_selected_profile()

        assert result == "platform"

    def test_set_selected_profile(self, temp_home, new_config_dir):
        """Should save profile selection."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)

        config.set_selected_profile("api")

        # Read back
        result = config.get_selected_profile()
        assert result == "api"

    def test_set_selected_profile_preserves_other_config(self, temp_home, new_config_dir):
        """Setting profile should not overwrite other config."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)
        initial = {
            "config_version": "1.0.0",
            "organization_source": {"url": "https://example.org/config.json"},
            "hooks": {"enabled": True},
        }
        (new_config_dir / "config.json").write_text(json.dumps(initial))

        config.set_selected_profile("platform")

        loaded = config.load_user_config()
        assert loaded["selected_profile"] == "platform"
        assert loaded["organization_source"]["url"] == "https://example.org/config.json"
        assert loaded["hooks"]["enabled"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Standalone Mode
# ═══════════════════════════════════════════════════════════════════════════════


class TestStandaloneMode:
    """Tests for is_standalone_mode function."""

    def test_is_standalone_mode_returns_true_when_no_org_configured(
        self, temp_home, new_config_dir
    ):
        """Should return True when no organization_source is configured.

        This is the default state for fresh installs and solo developers.
        When no org config is present, we default to standalone mode to
        avoid friction for solo devs who don't need team selection.
        """
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)

        result = config.is_standalone_mode()

        assert result is True

    def test_is_standalone_mode_returns_true_when_set(self, temp_home, new_config_dir):
        """Should return True when standalone is set."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)
        (new_config_dir / "config.json").write_text(
            '{"config_version": "1.0.0", "standalone": true}'
        )

        result = config.is_standalone_mode()

        assert result is True

    def test_is_standalone_mode_returns_false_when_org_source_set(self, temp_home, new_config_dir):
        """Should return False when organization_source is configured."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        new_config_dir.mkdir(parents=True, exist_ok=True)
        cfg = {
            "config_version": "1.0.0",
            "organization_source": {"url": "https://example.org/config.json"},
        }
        (new_config_dir / "config.json").write_text(json.dumps(cfg))

        result = config.is_standalone_mode()

        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for deep_merge (Keep existing)
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_empty_override_returns_base(self):
        """Empty override should not modify base."""
        from scc_cli.config import deep_merge

        base = {"a": 1, "b": {"c": 2}}
        result = deep_merge(base.copy(), {})
        assert result == {"a": 1, "b": {"c": 2}}

    def test_simple_override(self):
        """Simple keys should be overridden."""
        from scc_cli.config import deep_merge

        base = {"a": 1, "b": 2}
        override = {"b": 3}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        """Nested dicts should be merged recursively."""
        from scc_cli.config import deep_merge

        base = {"a": {"b": 1, "c": 2}}
        override = {"a": {"c": 3}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 1, "c": 3}}

    def test_new_keys_added(self):
        """New keys in override should be added."""
        from scc_cli.config import deep_merge

        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 2}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Default Config
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefaultConfig:
    """Tests for USER_CONFIG_DEFAULTS constant."""

    def test_default_config_has_version(self, temp_home):
        """Default config should have config_version."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        assert "config_version" in config.USER_CONFIG_DEFAULTS
        assert config.USER_CONFIG_DEFAULTS["config_version"] == "1.0.0"

    def test_default_config_has_cache_settings(self, temp_home):
        """Default config should have cache settings."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        assert "cache" in config.USER_CONFIG_DEFAULTS
        assert config.USER_CONFIG_DEFAULTS["cache"]["enabled"] is True

    def test_default_config_has_hooks_settings(self, temp_home):
        """Default config should have hooks settings."""
        import importlib

        from scc_cli import config

        importlib.reload(config)

        assert "hooks" in config.USER_CONFIG_DEFAULTS
