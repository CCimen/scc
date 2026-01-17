from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from pathlib import Path

from scc_cli import config
from scc_cli.core.personal_profiles import (
    compute_fingerprints,
    compute_structured_diff,
    export_profiles_to_repo,
    import_profiles_from_repo,
    list_personal_profiles,
    load_personal_profile,
    load_workspace_mcp,
    load_workspace_settings,
    merge_personal_mcp,
    merge_personal_settings,
    save_applied_state,
    save_personal_profile,
    write_workspace_mcp,
    write_workspace_settings,
)
from scc_cli.doctor.core import run_doctor
from scc_cli.maintenance import (
    MaintenancePreview,
    ResetResult,
    RiskTier,
    clear_cache,
    clear_contexts,
    delete_all_sessions,
    factory_reset,
    get_paths,
    get_total_size,
    preview_operation,
    prune_containers,
    prune_sessions,
    reset_config,
    reset_exceptions,
)
from scc_cli.support_bundle import create_bundle

from .models import (
    ConfirmationKind,
    DoctorInfo,
    PathsInfo,
    ProfileDiffInfo,
    ProfileSyncMode,
    ProfileSyncPathPayload,
    ProfileSyncPayload,
    ProfileSyncPreview,
    ProfileSyncResult,
    SettingsAction,
    SettingsActionResult,
    SettingsActionStatus,
    SettingsCategory,
    SettingsChangeRequest,
    SettingsHeader,
    SettingsValidationRequest,
    SettingsValidationResult,
    SettingsViewModel,
    SupportBundleInfo,
    SupportBundlePayload,
    VersionInfo,
)


@dataclass(frozen=True)
class SettingsContext:
    """Context for settings use cases."""

    workspace: Path


SETTINGS_ACTIONS: list[SettingsAction] = [
    SettingsAction(
        id="clear_cache",
        label="Clear cache",
        description="Remove regenerable cache files",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="clear_contexts",
        label="Clear contexts",
        description="Clear recent work contexts",
        risk_tier=RiskTier.CHANGES_STATE,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="prune_containers",
        label="Prune containers",
        description="Remove stopped Docker containers",
        risk_tier=RiskTier.CHANGES_STATE,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="prune_sessions",
        label="Prune sessions",
        description="Remove old sessions (keeps recent)",
        risk_tier=RiskTier.CHANGES_STATE,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="reset_exceptions",
        label="Reset exceptions",
        description="Clear all policy exceptions",
        risk_tier=RiskTier.DESTRUCTIVE,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="delete_sessions",
        label="Delete all sessions",
        description="Remove entire session history",
        risk_tier=RiskTier.DESTRUCTIVE,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="reset_config",
        label="Reset configuration",
        description="Reset to defaults (requires setup)",
        risk_tier=RiskTier.DESTRUCTIVE,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="factory_reset",
        label="Factory reset",
        description="Remove all SCC data",
        risk_tier=RiskTier.FACTORY_RESET,
        category=SettingsCategory.MAINTENANCE,
    ),
    SettingsAction(
        id="profile_save",
        label="Save profile",
        description="Capture current workspace settings",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.PROFILES,
    ),
    SettingsAction(
        id="profile_apply",
        label="Apply profile",
        description="Restore saved settings to workspace",
        risk_tier=RiskTier.CHANGES_STATE,
        category=SettingsCategory.PROFILES,
    ),
    SettingsAction(
        id="profile_diff",
        label="Show diff",
        description="Compare profile vs workspace",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.PROFILES,
    ),
    SettingsAction(
        id="profile_sync",
        label="Sync profiles",
        description="Export/import via repo",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.PROFILES,
    ),
    SettingsAction(
        id="run_doctor",
        label="Run doctor",
        description="Check prerequisites and system health",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.DIAGNOSTICS,
    ),
    SettingsAction(
        id="generate_support_bundle",
        label="Generate support bundle",
        description="Create diagnostic bundle for troubleshooting",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.DIAGNOSTICS,
    ),
    SettingsAction(
        id="show_paths",
        label="Show paths",
        description="Show SCC file locations",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.ABOUT,
    ),
    SettingsAction(
        id="show_version",
        label="Show version",
        description="Show build info and CLI version",
        risk_tier=RiskTier.SAFE,
        category=SettingsCategory.ABOUT,
    ),
]


