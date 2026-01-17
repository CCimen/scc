"""Agent runner port definition."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from scc_cli.ports.models import AgentCommand, AgentSettings


class AgentRunner(Protocol):
    """Abstract agent runner operations."""

    def build_settings(self, config: dict[str, Any], *, path: Path) -> AgentSettings:
        """Render agent settings from a config payload."""

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        """Build the command used to launch the agent."""

    def describe(self) -> str:
        """Return a human-readable description of the runner."""
