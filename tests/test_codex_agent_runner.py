"""Tests for CodexAgentRunner adapter."""

from __future__ import annotations

from pathlib import Path

from scc_cli.adapters.codex_agent_runner import DEFAULT_SETTINGS_PATH, CodexAgentRunner


class TestCodexAgentRunner:
    """Canonical 4-test shape for CodexAgentRunner."""

    def test_build_settings_returns_codex_path(self) -> None:
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        assert settings.path == Path("/home/agent/.codex/config.toml")

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
