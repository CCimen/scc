"""Tests for provider resolution and config helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scc_cli.core.errors import ProviderNotAllowedError
from scc_cli.core.provider_resolution import (
    KNOWN_PROVIDERS,
    resolve_active_provider,
)

# ═══════════════════════════════════════════════════════════════════════════════
# resolve_active_provider
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveActiveProvider:
    """Tests for the pure resolver function."""

    def test_default_resolution_returns_claude(self) -> None:
        assert resolve_active_provider(None, None) == "claude"

    def test_cli_flag_overrides_default(self) -> None:
        assert resolve_active_provider("codex", None) == "codex"

    def test_config_overrides_default(self) -> None:
        assert resolve_active_provider(None, "codex") == "codex"

    def test_cli_flag_beats_config(self) -> None:
        assert resolve_active_provider("claude", "codex") == "claude"

    def test_unknown_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider 'fake'"):
            resolve_active_provider("fake", None)

    def test_unknown_config_provider_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown provider 'nope'"):
            resolve_active_provider(None, "nope")

    def test_allowed_providers_empty_means_all_allowed(self) -> None:
        # Empty tuple = no restriction
        assert resolve_active_provider("codex", None, allowed_providers=()) == "codex"

    def test_provider_in_allowed_list_passes(self) -> None:
        assert resolve_active_provider("claude", None, allowed_providers=("claude",)) == "claude"

    def test_provider_not_in_allowed_list_raises(self) -> None:
        with pytest.raises(ProviderNotAllowedError) as exc_info:
            resolve_active_provider("codex", None, allowed_providers=("claude",))
        err = exc_info.value
        assert err.provider_id == "codex"
        assert err.allowed_providers == ("claude",)
        assert "codex" in err.user_message
        assert "claude" in err.user_message

    def test_config_provider_blocked_by_policy(self) -> None:
        with pytest.raises(ProviderNotAllowedError):
            resolve_active_provider(None, "codex", allowed_providers=("claude",))

    def test_known_providers_contains_claude_and_codex(self) -> None:
        assert "claude" in KNOWN_PROVIDERS
        assert "codex" in KNOWN_PROVIDERS


# ═══════════════════════════════════════════════════════════════════════════════
# ProviderNotAllowedError
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderNotAllowedError:
    """Tests for the error type itself."""

    def test_auto_generated_user_message(self) -> None:
        err = ProviderNotAllowedError(
            provider_id="codex",
            allowed_providers=("claude",),
        )
        assert "codex" in err.user_message
        assert "claude" in err.user_message

    def test_auto_generated_suggested_action(self) -> None:
        err = ProviderNotAllowedError(
            provider_id="codex",
            allowed_providers=("claude",),
        )
        assert "allowed providers" in err.suggested_action.lower()

    def test_custom_message_preserved(self) -> None:
        err = ProviderNotAllowedError(
            provider_id="codex",
            allowed_providers=("claude",),
            user_message="Custom message",
        )
        assert err.user_message == "Custom message"


# ═══════════════════════════════════════════════════════════════════════════════
# Config helpers: get_selected_provider / set_selected_provider
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderConfigHelpers:
    """Tests for selected_provider config persistence."""

    def test_get_selected_provider_returns_none_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scc_cli import config as config_mod

        config_dir = tmp_path / ".config" / "scc"
        config_dir.mkdir(parents=True)
        monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", config_dir / "config.json")

        assert config_mod.get_selected_provider() is None

    def test_set_and_get_selected_provider(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scc_cli import config as config_mod

        config_dir = tmp_path / ".config" / "scc"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)

        config_mod.set_selected_provider("codex")
        assert config_mod.get_selected_provider() == "codex"

        # Verify it's actually on disk
        on_disk = json.loads(config_file.read_text())
        assert on_disk["selected_provider"] == "codex"

    def test_set_provider_preserves_other_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from scc_cli import config as config_mod

        config_dir = tmp_path / ".config" / "scc"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "config.json"
        # Pre-populate config with a profile
        config_file.write_text(json.dumps({"selected_profile": "my-team"}))

        monkeypatch.setattr(config_mod, "CONFIG_DIR", config_dir)
        monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)

        config_mod.set_selected_provider("codex")

        on_disk = json.loads(config_file.read_text())
        assert on_disk["selected_provider"] == "codex"
        assert on_disk["selected_profile"] == "my-team"

    def test_selected_provider_in_defaults(self) -> None:
        from scc_cli.config import USER_CONFIG_DEFAULTS

        assert "selected_provider" in USER_CONFIG_DEFAULTS
        assert USER_CONFIG_DEFAULTS["selected_provider"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# NormalizedTeamConfig.allowed_providers field
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizedTeamConfigAllowedProviders:
    """Tests for the allowed_providers field on NormalizedTeamConfig."""

    def test_default_is_empty_tuple(self) -> None:
        from scc_cli.ports.config_models import NormalizedTeamConfig

        cfg = NormalizedTeamConfig(name="test-team")
        assert cfg.allowed_providers == ()

    def test_can_set_allowed_providers(self) -> None:
        from scc_cli.ports.config_models import NormalizedTeamConfig

        cfg = NormalizedTeamConfig(name="test-team", allowed_providers=("claude",))
        assert cfg.allowed_providers == ("claude",)
