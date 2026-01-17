"""Domain models used by port protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MountSpec:
    """Describe a filesystem mount for a sandbox runtime."""

    source: Path
    target: Path
    read_only: bool = False


@dataclass(frozen=True)
class SandboxSpec:
    """Specification for launching a sandbox."""

    image: str
    workspace_mount: MountSpec
    workdir: Path
    env: dict[str, str] = field(default_factory=dict)
    network_policy: str | None = None
    user: str | None = None
    group: str | None = None
    extra_mounts: list[MountSpec] = field(default_factory=list)
    continue_session: bool = False
    force_new: bool = False
    agent_settings: AgentSettings | None = None
    org_config: dict[str, Any] | None = None


@dataclass(frozen=True)
class SandboxHandle:
    """Opaque identifier for a sandbox session."""

    sandbox_id: str
    name: str | None = None


class SandboxState(str, Enum):
    """Lifecycle state for a sandbox session."""

    CREATED = "created"
    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SandboxStatus:
    """Status for a sandbox session with timestamps."""

    state: SandboxState
    created_at: datetime | None = None
    started_at: datetime | None = None
    stopped_at: datetime | None = None


@dataclass(frozen=True)
class AgentCommand:
    """Command specification for launching an agent."""

    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    workdir: Path | None = None


@dataclass(frozen=True)
class AgentSettings:
    """Settings payload and target location for an agent."""

    content: dict[str, Any]
    path: Path
