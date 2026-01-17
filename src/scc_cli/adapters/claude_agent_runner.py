"""Claude Code adapter for AgentRunner port."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scc_cli.ports.agent_runner import AgentRunner
from scc_cli.ports.models import AgentCommand, AgentSettings

DEFAULT_SETTINGS_PATH = Path("/home/agent/.claude/settings.json")


class ClaudeAgentRunner(AgentRunner):
    """AgentRunner implementation for Claude Code."""

    def build_settings(
        self, config: dict[str, Any], *, path: Path = DEFAULT_SETTINGS_PATH
    ) -> AgentSettings:
        return AgentSettings(content=config, path=path)

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        return AgentCommand(argv=["claude"], env={}, workdir=settings.path.parent)

    def describe(self) -> str:
        return "Claude Code"
