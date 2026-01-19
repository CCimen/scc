"""Local adapter for personal profile operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scc_cli.core import personal_profiles
from scc_cli.core.personal_profiles import PersonalProfile
from scc_cli.ports.personal_profile_service import PersonalProfileService


class LocalPersonalProfileService(PersonalProfileService):
    """Filesystem-backed personal profile adapter."""

    def load_personal_profile_with_status(
        self, workspace: Path
    ) -> tuple[PersonalProfile | None, bool]:
        return personal_profiles.load_personal_profile_with_status(workspace)

    def detect_drift(self, workspace: Path) -> bool:
        return personal_profiles.detect_drift(workspace)

    def workspace_has_overrides(self, workspace: Path) -> bool:
        return personal_profiles.workspace_has_overrides(workspace)

    def load_workspace_settings_with_status(
        self, workspace: Path
    ) -> tuple[dict[str, Any] | None, bool]:
        return personal_profiles.load_workspace_settings_with_status(workspace)

    def load_workspace_mcp_with_status(self, workspace: Path) -> tuple[dict[str, Any] | None, bool]:
        return personal_profiles.load_workspace_mcp_with_status(workspace)

    def merge_personal_settings(
        self,
        workspace: Path,
        existing: dict[str, Any],
        personal: dict[str, Any],
    ) -> dict[str, Any]:
        return personal_profiles.merge_personal_settings(workspace, existing, personal)

    def merge_personal_mcp(
        self, existing: dict[str, Any], personal: dict[str, Any]
    ) -> dict[str, Any]:
        return personal_profiles.merge_personal_mcp(existing, personal)

    def write_workspace_settings(self, workspace: Path, data: dict[str, Any]) -> None:
        personal_profiles.write_workspace_settings(workspace, data)

    def write_workspace_mcp(self, workspace: Path, data: dict[str, Any]) -> None:
        personal_profiles.write_workspace_mcp(workspace, data)

    def save_applied_state(
        self, workspace: Path, profile_id: str, fingerprints: dict[str, str]
    ) -> None:
        personal_profiles.save_applied_state(workspace, profile_id, fingerprints)

    def compute_fingerprints(self, workspace: Path) -> dict[str, str]:
        return personal_profiles.compute_fingerprints(workspace)
