"""Tests for ClaudeAgentRunner adapter."""

from __future__ import annotations

import json
from pathlib import Path

from scc_cli.adapters.claude_agent_runner import DEFAULT_SETTINGS_PATH, ClaudeAgentRunner


class TestClaudeAgentRunner:
    """Canonical test shape for ClaudeAgentRunner."""

    def test_build_settings_returns_claude_path(self) -> None:
        runner = ClaudeAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        assert settings.path == Path("/home/agent/.claude/settings.json")
        assert settings.suffix == ".json"

    def test_build_settings_renders_json_bytes(self) -> None:
        """D035: runner serialises config to JSON, not dict passthrough."""
        runner = ClaudeAgentRunner()
        config = {"enabledPlugins": ["tool@official"], "permissions": {}}
        settings = runner.build_settings(config, path=DEFAULT_SETTINGS_PATH)
        assert isinstance(settings.rendered_bytes, bytes)
        # Verify it's valid JSON by round-tripping
        parsed = json.loads(settings.rendered_bytes)
        assert parsed["enabledPlugins"] == ["tool@official"]
        assert parsed["permissions"] == {}

    def test_build_settings_empty_config_renders_valid_json(self) -> None:
        """Empty config produces valid JSON bytes."""
        runner = ClaudeAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        parsed = json.loads(settings.rendered_bytes)
        assert parsed == {}

    def test_build_command_returns_claude_argv(self) -> None:
        runner = ClaudeAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        command = runner.build_command(settings)
        assert command.argv == ["claude"]

    def test_describe_returns_claude_code(self) -> None:
        runner = ClaudeAgentRunner()
        assert runner.describe() == "Claude Code"

    def test_env_is_clean_str_to_str(self) -> None:
        """D003 contract guard: env dict must be empty str→str."""
        runner = ClaudeAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        command = runner.build_command(settings)
        assert command.env == {}
        assert isinstance(command.env, dict)