def load_settings_state(context: SettingsContext) -> SettingsViewModel:
    """Load settings state for UI rendering."""

    header = SettingsHeader(
        profile_name=config.get_selected_profile() or "standalone",
        org_name=_load_org_name(),
    )
    return SettingsViewModel(
        header=header,
        categories=list(SettingsCategory),
        actions_by_category=_group_actions_by_category(SETTINGS_ACTIONS),
        sync_repo_path=_load_sync_repo_path(),
    )


def validate_settings(request: SettingsValidationRequest) -> SettingsValidationResult | None:
    """Validate a settings action and return confirmation details."""

    action = _get_action(request.action_id)
    if action is None:
        raise ValueError(f"Unknown settings action: {request.action_id}")

    if action.id == "profile_sync" and isinstance(request.payload, ProfileSyncPayload):
        return _validate_profile_sync(action, request.payload)

    if action.risk_tier in (RiskTier.CHANGES_STATE, RiskTier.DESTRUCTIVE):
        preview = _safe_preview(action.id)
        return SettingsValidationResult(
            action=action,
            confirmation=ConfirmationKind.CONFIRM,
            detail=preview,
            message=f"{action.label}: {action.description}",
        )

    if action.risk_tier == RiskTier.FACTORY_RESET:
        preview = _safe_preview(action.id)
        return SettingsValidationResult(
            action=action,
            confirmation=ConfirmationKind.TYPE_TO_CONFIRM,
            detail=preview,
            message="Type RESET to confirm",
            required_phrase="RESET",
        )

    return None


def apply_settings_change(request: SettingsChangeRequest) -> SettingsActionResult:
    """Apply a settings action and return the result."""

    action = _get_action(request.action_id)
    if action is None:
        raise ValueError(f"Unknown settings action: {request.action_id}")

    try:
        if action.id == "clear_cache":
            result = clear_cache()
            message = f"Cache cleared: {result.bytes_freed_human}"
            return _result_from_reset(result, message)

        if action.id == "clear_contexts":
            result = clear_contexts()
            message = f"Cleared {result.removed_count} contexts"
            return _result_from_reset(result, message)

        if action.id == "prune_containers":
            result = prune_containers(dry_run=False)
            message = f"Pruned {result.removed_count} containers"
            return _result_from_reset(result, message)

        if action.id == "prune_sessions":
            result = prune_sessions(older_than_days=30, keep_n=20, dry_run=False)
            message = f"Pruned {result.removed_count} sessions"
            return _result_from_reset(result, message)

        if action.id == "reset_exceptions":
            result = reset_exceptions(scope="all")
            message = f"Reset {result.removed_count} exceptions"
            return _result_from_reset(result, message)

        if action.id == "delete_sessions":
            result = delete_all_sessions()
            message = f"Deleted {result.removed_count} sessions"
            return _result_from_reset(result, message)

        if action.id == "reset_config":
            result = reset_config()
            message = "Configuration reset. Run 'scc setup' to reconfigure."
            return _result_from_reset(result, message)

        if action.id == "factory_reset":
            results = factory_reset()
            failed = [r for r in results if not r.success]
            if failed:
                error = failed[0].message
                return SettingsActionResult(
                    status=SettingsActionStatus.ERROR,
                    message=error,
                    error=error,
                )
            message = "Factory reset complete. Run 'scc setup' to reconfigure."
            return SettingsActionResult(status=SettingsActionStatus.SUCCESS, message=message)

        if action.id == "profile_save":
            return _apply_profile_save(request.workspace)

        if action.id == "profile_apply":
            return _apply_profile_apply(request.workspace)

        if action.id == "profile_diff":
            return _apply_profile_diff(request.workspace)

        if action.id == "profile_sync":
            return _apply_profile_sync(request)

        if action.id == "run_doctor":
            doctor_result = run_doctor(request.workspace)
            return SettingsActionResult(
                status=SettingsActionStatus.SUCCESS,
                detail=DoctorInfo(result=doctor_result),
                needs_ack=True,
            )

        if action.id == "generate_support_bundle":
            return _apply_support_bundle(request)

        if action.id == "show_paths":
            return SettingsActionResult(
                status=SettingsActionStatus.SUCCESS,
                detail=PathsInfo(paths=get_paths(), total_size=get_total_size()),
                needs_ack=True,
            )

        if action.id == "show_version":
            version = _load_version()
            return SettingsActionResult(
                status=SettingsActionStatus.SUCCESS,
                detail=VersionInfo(version=version),
                needs_ack=True,
            )

        return SettingsActionResult(
            status=SettingsActionStatus.NOOP,
            message=None,
        )
    except Exception as exc:  # pragma: no cover - defensive for unexpected failures
        return SettingsActionResult(
            status=SettingsActionStatus.ERROR,
            message=str(exc),
            error=str(exc),
        )


