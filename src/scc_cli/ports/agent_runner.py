"""Agent runner port definition."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from scc_cli.ports.models import AgentCommand, AgentSettings


class AgentRunner(Protocol):
    """Abstract agent runner operations."""

    def build_settings(self, config: dict[str, Any], *, path: Path) -> AgentSettings:
        """Serialize a config dict into provider-native format and return pre-rendered bytes.

        The implementation owns the serialisation format (JSON, TOML, etc.).
        The returned ``AgentSettings.rendered_bytes`` is written verbatim by
        the runtime — no further format assumption is made.  See D035.
        """

    def build_command(self, settings: AgentSettings) -> AgentCommand:
        """Build the command used to launch the agent."""

    def describe(self) -> str:
        """Return a human-readable description of the runner."""
