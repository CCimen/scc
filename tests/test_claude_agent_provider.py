"""Characterization tests for ClaudeAgentProvider.

These tests pin the exact AgentLaunchSpec shape that ClaudeAgentProvider
produces so that regressions in the adapter seam are caught immediately.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scc_cli.adapters.claude_agent_provider import ClaudeAgentProvider

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def provider() -> ClaudeAgentProvider:
    return ClaudeAgentProvider()


# ═══════════════════════════════════════════════════════════════════════════════
# capability_profile
# ═══════════════════════════════════════════════════════════════════════════════


def test_capability_profile_returns_claude_metadata(provider: ClaudeAgentProvider) -> None:
    """capability_profile() must return the stable Claude provider metadata."""
    profile = provider.capability_profile()

    assert profile.provider_id == "claude"
    assert profile.display_name == "Claude Code"
    assert profile.required_destination_set == "anthropic-core"
    assert profile.supports_resume is True


# ═══════════════════════════════════════════════════════════════════════════════
# prepare_launch — without settings_path
# ═══════════════════════════════════════════════════════════════════════════════


def test_prepare_launch_without_settings_produces_clean_spec(
    provider: ClaudeAgentProvider, tmp_path: Path
) -> None:
    """No settings_path → artifact_paths is empty, env is empty, argv is canonical."""
    spec = provider.prepare_launch(config={}, workspace=tmp_path, settings_path=None)

    assert spec.provider_id == "claude"
    assert spec.argv == ("claude", "--dangerously-skip-permissions")
    assert spec.env == {}
    assert spec.artifact_paths == ()
    assert spec.required_destination_sets == ("anthropic-core",)
    assert spec.workdir == tmp_path


# ═══════════════════════════════════════════════════════════════════════════════
# prepare_launch — with settings_path
# ═══════════════════════════════════════════════════════════════════════════════


def test_prepare_launch_with_settings_includes_artifact_path(
    provider: ClaudeAgentProvider, tmp_path: Path
) -> None:
    """settings_path present → it appears in artifact_paths; env stays empty."""
    fake_settings = tmp_path / "claude-settings.json"
    fake_settings.write_text("{}")

    spec = provider.prepare_launch(
        config={"mcpServers": {}}, workspace=tmp_path, settings_path=fake_settings
    )

    assert fake_settings in spec.artifact_paths
    assert spec.env == {}


# ═══════════════════════════════════════════════════════════════════════════════
# prepare_launch — env contract (D003 / KNOWLEDGE.md)
# ═══════════════════════════════════════════════════════════════════════════════


def test_prepare_launch_env_is_clean_str_to_str(
    provider: ClaudeAgentProvider, tmp_path: Path
) -> None:
    """All env values must be plain str, never nested dicts (D003 contract)."""
    spec = provider.prepare_launch(config={"key": "value"}, workspace=tmp_path)

    for key, val in spec.env.items():
        assert isinstance(key, str), f"env key {key!r} is not str"
        assert isinstance(val, str), f"env value for {key!r} is not str: {val!r}"
