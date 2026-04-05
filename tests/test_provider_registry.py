"""Tests for the canonical provider runtime registry."""

from __future__ import annotations

import pytest

from scc_cli.core.contracts import ProviderRuntimeSpec
from scc_cli.core.errors import InvalidProviderError
from scc_cli.core.image_contracts import SCC_CLAUDE_IMAGE_REF, SCC_CODEX_IMAGE_REF
from scc_cli.core.provider_registry import PROVIDER_REGISTRY, get_runtime_spec
from scc_cli.core.provider_resolution import KNOWN_PROVIDERS

# ── Claude spec ──────────────────────────────────────────────────────────


class TestClaudeSpec:
    def test_claude_spec_returns_correct_fields(self) -> None:
        spec = get_runtime_spec("claude")
        assert isinstance(spec, ProviderRuntimeSpec)
        assert spec.provider_id == "claude"
        assert spec.display_name == "Claude Code"
        assert spec.image_ref == SCC_CLAUDE_IMAGE_REF
        assert spec.config_dir == ".claude"
        assert spec.settings_path == ".claude/settings.json"
        assert spec.data_volume == "docker-claude-sandbox-data"


# ── Codex spec ───────────────────────────────────────────────────────────


class TestCodexSpec:
    def test_codex_spec_returns_correct_fields(self) -> None:
        spec = get_runtime_spec("codex")
        assert isinstance(spec, ProviderRuntimeSpec)
        assert spec.provider_id == "codex"
        assert spec.display_name == "Codex"
        assert spec.image_ref == SCC_CODEX_IMAGE_REF
        assert spec.config_dir == ".codex"
        assert spec.settings_path == ".codex/config.toml"
        assert spec.data_volume == "docker-codex-sandbox-data"


# ── Fail-closed lookup ──────────────────────────────────────────────────


class TestFailClosed:
    def test_unknown_provider_raises_invalid_provider_error(self) -> None:
        with pytest.raises(InvalidProviderError) as exc_info:
            get_runtime_spec("gemini")
        err = exc_info.value
        assert err.provider_id == "gemini"
        assert set(err.known_providers) == {"claude", "codex"}

    def test_empty_string_provider_raises(self) -> None:
        with pytest.raises(InvalidProviderError) as exc_info:
            get_runtime_spec("")
        assert exc_info.value.provider_id == ""

    def test_invalid_provider_error_message_includes_known_providers(self) -> None:
        with pytest.raises(InvalidProviderError) as exc_info:
            get_runtime_spec("unknown-agent")
        err = exc_info.value
        assert "unknown-agent" in err.user_message
        assert "claude" in err.user_message
        assert "codex" in err.user_message

    def test_invalid_provider_error_suggested_action(self) -> None:
        with pytest.raises(InvalidProviderError) as exc_info:
            get_runtime_spec("nope")
        err = exc_info.value
        assert "claude" in err.suggested_action
        assert "codex" in err.suggested_action


# ── Registry integrity ──────────────────────────────────────────────────


class TestRegistryIntegrity:
    def test_all_registry_fields_are_nonempty(self) -> None:
        for pid, spec in PROVIDER_REGISTRY.items():
            assert spec.provider_id, f"{pid}: provider_id is empty"
            assert spec.display_name, f"{pid}: display_name is empty"
            assert spec.image_ref, f"{pid}: image_ref is empty"
            assert spec.config_dir, f"{pid}: config_dir is empty"
            assert spec.settings_path, f"{pid}: settings_path is empty"
            assert spec.data_volume, f"{pid}: data_volume is empty"

    def test_registry_keys_match_known_providers(self) -> None:
        """Guardrail: registry stays in sync with KNOWN_PROVIDERS."""
        assert set(PROVIDER_REGISTRY.keys()) == set(KNOWN_PROVIDERS)

    def test_different_providers_have_different_volumes(self) -> None:
        """Coexistence safety: volumes must not collide."""
        volumes = [spec.data_volume for spec in PROVIDER_REGISTRY.values()]
        assert len(volumes) == len(set(volumes))

    def test_different_providers_have_different_config_dirs(self) -> None:
        """Coexistence safety: config dirs must not collide."""
        dirs = [spec.config_dir for spec in PROVIDER_REGISTRY.values()]
        assert len(dirs) == len(set(dirs))

    def test_spec_is_frozen(self) -> None:
        spec = get_runtime_spec("claude")
        with pytest.raises(AttributeError):
            spec.provider_id = "hacked"  # type: ignore[misc]