def _group_actions_by_category(
    actions: list[SettingsAction],
) -> dict[SettingsCategory, list[SettingsAction]]:
    grouped: dict[SettingsCategory, list[SettingsAction]] = {
        category: [] for category in SettingsCategory
    }
    for action in actions:
        grouped[action.category].append(action)
    return grouped


def _get_action(action_id: str) -> SettingsAction | None:
    for action in SETTINGS_ACTIONS:
        if action.id == action_id:
            return action
    return None


def _load_org_name() -> str | None:
    org_config = config.load_cached_org_config()
    if not org_config:
        return None
    org_data = org_config.get("organization", {}) if isinstance(org_config, dict) else {}
    name = org_data.get("name") or org_data.get("id")
    return str(name) if name is not None else None


def _load_sync_repo_path() -> str:
    try:
        cfg = config.load_user_config()
    except Exception:
        cfg = {}
    last_repo = cfg.get("sync", {}).get("last_repo") if isinstance(cfg, dict) else None
    if last_repo:
        return str(last_repo)
    return "~/dotfiles/scc-profiles"


def _save_sync_repo_path(path: str) -> None:
    try:
        cfg = config.load_user_config()
    except Exception:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    cfg.setdefault("sync", {})
    if isinstance(cfg["sync"], dict):
        cfg["sync"]["last_repo"] = path
    config.save_user_config(cfg)


def _safe_preview(action_id: str) -> MaintenancePreview | None:
    try:
        return preview_operation(action_id)
    except Exception:
        return None


def _validate_profile_sync(
    action: SettingsAction,
    payload: ProfileSyncPayload,
) -> SettingsValidationResult | None:
    if payload.mode == ProfileSyncMode.EXPORT:
        if not payload.repo_path.exists():
            return SettingsValidationResult(
                action=action,
                confirmation=ConfirmationKind.CONFIRM,
                message=f"Create directory? {payload.repo_path}",
            )
        return None

    if payload.mode == ProfileSyncMode.IMPORT:
        if not payload.repo_path.exists():
            return SettingsValidationResult(
                action=action,
                confirmation=None,
                error=f"Path not found: {payload.repo_path}",
            )
        preview = import_profiles_from_repo(payload.repo_path, dry_run=True)
        if preview.imported == 0 and preview.skipped == 0:
            return SettingsValidationResult(
                action=action,
                confirmation=None,
                error="No profiles found in repository.",
            )
        return SettingsValidationResult(
            action=action,
            confirmation=ConfirmationKind.CONFIRM,
            detail=ProfileSyncPreview(
                repo_path=payload.repo_path,
                imported=preview.imported,
                skipped=preview.skipped,
                warnings=preview.warnings,
            ),
            message=f"Import preview from {payload.repo_path}",
        )

    return None


