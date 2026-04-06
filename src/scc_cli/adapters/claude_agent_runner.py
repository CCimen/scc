"""Claude Code adapter for AgentRunner port."""

from __future__ import annotations

import json
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
        rendered = json.dumps(config, indent=2, sort_keys=True).encode()
        return AgentSettings(rendered_bytes=rendered, path=path, suffix=".json")

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        return AgentCommand(argv=["claude"], env={}, workdir=settings.path.parent)

    def describe(self) -> str:
        return "Claude Code"
