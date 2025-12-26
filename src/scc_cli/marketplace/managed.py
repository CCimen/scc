"""
Managed state tracking for SCC marketplace integration.

This module tracks what SCC has added to settings.local.json, enabling
non-destructive merges that preserve user customizations.

Key responsibilities:
1. ManagedState - Data structure tracking SCC-managed entries
2. load_managed_state() - Load tracking state from .scc-managed.json
3. save_managed_state() - Persist tracking state to disk
4. clear_managed_state() - Remove tracking state (for reset operations)

Per RQ-7: Non-destructive merge preserves user-added plugins/marketplaces.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from scc_cli.marketplace.constants import MANAGED_STATE_FILE


@dataclass
class ManagedState:
    """Tracks what SCC has added to settings.local.json.

    This state enables non-destructive merging:
    - On sync: Remove entries in managed_plugins/marketplaces, then add new ones
    - User customizations: Entries NOT in managed lists are preserved

    Attributes:
        managed_plugins: Plugin references (name@marketplace) managed by SCC
        managed_marketplaces: Marketplace paths managed by SCC
        last_sync: Timestamp of last successful sync
        org_config_url: URL of the org config that was synced
        team_id: Team ID that was selected during sync
    """

    managed_plugins: list[str] = field(default_factory=list)
    managed_marketplaces: list[str] = field(default_factory=list)
    last_sync: datetime | None = None
    org_config_url: str | None = None
    team_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        result: dict[str, Any] = {
            "managed_plugins": self.managed_plugins,
            "managed_marketplaces": self.managed_marketplaces,
        }

        if self.last_sync is not None:
            result["last_sync"] = self.last_sync.isoformat()

        if self.org_config_url is not None:
            result["org_config_url"] = self.org_config_url

        if self.team_id is not None:
            result["team_id"] = self.team_id

        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ManagedState:
        """Deserialize from dictionary."""
        last_sync = None
        if "last_sync" in data and data["last_sync"]:
            try:
                last_sync = datetime.fromisoformat(data["last_sync"])
            except (ValueError, TypeError):
                pass

        return cls(
            managed_plugins=data.get("managed_plugins", []),
            managed_marketplaces=data.get("managed_marketplaces", []),
            last_sync=last_sync,
            org_config_url=data.get("org_config_url"),
            team_id=data.get("team_id"),
        )


def load_managed_state(project_dir: Path) -> ManagedState:
    """Load managed state from .scc-managed.json.

    Args:
        project_dir: Project root directory

    Returns:
        ManagedState with tracking data, or empty state if file doesn't exist
    """
    managed_path = project_dir / ".claude" / MANAGED_STATE_FILE

    if not managed_path.exists():
        return ManagedState()

    try:
        data: dict[str, Any] = json.loads(managed_path.read_text())
        return ManagedState.from_dict(data)
    except json.JSONDecodeError:
        # Corrupted file - return empty state
        return ManagedState()


def save_managed_state(project_dir: Path, state: ManagedState) -> None:
    """Save managed state to .scc-managed.json.

    Creates .claude directory if it doesn't exist.

    Args:
        project_dir: Project root directory
        state: ManagedState to persist
    """
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)

    managed_path = claude_dir / MANAGED_STATE_FILE
    managed_path.write_text(json.dumps(state.to_dict(), indent=2))


def clear_managed_state(project_dir: Path) -> None:
    """Remove managed state file.

    Used for reset operations. Preserves .claude directory and other files.

    Args:
        project_dir: Project root directory
    """
    managed_path = project_dir / ".claude" / MANAGED_STATE_FILE

    if managed_path.exists():
        managed_path.unlink()
