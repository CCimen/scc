"""Tests for CodexAgentRunner adapter."""

from __future__ import annotations

from pathlib import Path

import tomllib

from scc_cli.adapters.codex_agent_runner import DEFAULT_SETTINGS_PATH, CodexAgentRunner


class TestCodexAgentRunner:
    """Canonical 4-test shape for CodexAgentRunner."""

    def test_build_settings_returns_codex_path(self) -> None:
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        assert settings.path == Path("/home/agent/.codex/config.toml")
        assert settings.suffix == ".toml"

    def test_build_settings_renders_toml_bytes(self) -> None:
        """D035: runner serialises config to TOML, not dict passthrough."""
        runner = CodexAgentRunner()
        config = {"cli_auth_credentials_store": "file", "model": "o3"}
        settings = runner.build_settings(config, path=DEFAULT_SETTINGS_PATH)
        assert isinstance(settings.rendered_bytes, bytes)
        # Verify it's valid TOML by round-tripping through tomllib
        parsed = tomllib.loads(settings.rendered_bytes.decode())
        assert parsed["cli_auth_credentials_store"] == "file"
        assert parsed["model"] == "o3"

    def test_build_settings_renders_nested_toml(self) -> None:
        """TOML sections for nested dicts."""
        runner = CodexAgentRunner()
        config = {"sandbox": {"auto_approve": True}, "model": "o3"}
        settings = runner.build_settings(config, path=DEFAULT_SETTINGS_PATH)
        parsed = tomllib.loads(settings.rendered_bytes.decode())
        assert parsed["model"] == "o3"
        assert parsed["sandbox"]["auto_approve"] is True

    def test_build_command_returns_codex_argv(self) -> None:
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        command = runner.build_command(settings)
        assert command.argv == ["codex"]
        assert "--dangerously-skip-permissions" not in command.argv

    def test_describe_returns_codex(self) -> None:
        runner = CodexAgentRunner()
        assert runner.describe() == "Codex"

    def test_env_is_clean_str_to_str(self) -> None:
        """D003 contract guard: env dict must be empty str→str."""
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        command = runner.build_command(settings)
        assert command.env == {}
        assert isinstance(command.env, dict)
