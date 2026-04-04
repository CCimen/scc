"""Codex CLI adapter for AgentRunner port."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scc_cli.ports.agent_runner import AgentRunner
from scc_cli.ports.models import AgentCommand, AgentSettings

DEFAULT_SETTINGS_PATH = Path("/home/agent/.codex/config.toml")


class CodexAgentRunner(AgentRunner):
    """AgentRunner implementation for OpenAI Codex CLI."""

    def build_settings(
        self, config: dict[str, Any], *, path: Path = DEFAULT_SETTINGS_PATH
    ) -> AgentSettings:
        return AgentSettings(content=config, path=path)

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        return AgentCommand(argv=["codex"], env={}, workdir=settings.path.parent)

    def describe(self) -> str:
        return "Codex"
