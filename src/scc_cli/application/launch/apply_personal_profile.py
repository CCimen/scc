"""Apply personal profiles to workspace settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scc_cli.application.interaction_requests import ConfirmRequest
from scc_cli.application.personal_profile_policy import (
    ProfilePolicySkip,
    filter_personal_profile_mcp,
    filter_personal_profile_settings,
)
from scc_cli.ports.personal_profile_service import PersonalProfileService


@dataclass(frozen=True)
class ApplyPersonalProfileDependencies:
    """Dependencies for applying personal profiles.

    Invariants:
        - Personal profile operations are delegated to the profile service.

    Args:
        profile_service: Port for personal profile operations.
    """

    profile_service: PersonalProfileService


@dataclass(frozen=True)
class ApplyPersonalProfileRequest:
    """Inputs for applying a personal profile to a workspace.

    Invariants:
        - Confirmation prompts are returned as interaction requests.
        - Applied profile content mirrors existing merge behavior.

    Args:
        workspace_path: Path to the workspace.
        interactive_allowed: Whether the UI may prompt for confirmation.
        confirm_apply: Optional confirmation response when prompted.
        org_config: Optional org config for security enforcement.
    """

    workspace_path: Path
    interactive_allowed: bool
    confirm_apply: bool | None = None
    org_config: dict[str, Any] | None = None


@dataclass(frozen=True)
class ApplyPersonalProfileConfirmation:
    """Confirmation request returned when drift requires user input.

    Invariants:
        - Prompt text remains stable for CLI/UI adapters.

    Args:
        request: ConfirmRequest describing the prompt.
        profile_id: Identifier for the profile being applied.
        default_response: Default response value for the confirmation.
        message: Optional notice to render before prompting.
    """

    request: ConfirmRequest
    profile_id: str
    default_response: bool
    message: str | None


@dataclass(frozen=True)
class ApplyPersonalProfileResult:
    """Result of applying (or skipping) a personal profile.

    Invariants:
        - Applied state is saved only when settings are written.
        - Messages mirror existing CLI output.

    Args:
        profile_id: Identifier for the profile, if one exists.
        applied: Whether the profile was applied.
        message: Optional message to render at the edge.
        skipped_items: Items skipped due to org security policy.
    """

    profile_id: str | None
    applied: bool
    message: str | None = None
    skipped_items: list[ProfilePolicySkip] = field(default_factory=list)


ApplyPersonalProfileOutcome = ApplyPersonalProfileConfirmation | ApplyPersonalProfileResult


def apply_personal_profile(
    request: ApplyPersonalProfileRequest,
    *,
    dependencies: ApplyPersonalProfileDependencies,
) -> ApplyPersonalProfileOutcome:
    """Apply personal profile data to a workspace without prompting.

    Invariants:
        - Drift confirmation mirrors existing CLI flow.
        - Invalid JSON conditions skip applying the profile.

    Args:
        request: ApplyPersonalProfileRequest inputs.
        dependencies: Ports required to load and write profiles.

    Returns:
        Confirmation request or result describing applied state.
    """
    profile, corrupt = dependencies.profile_service.load_personal_profile_with_status(
        request.workspace_path
    )
    if corrupt:
        return ApplyPersonalProfileResult(
            profile_id=None,
            applied=False,
            message="[yellow]Personal profile is invalid JSON. Skipping.[/yellow]",
        )
    if profile is None:
        return ApplyPersonalProfileResult(profile_id=None, applied=False)

    drift = dependencies.profile_service.detect_drift(request.workspace_path)
    if drift and not dependencies.profile_service.workspace_has_overrides(request.workspace_path):
        drift = False

    if drift:
        if not request.interactive_allowed:
            return ApplyPersonalProfileResult(
                profile_id=profile.profile_id,
                applied=False,
                message=(
                    "[yellow]Workspace overrides detected; personal profile not applied.[/yellow]"
                ),
            )
        if request.confirm_apply is None:
            return ApplyPersonalProfileConfirmation(
                request=ConfirmRequest(
                    request_id="apply-personal-profile",
                    prompt="Apply personal profile anyway?",
                ),
                profile_id=profile.profile_id,
                default_response=False,
                message="[yellow]Workspace overrides detected.[/yellow]",
            )
        if request.confirm_apply is False:
            return ApplyPersonalProfileResult(profile_id=profile.profile_id, applied=False)

    existing_settings, settings_invalid = (
        dependencies.profile_service.load_workspace_settings_with_status(request.workspace_path)
    )
    existing_mcp, mcp_invalid = dependencies.profile_service.load_workspace_mcp_with_status(
        request.workspace_path
    )
    if settings_invalid:
        return ApplyPersonalProfileResult(
            profile_id=profile.profile_id,
            applied=False,
            message="[yellow]Invalid JSON in .claude/settings.local.json[/yellow]",
        )
    if mcp_invalid:
        return ApplyPersonalProfileResult(
            profile_id=profile.profile_id,
            applied=False,
            message="[yellow]Invalid JSON in .mcp.json[/yellow]",
        )

    existing_settings = existing_settings or {}
    existing_mcp = existing_mcp or {}

    profile_settings = profile.settings or {}
    profile_mcp = profile.mcp or {}
    policy_skips: list[ProfilePolicySkip] = []
    if request.org_config:
        profile_settings, skipped_plugins = filter_personal_profile_settings(
            profile_settings,
            request.org_config,
        )
        profile_mcp, skipped_mcps = filter_personal_profile_mcp(
            profile_mcp,
            request.org_config,
        )
        policy_skips.extend(skipped_plugins)
        policy_skips.extend(skipped_mcps)

    merged_settings = dependencies.profile_service.merge_personal_settings(
        request.workspace_path,
        existing_settings,
        profile_settings,
    )
    merged_mcp = dependencies.profile_service.merge_personal_mcp(existing_mcp, profile_mcp)

    dependencies.profile_service.write_workspace_settings(request.workspace_path, merged_settings)
    if profile_mcp:
        dependencies.profile_service.write_workspace_mcp(request.workspace_path, merged_mcp)

    dependencies.profile_service.save_applied_state(
        request.workspace_path,
        profile.profile_id,
        dependencies.profile_service.compute_fingerprints(request.workspace_path),
    )

    return ApplyPersonalProfileResult(
        profile_id=profile.profile_id,
        applied=True,
        message="[green]Applied personal profile.[/green]",
        skipped_items=policy_skips,
    )
