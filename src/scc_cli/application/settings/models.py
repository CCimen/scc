from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import TypeAlias

from scc_cli.core.personal_profiles import StructuredDiff
from scc_cli.doctor.types import DoctorResult
from scc_cli.maintenance import MaintenancePreview, PathInfo, RiskTier


class SettingsCategory(Enum):
    """Categories for the settings screen."""

    MAINTENANCE = auto()
    PROFILES = auto()
    DIAGNOSTICS = auto()
    ABOUT = auto()


@dataclass(frozen=True)
class SettingsAction:
    """Represents a settings action with its metadata."""

    id: str
    label: str
    description: str
    risk_tier: RiskTier
    category: SettingsCategory


@dataclass(frozen=True)
class SettingsHeader:
    """Header metadata for the settings screen."""

    profile_name: str
    org_name: str | None


@dataclass(frozen=True)
class SettingsViewModel:
    """View model for settings screen rendering."""

    header: SettingsHeader
    categories: list[SettingsCategory]
    actions_by_category: dict[SettingsCategory, list[SettingsAction]]
    sync_repo_path: str


class ProfileSyncMode(Enum):
    """Profile sync operation modes."""

    CHANGE_PATH = "change_path"
    EXPORT = "export"
    IMPORT = "import"
    FULL_SYNC = "full_sync"


@dataclass(frozen=True)
class ProfileSyncPayload:
    """Input for profile sync operations."""

    mode: ProfileSyncMode
    repo_path: Path
    create_dir: bool = False


@dataclass(frozen=True)
class ProfileSyncPathPayload:
    """Input for updating profile sync paths."""

    new_path: str


@dataclass(frozen=True)
class SupportBundlePayload:
    """Input for generating support bundles."""

    output_path: Path
    redact_paths: bool = True


SettingsActionPayload: TypeAlias = (
    ProfileSyncPayload | ProfileSyncPathPayload | SupportBundlePayload
)


@dataclass(frozen=True)
class SettingsValidationRequest:
    """Input for settings validation."""

    action_id: str
    workspace: Path
    payload: SettingsActionPayload | None = None


class ConfirmationKind(Enum):
    """Confirmation modes for settings actions."""

    CONFIRM = auto()
    TYPE_TO_CONFIRM = auto()


@dataclass(frozen=True)
class ProfileSyncPreview:
    """Preview of a profile sync import."""

    repo_path: Path
    imported: int
    skipped: int
    warnings: list[str] = field(default_factory=list)


SettingsValidationDetail: TypeAlias = MaintenancePreview | ProfileSyncPreview


@dataclass(frozen=True)
class SettingsValidationResult:
    """Validation data for settings actions."""

    action: SettingsAction
    confirmation: ConfirmationKind | None
    detail: SettingsValidationDetail | None = None
    message: str | None = None
    required_phrase: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class SettingsChangeRequest:
    """Input for applying settings actions."""

    action_id: str
    workspace: Path
    payload: SettingsActionPayload | None = None
    confirmed: bool = False


class SettingsActionStatus(Enum):
    """Result status for settings actions."""

    SUCCESS = auto()
    NOOP = auto()
    ERROR = auto()


@dataclass(frozen=True)
class PathsInfo:
    """Rendered path information for settings."""

    paths: list[PathInfo]
    total_size: int


@dataclass(frozen=True)
class VersionInfo:
    """Version information for the CLI."""

    version: str


@dataclass(frozen=True)
class ProfileDiffInfo:
    """Structured diff details for profile comparisons."""

    diff: StructuredDiff


@dataclass(frozen=True)
class SupportBundleInfo:
    """Details about a generated support bundle."""

    output_path: Path


@dataclass(frozen=True)
class DoctorInfo:
    """Doctor result payload."""

    result: DoctorResult


@dataclass(frozen=True)
class ProfileSyncResult:
    """Outcome details for profile sync operations."""

    mode: ProfileSyncMode
    repo_path: Path
    imported: int = 0
    exported: int = 0
    skipped: int = 0
    profile_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


SettingsActionDetail: TypeAlias = (
    PathsInfo | VersionInfo | ProfileDiffInfo | SupportBundleInfo | DoctorInfo | ProfileSyncResult
)


@dataclass(frozen=True)
class SettingsActionResult:
    """Outcome of running a settings action."""

    status: SettingsActionStatus
    message: str | None = None
    detail: SettingsActionDetail | None = None
    details: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    needs_ack: bool = False
    error: str | None = None
