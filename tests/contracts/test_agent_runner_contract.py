"""Contract tests for AgentRunner implementations."""

from __future__ import annotations

from pathlib import Path

import pytest

from scc_cli.adapters.claude_agent_runner import ClaudeAgentRunner
from scc_cli.adapters.codex_agent_runner import CodexAgentRunner
from scc_cli.ports.agent_runner import AgentRunner


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


# ---------------------------------------------------------------------------
# Parametric contract: every AgentRunner satisfies the protocol shape
# ---------------------------------------------------------------------------

_RUNNERS: list[tuple[str, AgentRunner, str, Path]] = [
    (
        "claude",
        ClaudeAgentRunner(),
        "claude",
        Path("/home/agent/.claude/settings.json"),
    ),
    (
        "codex",
        CodexAgentRunner(),
        "codex",
        Path("/home/agent/.codex/config.toml"),
    ),
]


@pytest.mark.parametrize(
    ("label", "runner", "expected_argv0", "expected_settings_path"),
    _RUNNERS,
    ids=[r[0] for r in _RUNNERS],
)
class TestAgentRunnerContract:
    """Every AgentRunner must satisfy the same structural contract."""

    def test_build_settings_round_trips(
        self,
        label: str,
        runner: AgentRunner,
        expected_argv0: str,
        expected_settings_path: Path,
    ) -> None:
        settings = runner.build_settings({"key": "val"}, path=expected_settings_path)
        assert settings.content == {"key": "val"}
        assert settings.path == expected_settings_path

    def test_build_command_returns_expected_argv(
        self,
        label: str,
        runner: AgentRunner,
        expected_argv0: str,
        expected_settings_path: Path,
    ) -> None:
        settings = runner.build_settings({}, path=expected_settings_path)
        command = runner.build_command(settings)
        assert command.argv[0] == expected_argv0
        assert isinstance(command.env, dict)

    def test_describe_returns_non_empty_string(
        self,
        label: str,
        runner: AgentRunner,
        expected_argv0: str,
        expected_settings_path: Path,
    ) -> None:
        desc = runner.describe()
        assert isinstance(desc, str)
        assert len(desc) > 0

    def test_env_is_empty_dict(
        self,
        label: str,
        runner: AgentRunner,
        expected_argv0: str,
        expected_settings_path: Path,
    ) -> None:
        """D003 contract guard: env dict should be clean str→str."""
        settings = runner.build_settings({}, path=expected_settings_path)
        command = runner.build_command(settings)
        assert command.env == {}
