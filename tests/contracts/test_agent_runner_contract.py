"""Contract tests for AgentRunner implementations."""

from __future__ import annotations

from pathlib import Path

from scc_cli.adapters.claude_agent_runner import ClaudeAgentRunner


def test_agent_runner_builds_settings_and_command() -> None:
    runner = ClaudeAgentRunner()
    payload = {"enabledPlugins": ["tool@official"]}
    settings_path = Path("/home/agent/.claude/settings.json")

    settings = runner.build_settings(payload, path=settings_path)
    command = runner.build_command(settings)

    assert settings.content == payload
    assert settings.path == settings_path
    assert command.argv[0] == "claude"
    assert runner.describe()