def _result_from_reset(result: ResetResult, message: str) -> SettingsActionResult:
    if not result.success:
        error = result.message
        return SettingsActionResult(
            status=SettingsActionStatus.ERROR,
            message=error,
            error=error,
        )
    return SettingsActionResult(status=SettingsActionStatus.SUCCESS, message=message)


def _apply_profile_save(workspace: Path) -> SettingsActionResult:
    settings = load_workspace_settings(workspace)
    mcp = load_workspace_mcp(workspace)

    if not settings and not mcp:
        return SettingsActionResult(
            status=SettingsActionStatus.NOOP,
            details=[
                "No workspace settings found to save.",
                "Create .claude/settings.local.json or .mcp.json first.",
            ],
            needs_ack=True,
        )

    profile = save_personal_profile(workspace, settings, mcp)
    fingerprints = compute_fingerprints(workspace)
    save_applied_state(workspace, profile.profile_id, fingerprints)

    return SettingsActionResult(
        status=SettingsActionStatus.SUCCESS,
        message="Profile saved",
        details=[f"Profile saved: {profile.path.name}"],
        needs_ack=True,
    )


def _apply_profile_apply(workspace: Path) -> SettingsActionResult:
    profile = load_personal_profile(workspace)
    if not profile:
        return SettingsActionResult(
            status=SettingsActionStatus.NOOP,
            details=[
                "No profile saved for this workspace.",
                "Use 'Save profile' first.",
            ],
            needs_ack=True,
        )

    current_settings = load_workspace_settings(workspace) or {}
    current_mcp = load_workspace_mcp(workspace) or {}

    if profile.settings:
        merged_settings = merge_personal_settings(workspace, current_settings, profile.settings)
        write_workspace_settings(workspace, merged_settings)

    if profile.mcp:
        merged_mcp = merge_personal_mcp(current_mcp, profile.mcp)
        write_workspace_mcp(workspace, merged_mcp)

    fingerprints = compute_fingerprints(workspace)
    save_applied_state(workspace, profile.profile_id, fingerprints)

    return SettingsActionResult(
        status=SettingsActionStatus.SUCCESS,
        message="Profile applied",
        details=["Profile applied to workspace"],
        needs_ack=True,
    )


def _apply_profile_diff(workspace: Path) -> SettingsActionResult:
    profile = load_personal_profile(workspace)
    if not profile:
        return SettingsActionResult(
            status=SettingsActionStatus.NOOP,
            details=["No profile saved for this workspace."],
            needs_ack=True,
        )

    current_settings = load_workspace_settings(workspace) or {}
    current_mcp = load_workspace_mcp(workspace) or {}

    diff = compute_structured_diff(
        workspace_settings=current_settings,
        profile_settings=profile.settings,
        workspace_mcp=current_mcp,
        profile_mcp=profile.mcp,
    )

    if diff.is_empty:
        return SettingsActionResult(
            status=SettingsActionStatus.SUCCESS,
            details=["Profile is in sync with workspace"],
            needs_ack=True,
        )

    return SettingsActionResult(
        status=SettingsActionStatus.SUCCESS,
        detail=ProfileDiffInfo(diff=diff),
        needs_ack=True,
    )


def _apply_profile_sync(request: SettingsChangeRequest) -> SettingsActionResult:
    payload = request.payload
    if isinstance(payload, ProfileSyncPathPayload):
        _save_sync_repo_path(payload.new_path)
        return SettingsActionResult(
            status=SettingsActionStatus.SUCCESS,
            details=[f"Path updated to: {payload.new_path}"],
            needs_ack=True,
        )

    if not isinstance(payload, ProfileSyncPayload):
        return SettingsActionResult(
            status=SettingsActionStatus.ERROR,
            message="Profile sync requires a payload",
            error="missing payload",
        )

    if payload.mode == ProfileSyncMode.EXPORT:
        return _apply_profile_sync_export(payload)
    if payload.mode == ProfileSyncMode.IMPORT:
        return _apply_profile_sync_import(payload, request.confirmed)
    if payload.mode == ProfileSyncMode.FULL_SYNC:
        return _apply_profile_sync_full(payload)

    return SettingsActionResult(status=SettingsActionStatus.NOOP)


