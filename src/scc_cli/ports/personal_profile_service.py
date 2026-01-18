"""Personal profile port for application use cases."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from scc_cli.core.personal_profiles import PersonalProfile


class PersonalProfileService(Protocol):
    """Operations for reading and applying personal profiles.

    Invariants:
        - Returned profile data mirrors persisted profile content.
        - Drift detection and merge behavior stay consistent with existing CLI logic.
    """

    def load_personal_profile_with_status(
        self, workspace: Path
    ) -> tuple[PersonalProfile | None, bool]:
        """Load the profile for a workspace, returning (profile, invalid)."""

    def detect_drift(self, workspace: Path) -> bool:
        """Return True when workspace overlays differ from last applied state."""

    def workspace_has_overrides(self, workspace: Path) -> bool:
        """Return True when workspace has local overrides."""

    def load_workspace_settings_with_status(
        self, workspace: Path
    ) -> tuple[dict[str, Any] | None, bool]:
        """Load workspace settings, returning (data, invalid)."""

    def load_workspace_mcp_with_status(self, workspace: Path) -> tuple[dict[str, Any] | None, bool]:
        """Load workspace MCP config, returning (data, invalid)."""

    def merge_personal_settings(
        self,
        workspace: Path,
        existing: dict[str, Any],
        personal: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge personal settings into existing settings."""

    def merge_personal_mcp(
        self, existing: dict[str, Any], personal: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge personal MCP data into existing data."""

    def write_workspace_settings(self, workspace: Path, data: dict[str, Any]) -> None:
        """Persist workspace settings."""

    def write_workspace_mcp(self, workspace: Path, data: dict[str, Any]) -> None:
        """Persist workspace MCP config."""

    def save_applied_state(
        self, workspace: Path, profile_id: str, fingerprints: dict[str, str]
    ) -> None:
        """Persist applied profile state."""

    def compute_fingerprints(self, workspace: Path) -> dict[str, str]:
        """Compute fingerprints for workspace profile files."""
