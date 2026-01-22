"""Tests for personal profile integration in start flow."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scc_cli.adapters.personal_profile_service_local import LocalPersonalProfileService
from scc_cli.application.launch import (
    ApplyPersonalProfileConfirmation,
    ApplyPersonalProfileDependencies,
    ApplyPersonalProfileRequest,
    ApplyPersonalProfileResult,
    apply_personal_profile,
)
from scc_cli.core import personal_profiles
from scc_cli.core.enums import TargetType
from scc_cli.core.personal_profiles import PersonalProfile
from scc_cli.marketplace.managed import ManagedState, save_managed_state


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(data, indent=2))


@dataclass
class FakePersonalProfileService:
    profile: PersonalProfile | None
    corrupt_profile: bool = False
    drift: bool = False
    has_overrides: bool = False
    settings_invalid: bool = False
    mcp_invalid: bool = False
    writes: dict[str, Any] = field(default_factory=dict)

    def load_personal_profile_with_status(
        self, workspace: Path
    ) -> tuple[PersonalProfile | None, bool]:
        return self.profile, self.corrupt_profile

    def detect_drift(self, workspace: Path) -> bool:
        return self.drift

    def workspace_has_overrides(self, workspace: Path) -> bool:
        return self.has_overrides

    def load_workspace_settings_with_status(
        self, workspace: Path
    ) -> tuple[dict[str, Any] | None, bool]:
        return {}, self.settings_invalid

    def load_workspace_mcp_with_status(self, workspace: Path) -> tuple[dict[str, Any] | None, bool]:
        return {}, self.mcp_invalid

    def merge_personal_settings(
        self, workspace: Path, existing: dict[str, Any], personal: dict[str, Any]
    ) -> dict[str, Any]:
        return {**existing, **personal}

    def merge_personal_mcp(
        self, existing: dict[str, Any], personal: dict[str, Any]
    ) -> dict[str, Any]:
        return {**existing, **personal}

    def write_workspace_settings(self, workspace: Path, data: dict[str, Any]) -> None:
        self.writes["settings"] = data

    def write_workspace_mcp(self, workspace: Path, data: dict[str, Any]) -> None:
        self.writes["mcp"] = data

    def save_applied_state(
        self, workspace: Path, profile_id: str, fingerprints: dict[str, str]
    ) -> None:
        self.writes["applied_state"] = {
            "profile_id": profile_id,
            "fingerprints": fingerprints,
        }

    def compute_fingerprints(self, workspace: Path) -> dict[str, str]:
        return {"settings.local.json": "hash", ".mcp.json": "hash"}


def test_apply_personal_profile_applies(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.local.json"
    _write_json(settings_path, {"enabledPlugins": {"team@market": True}})

    save_managed_state(
        tmp_path,
        ManagedState(managed_plugins=["team@market"], managed_marketplaces=[]),
    )

    personal_profiles.save_personal_profile(
        tmp_path,
        {"enabledPlugins": {"team@market": False, "user@market": True}},
        {},
    )

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=False,
        confirm_apply=None,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(
            profile_service=LocalPersonalProfileService(),
        ),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    assert outcome.applied is True
    assert outcome.profile_id is not None

    updated = personal_profiles.load_workspace_settings(tmp_path) or {}
    assert updated.get("enabledPlugins", {}).get("team@market") is False
    assert updated.get("enabledPlugins", {}).get("user@market") is True

    state = personal_profiles.load_applied_state(tmp_path)
    assert state is not None
    assert state.profile_id == outcome.profile_id


def test_personal_profile_drift_requires_confirmation(tmp_path: Path) -> None:
    profile = PersonalProfile(
        repo_id="repo",
        profile_id="profile-1",
        saved_at=None,
        settings={"foo": "bar"},
        mcp=None,
        path=tmp_path / "profile.json",
    )
    service = FakePersonalProfileService(
        profile=profile,
        drift=True,
        has_overrides=True,
    )

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=True,
        confirm_apply=None,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(profile_service=service),
    )

    assert isinstance(outcome, ApplyPersonalProfileConfirmation)
    assert outcome.default_response is False
    assert outcome.profile_id == "profile-1"


def test_personal_profile_drift_skipped_when_non_interactive(tmp_path: Path) -> None:
    profile = PersonalProfile(
        repo_id="repo",
        profile_id="profile-2",
        saved_at=None,
        settings={"foo": "bar"},
        mcp=None,
        path=tmp_path / "profile.json",
    )
    service = FakePersonalProfileService(
        profile=profile,
        drift=True,
        has_overrides=True,
    )

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=False,
        confirm_apply=None,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(profile_service=service),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    assert outcome.applied is False
    assert "Workspace overrides detected" in (outcome.message or "")


def test_personal_profile_confirmation_rejects_apply(tmp_path: Path) -> None:
    profile = PersonalProfile(
        repo_id="repo",
        profile_id="profile-3",
        saved_at=None,
        settings={"foo": "bar"},
        mcp=None,
        path=tmp_path / "profile.json",
    )
    service = FakePersonalProfileService(
        profile=profile,
        drift=True,
        has_overrides=True,
    )

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=True,
        confirm_apply=False,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(profile_service=service),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    assert outcome.applied is False


def test_personal_profile_invalid_json_settings(tmp_path: Path) -> None:
    profile = PersonalProfile(
        repo_id="repo",
        profile_id="profile-4",
        saved_at=None,
        settings={"foo": "bar"},
        mcp=None,
        path=tmp_path / "profile.json",
    )
    service = FakePersonalProfileService(
        profile=profile,
        settings_invalid=True,
    )

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=True,
        confirm_apply=True,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(profile_service=service),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    assert outcome.applied is False
    assert "Invalid JSON" in (outcome.message or "")


def test_personal_profile_invalid_json_mcp(tmp_path: Path) -> None:
    profile = PersonalProfile(
        repo_id="repo",
        profile_id="profile-5",
        saved_at=None,
        settings={"foo": "bar"},
        mcp={"mcp": "config"},
        path=tmp_path / "profile.json",
    )
    service = FakePersonalProfileService(
        profile=profile,
        mcp_invalid=True,
    )

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=True,
        confirm_apply=True,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(profile_service=service),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    assert outcome.applied is False
    assert "Invalid JSON" in (outcome.message or "")


def test_personal_profile_blocks_org_blocked_plugins(tmp_path: Path) -> None:
    personal_profiles.save_personal_profile(
        tmp_path,
        {"enabledPlugins": {"blocked@market": True, "allowed@market": True}},
        {},
    )
    org_config = {"security": {"blocked_plugins": ["blocked@market"]}}

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=False,
        confirm_apply=None,
        org_config=org_config,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(
            profile_service=LocalPersonalProfileService(),
        ),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    updated = personal_profiles.load_workspace_settings(tmp_path) or {}
    plugins = updated.get("enabledPlugins", {})
    assert "blocked@market" not in plugins
    assert plugins.get("allowed@market") is True
    assert any(
        skipped.item == "blocked@market" and skipped.target_type == TargetType.PLUGIN
        for skipped in outcome.skipped_items
    )


def test_personal_profile_blocks_org_blocked_mcp(tmp_path: Path) -> None:
    personal_profiles.save_personal_profile(
        tmp_path,
        {},
        {
            "mcpServers": {
                "blocked": {"type": "http", "url": "https://blocked.example.com"},
                "allowed": {"type": "http", "url": "https://good.example.com"},
            }
        },
    )
    org_config = {"security": {"blocked_mcp_servers": ["blocked.example.com"]}}

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=False,
        confirm_apply=None,
        org_config=org_config,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(
            profile_service=LocalPersonalProfileService(),
        ),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    updated_mcp = personal_profiles.load_workspace_mcp(tmp_path) or {}
    servers = updated_mcp.get("mcpServers", {})
    assert "blocked" not in servers
    assert "allowed" in servers
    assert any(
        skipped.item == "blocked" and skipped.target_type == TargetType.MCP_SERVER
        for skipped in outcome.skipped_items
    )


def test_personal_profile_blocks_stdio_mcp_when_disabled(tmp_path: Path) -> None:
    personal_profiles.save_personal_profile(
        tmp_path,
        {},
        {
            "mcpServers": {
                "stdio-server": {"type": "stdio", "command": "/usr/bin/stdio"},
            }
        },
    )
    org_config = {"security": {"allow_stdio_mcp": False}}

    request = ApplyPersonalProfileRequest(
        workspace_path=tmp_path,
        interactive_allowed=False,
        confirm_apply=None,
        org_config=org_config,
    )
    outcome = apply_personal_profile(
        request,
        dependencies=ApplyPersonalProfileDependencies(
            profile_service=LocalPersonalProfileService(),
        ),
    )

    assert isinstance(outcome, ApplyPersonalProfileResult)
    assert any(
        skipped.item == "stdio-server" and skipped.target_type == TargetType.MCP_SERVER
        for skipped in outcome.skipped_items
    )
    assert personal_profiles.load_workspace_mcp(tmp_path) is None