def _apply_profile_sync_export(payload: ProfileSyncPayload) -> SettingsActionResult:
    profiles = list_personal_profiles()
    if not profiles:
        return SettingsActionResult(
            status=SettingsActionStatus.NOOP,
            details=[
                "No profiles to export.",
                "Save a profile first with 'Save profile'.",
            ],
            needs_ack=True,
        )

    if not payload.repo_path.exists() and not payload.create_dir:
        return SettingsActionResult(
            status=SettingsActionStatus.NOOP,
            details=[f"Path does not exist: {payload.repo_path}"],
            needs_ack=True,
        )

    payload.repo_path.mkdir(parents=True, exist_ok=True)
    result = export_profiles_to_repo(payload.repo_path, profiles)
    _save_sync_repo_path(str(payload.repo_path))

    sync_result = ProfileSyncResult(
        mode=ProfileSyncMode.EXPORT,
        repo_path=payload.repo_path,
        exported=result.exported,
        profile_ids=[profile.repo_id for profile in profiles],
        warnings=result.warnings,
    )

    return SettingsActionResult(
        status=SettingsActionStatus.SUCCESS,
        message=f"Exported {result.exported} profile(s)",
        detail=sync_result,
        needs_ack=True,
    )


def _apply_profile_sync_import(
    payload: ProfileSyncPayload,
    confirmed: bool,
) -> SettingsActionResult:
    if not payload.repo_path.exists():
        return SettingsActionResult(
            status=SettingsActionStatus.NOOP,
            details=[f"Path not found: {payload.repo_path}"],
            needs_ack=True,
        )

    if not confirmed:
        return SettingsActionResult(status=SettingsActionStatus.NOOP)

    result = import_profiles_from_repo(payload.repo_path, dry_run=False)
    _save_sync_repo_path(str(payload.repo_path))

    sync_result = ProfileSyncResult(
        mode=ProfileSyncMode.IMPORT,
        repo_path=payload.repo_path,
        imported=result.imported,
        skipped=result.skipped,
        warnings=result.warnings,
    )

    return SettingsActionResult(
        status=SettingsActionStatus.SUCCESS,
        message=f"Imported {result.imported} profile(s)",
        detail=sync_result,
        needs_ack=True,
    )


def _apply_profile_sync_full(payload: ProfileSyncPayload) -> SettingsActionResult:
    imported = 0
    exported = 0
    if payload.repo_path.exists():
        import_result = import_profiles_from_repo(payload.repo_path, dry_run=False)
        imported = import_result.imported
    else:
        payload.repo_path.mkdir(parents=True, exist_ok=True)

    profiles = list_personal_profiles()
    if profiles:
        export_result = export_profiles_to_repo(payload.repo_path, profiles)
        exported = export_result.exported

    _save_sync_repo_path(str(payload.repo_path))

    sync_result = ProfileSyncResult(
        mode=ProfileSyncMode.FULL_SYNC,
        repo_path=payload.repo_path,
        imported=imported,
        exported=exported,
    )

    return SettingsActionResult(
        status=SettingsActionStatus.SUCCESS,
        message=f"Synced: {imported} imported, {exported} exported",
        detail=sync_result,
        needs_ack=True,
    )


def _apply_support_bundle(request: SettingsChangeRequest) -> SettingsActionResult:
    payload = request.payload
    if not isinstance(payload, SupportBundlePayload):
        return SettingsActionResult(
            status=SettingsActionStatus.ERROR,
            message="Support bundle requires a payload",
            error="missing payload",
        )

    create_bundle(output_path=payload.output_path, redact_paths_flag=payload.redact_paths)
    info = SupportBundleInfo(output_path=payload.output_path)

    return SettingsActionResult(
        status=SettingsActionStatus.SUCCESS,
        message=f"Support bundle saved to {payload.output_path.name}",
        detail=info,
        needs_ack=True,
    )


def _load_version() -> str:
    try:
        return get_version("scc-cli")
    except PackageNotFoundError:
        return "unknown"
