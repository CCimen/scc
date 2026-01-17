from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class RiskTier(Enum):
    """Risk level for maintenance operations.

    Tier 0: Safe - no confirmation needed
    Tier 1: Changes State - Y/N confirmation
    Tier 2: Destructive - Y/N + impact list
    Tier 3: Factory Reset - type-to-confirm
    """

    SAFE = 0
    CHANGES_STATE = 1
    DESTRUCTIVE = 2
    FACTORY_RESET = 3


@dataclass
class PathInfo:
    """Information about a configuration path.

    Attributes:
        name: Human-readable name (e.g., "Config", "Sessions")
        path: Absolute path to file or directory
        exists: Whether the path exists
        size_bytes: Size in bytes (0 if doesn't exist)
        permissions: Permission string ("rw", "r-", "--")
    """

    name: str
    path: Path
    exists: bool
    size_bytes: int
    permissions: str

    @property
    def size_human(self) -> str:
        """Human-readable size (e.g., '2.1 KB')."""
        if self.size_bytes == 0:
            return "0 B"
        size: float = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if size >= 10 else f"{int(size)} {unit}"
            size = size / 1024
        return f"{size:.1f} TB"


@dataclass
class ResetResult:
    """Result of a reset operation.

    All UI should render from these values, never hardcode paths.
    """

    success: bool
    action_id: str
    risk_tier: RiskTier
    paths: list[Path] = field(default_factory=list)
    removed_count: int = 0
    bytes_freed: int = 0
    backup_path: Path | None = None
    message: str = ""
    next_steps: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def bytes_freed_human(self) -> str:
        """Human-readable bytes freed."""
        if self.bytes_freed == 0:
            return "0 B"
        size: float = self.bytes_freed
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}" if size >= 10 else f"{int(size)} {unit}"
            size = size / 1024
        return f"{size:.1f} TB"


@dataclass
class MaintenancePreview:
    """Preview of what a maintenance operation would do.

    Used for --plan flag and [P]review button.
    """

    action_id: str
    risk_tier: RiskTier
    paths: list[Path]
    description: str
    item_count: int = 0
    bytes_estimate: int = 0
    backup_will_be_created: bool = False
    parameters: dict[str, Any] = field(default_factory=dict)
