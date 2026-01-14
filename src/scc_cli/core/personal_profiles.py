"""Personal project profiles (user-level settings overlay).

Provides per-project personal settings that layer between team config
and workspace overrides without overwriting user changes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse

from scc_cli import config as config_module
from scc_cli.marketplace.managed import load_managed_state
from scc_cli.subprocess_utils import run_command

PROFILE_VERSION = "1"
APPLIED_STATE_FILE = ".scc-personal.json"
REPO_PROFILE_DIR = Path(".scc") / "profiles"
REPO_INDEX_FILE = "index.json"


@dataclass
class PersonalProfile:
    """Represents a saved personal profile for a project."""

    repo_id: str
    profile_id: str
    saved_at: str | None
    settings: dict[str, Any] | None
    mcp: dict[str, Any] | None
    path: Path


@dataclass
class AppliedState:
    """Tracks the last-applied profile fingerprints in a workspace."""

    profile_id: str
    applied_at: str | None
    fingerprints: dict[str, str]


@dataclass
class ProfileStatus:
    """Profile status for TUI display."""

    exists: bool
    has_drift: bool
    import_count: int
    saved_at: str | None


@dataclass
class ProfileExportResult:
    exported: int
    profile_dir: Path
    index_path: Path
    warnings: list[str]


@dataclass
class ProfileImportResult:
    imported: int
    skipped: int
    warnings: list[str]


def get_personal_projects_dir() -> Path:
    """Return the directory for per-project personal profiles."""
    return config_module.CONFIG_DIR / "personal" / "projects"


def get_repo_profile_dir(repo_path: Path) -> Path:
    return repo_path / REPO_PROFILE_DIR


def get_repo_index_path(repo_path: Path) -> Path:
    return get_repo_profile_dir(repo_path) / REPO_INDEX_FILE


def _ensure_personal_dir() -> Path:
    personal_dir = get_personal_projects_dir()
    personal_dir.mkdir(parents=True, exist_ok=True)
    return personal_dir


def _normalize_remote_url(url: str) -> str:
    url = url.strip()
    if not url:
        return url

    # Handle scp-style URLs: git@github.com:org/repo.git
    if url.startswith("git@") and ":" in url:
        user_host, path = url.split(":", 1)
        host = user_host.split("@", 1)[1].lower()
        path = path.lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return f"{host}/{path}"

    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        host = parsed.netloc.lower()
        path = parsed.path.lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return f"{host}/{path}"

    # Fallback: strip .git if present
    return url[:-4] if url.endswith(".git") else url


def _get_remote_url(workspace: Path) -> str | None:
    output = run_command(["git", "-C", str(workspace), "remote", "get-url", "origin"], timeout=5)
    return output if output else None


def get_repo_id(workspace: Path) -> str:
    """Derive a stable repo identifier from git remote or workspace path."""
    remote = _get_remote_url(workspace)
    if remote:
        normalized = _normalize_remote_url(remote)
        return f"remote:{normalized}"
    resolved = str(workspace.resolve())
    return f"path:{resolved}"


def _profile_filename(repo_id: str) -> str:
    digest = hashlib.sha256(repo_id.encode()).hexdigest()[:12]
    return f"{digest}.json"


def get_profile_path(repo_id: str) -> Path:
    return get_personal_projects_dir() / _profile_filename(repo_id)


def _read_json(path: Path) -> dict[str, Any] | None:
    data, _, invalid = _read_json_with_status(path)
    if invalid:
        return None
    return data


def _read_json_with_status(path: Path) -> tuple[dict[str, Any] | None, bool, bool]:
    """Return (data, exists, invalid)."""
    if not path.exists():
        return None, False, False
    try:
        return json.loads(path.read_text()), True, False
    except (json.JSONDecodeError, OSError):
        return None, True, True


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _settings_path(workspace: Path) -> Path:
    return workspace / ".claude" / "settings.local.json"


def _mcp_path(workspace: Path) -> Path:
    return workspace / ".mcp.json"


def load_workspace_settings(workspace: Path) -> dict[str, Any] | None:
    return _read_json(_settings_path(workspace))


def load_workspace_settings_with_status(
    workspace: Path,
) -> tuple[dict[str, Any] | None, bool]:
    data, _, invalid = _read_json_with_status(_settings_path(workspace))
    return data, invalid


def load_workspace_mcp(workspace: Path) -> dict[str, Any] | None:
    return _read_json(_mcp_path(workspace))


def load_workspace_mcp_with_status(workspace: Path) -> tuple[dict[str, Any] | None, bool]:
    data, _, invalid = _read_json_with_status(_mcp_path(workspace))
    return data, invalid


def write_workspace_settings(workspace: Path, data: dict[str, Any]) -> None:
    _write_json(_settings_path(workspace), data)


def write_workspace_mcp(workspace: Path, data: dict[str, Any]) -> None:
    _write_json(_mcp_path(workspace), data)


def save_personal_profile(
    workspace: Path,
    settings: dict[str, Any] | None,
    mcp: dict[str, Any] | None,
) -> PersonalProfile:
    repo_id = get_repo_id(workspace)
    _ensure_personal_dir()
    profile_path = get_profile_path(repo_id)

    saved_at = datetime.now(timezone.utc).isoformat()
    settings_data = settings or {}
    mcp_data = mcp or {}

    payload = {
        "version": PROFILE_VERSION,
        "repo_id": repo_id,
        "saved_at": saved_at,
        "settings": settings_data,
        "mcp": mcp_data,
    }

    _write_json(profile_path, payload)

    return PersonalProfile(
        repo_id=repo_id,
        profile_id=repo_id,
        saved_at=saved_at,
        settings=settings_data,
        mcp=mcp_data,
        path=profile_path,
    )


def load_personal_profile(workspace: Path) -> PersonalProfile | None:
    profile, _ = load_personal_profile_with_status(workspace)
    return profile


def load_personal_profile_with_status(
    workspace: Path,
) -> tuple[PersonalProfile | None, bool]:
    repo_id = get_repo_id(workspace)
    path = get_profile_path(repo_id)
    data, exists, invalid = _read_json_with_status(path)
    if not exists:
        return None, False
    if invalid or not data:
        return None, True
    return (
        PersonalProfile(
            repo_id=data.get("repo_id", repo_id),
            profile_id=data.get("repo_id", repo_id),
            saved_at=data.get("saved_at"),
            settings=data.get("settings", {}),
            mcp=data.get("mcp", {}),
            path=path,
        ),
        False,
    )


def list_personal_profiles() -> list[PersonalProfile]:
    profiles: list[PersonalProfile] = []
    base = get_personal_projects_dir()
    if not base.exists():
        return profiles
    for path in sorted(base.glob("*.json")):
        data, _, invalid = _read_json_with_status(path)
        if invalid or not data:
            continue
        profiles.append(
            PersonalProfile(
                repo_id=data.get("repo_id", path.stem),
                profile_id=data.get("repo_id", path.stem),
                saved_at=data.get("saved_at"),
                settings=data.get("settings", {}),
                mcp=data.get("mcp", {}),
                path=path,
            )
        )
    return profiles


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def load_repo_index(repo_path: Path) -> tuple[dict[str, Any], bool]:
    """Load repo index, returning (index_data, invalid)."""
    index_path = get_repo_index_path(repo_path)
    data, exists, invalid = _read_json_with_status(index_path)
    if not exists or invalid or not isinstance(data, dict):
        return {"version": PROFILE_VERSION, "profiles": {}}, invalid

    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
    return {"version": data.get("version", PROFILE_VERSION), "profiles": profiles}, False


def save_repo_index(repo_path: Path, index: dict[str, Any]) -> None:
    index_path = get_repo_index_path(repo_path)
    _write_json(index_path, index)


def export_profiles_to_repo(
    repo_path: Path,
    profiles: list[PersonalProfile] | None = None,
) -> ProfileExportResult:
    warnings: list[str] = []
    exported = 0

    repo_profile_dir = get_repo_profile_dir(repo_path)
    repo_profile_dir.mkdir(parents=True, exist_ok=True)

    index, invalid = load_repo_index(repo_path)
    if invalid:
        warnings.append("Invalid index.json detected; rebuilding index.")
        index = {"version": PROFILE_VERSION, "profiles": {}}

    existing_map: dict[str, str] = {}
    for path in sorted(repo_profile_dir.glob("*.json")):
        data, _, invalid_profile = _read_json_with_status(path)
        if invalid_profile or not data:
            continue
        repo_id = data.get("repo_id")
        if repo_id:
            existing_map[repo_id] = path.name

    index_profiles = index.get("profiles", {})
    if not isinstance(index_profiles, dict):
        index_profiles = {}
    index_profiles.update(existing_map)
    index = {"version": index.get("version", PROFILE_VERSION), "profiles": index_profiles}

    if profiles is None:
        profiles = list_personal_profiles()

    if not profiles:
        warnings.append("No personal profiles found to export.")

    for profile in profiles:
        data, _, invalid_profile = _read_json_with_status(profile.path)
        if invalid_profile or not data:
            warnings.append(f"Invalid personal profile skipped: {profile.path.name}")
            continue

        repo_id = data.get("repo_id", profile.repo_id)
        if not repo_id:
            warnings.append(f"Missing repo_id in profile: {profile.path.name}")
            continue

        filename = _profile_filename(repo_id)
        dest_path = repo_profile_dir / filename
        _write_json(dest_path, data)
        index_profiles[repo_id] = filename
        exported += 1

    index["profiles"] = index_profiles
    save_repo_index(repo_path, index)

    return ProfileExportResult(
        exported=exported,
        profile_dir=repo_profile_dir,
        index_path=get_repo_index_path(repo_path),
        warnings=warnings,
    )


def import_profiles_from_repo(
    repo_path: Path,
    force: bool = False,
    dry_run: bool = False,
) -> ProfileImportResult:
    warnings: list[str] = []
    imported = 0
    skipped = 0

    repo_profile_dir = get_repo_profile_dir(repo_path)
    if not repo_profile_dir.exists():
        warnings.append("No profiles directory found in repo.")
        return ProfileImportResult(imported=0, skipped=0, warnings=warnings)

    index, invalid = load_repo_index(repo_path)
    if invalid:
        warnings.append("Invalid index.json detected; falling back to profile scan.")
        index = {"version": PROFILE_VERSION, "profiles": {}}

    entries: list[tuple[str | None, Path]] = []
    profiles_map = index.get("profiles", {})
    seen_files: set[str] = set()
    if profiles_map:
        for repo_id, filename in profiles_map.items():
            path = repo_profile_dir / filename
            entries.append((repo_id, path))
            seen_files.add(filename)

    for path in sorted(repo_profile_dir.glob("*.json")):
        if path.name in seen_files:
            continue
        entries.append((None, path))

    _ensure_personal_dir()

    for repo_id_hint, path in entries:
        data, _, invalid_profile = _read_json_with_status(path)
        if invalid_profile or not data:
            warnings.append(f"Invalid profile file skipped: {path.name}")
            skipped += 1
            continue

        repo_id = data.get("repo_id") or repo_id_hint
        if not repo_id:
            warnings.append(f"Missing repo_id in profile file: {path.name}")
            skipped += 1
            continue

        dest_path = get_profile_path(repo_id)
        existing, exists, invalid_existing = _read_json_with_status(dest_path)
        if invalid_existing:
            warnings.append(f"Invalid local profile skipped: {dest_path.name}")
            skipped += 1
            continue

        if exists and existing is not None:
            if _canonical_json(existing) == _canonical_json(data):
                skipped += 1
                continue
            if not force:
                warnings.append(f"Local profile differs; skipped {repo_id}")
                skipped += 1
                continue

        if not dry_run:
            _write_json(dest_path, data)
        imported += 1

    return ProfileImportResult(imported=imported, skipped=skipped, warnings=warnings)


def _fingerprint_json(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text())
        canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
    except json.JSONDecodeError:
        return hashlib.sha256(path.read_text().encode()).hexdigest()
    except OSError:
        return ""


def compute_fingerprints(workspace: Path) -> dict[str, str]:
    return {
        "settings.local.json": _fingerprint_json(_settings_path(workspace)),
        ".mcp.json": _fingerprint_json(_mcp_path(workspace)),
    }


def load_applied_state(workspace: Path) -> AppliedState | None:
    state_path = workspace / ".claude" / APPLIED_STATE_FILE
    data = _read_json(state_path)
    if not data:
        return None
    return AppliedState(
        profile_id=data.get("profile_id", ""),
        applied_at=data.get("applied_at"),
        fingerprints=data.get("fingerprints", {}),
    )


def save_applied_state(workspace: Path, profile_id: str, fingerprints: dict[str, str]) -> None:
    state_path = workspace / ".claude" / APPLIED_STATE_FILE
    payload = {
        "profile_id": profile_id,
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "fingerprints": fingerprints,
    }
    _write_json(state_path, payload)


def detect_drift(workspace: Path) -> bool:
    state = load_applied_state(workspace)
    if not state:
        return False
    current = compute_fingerprints(workspace)
    return current != state.fingerprints


def merge_personal_settings(
    workspace: Path,
    existing: dict[str, Any],
    personal: dict[str, Any],
) -> dict[str, Any]:
    """Merge personal settings without overwriting user customizations.

    - Personal overrides may replace team-managed entries
    - Existing user edits are preserved
    """
    managed = load_managed_state(workspace)
    managed_plugins = set(managed.managed_plugins)
    managed_marketplaces = set(managed.managed_marketplaces)

    merged = dict(existing)

    existing_plugins_raw = existing.get("enabledPlugins", {})
    if isinstance(existing_plugins_raw, list):
        existing_plugins: dict[str, bool] = {p: True for p in existing_plugins_raw}
    else:
        existing_plugins = dict(existing_plugins_raw)

    personal_plugins_raw = personal.get("enabledPlugins", {})
    if isinstance(personal_plugins_raw, list):
        personal_plugins = {p: True for p in personal_plugins_raw}
    else:
        personal_plugins = dict(personal_plugins_raw)

    for plugin, enabled in personal_plugins.items():
        if plugin in managed_plugins or plugin not in existing_plugins:
            existing_plugins[plugin] = enabled

    merged["enabledPlugins"] = existing_plugins

    existing_marketplaces = existing.get("extraKnownMarketplaces", {})
    if isinstance(existing_marketplaces, list):
        existing_marketplaces = {}

    personal_marketplaces = personal.get("extraKnownMarketplaces", {})
    if isinstance(personal_marketplaces, list):
        personal_marketplaces = {}

    for name, config in personal_marketplaces.items():
        if name not in existing_marketplaces:
            existing_marketplaces[name] = config
            continue

        source = existing_marketplaces.get(name, {}).get("source", {})
        path = source.get("path", "")
        if path in managed_marketplaces:
            existing_marketplaces[name] = config

    merged["extraKnownMarketplaces"] = existing_marketplaces

    for key, value in personal.items():
        if key in {"enabledPlugins", "extraKnownMarketplaces"}:
            continue
        if key not in merged:
            merged[key] = value
            continue
        if isinstance(merged.get(key), dict) and isinstance(value, dict):
            for sub_key, sub_value in value.items():
                if sub_key not in merged[key]:
                    merged[key][sub_key] = sub_value

    return merged


def merge_personal_mcp(existing: dict[str, Any], personal: dict[str, Any]) -> dict[str, Any]:
    if not personal:
        return existing
    if not existing:
        return personal
    merged = json.loads(json.dumps(personal))
    config_module.deep_merge(merged, existing)
    if isinstance(merged, dict):
        return cast(dict[str, Any], merged)
    return {}


def workspace_has_overrides(workspace: Path) -> bool:
    return _settings_path(workspace).exists() or _mcp_path(workspace).exists()


def extract_personal_plugins(profile: PersonalProfile) -> list[str]:
    settings = profile.settings or {}
    plugins = settings.get("enabledPlugins", {})
    if isinstance(plugins, list):
        return [str(p) for p in plugins]
    return [str(p) for p in plugins.keys()]


def extract_personal_mcp(profile: PersonalProfile) -> dict[str, Any]:
    return profile.mcp or {}


def _normalize_plugins(value: Any) -> dict[str, bool]:
    if isinstance(value, list):
        return {str(p): True for p in value}
    if isinstance(value, dict):
        return {str(k): bool(v) for k, v in value.items()}
    return {}


def _normalize_marketplaces(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def compute_sandbox_import_candidates(
    workspace_settings: dict[str, Any] | None,
    sandbox_settings: dict[str, Any] | None,
) -> tuple[list[str], dict[str, Any]]:
    """Return plugins/marketplaces present in sandbox settings but missing in workspace."""
    if not sandbox_settings:
        return [], {}

    workspace_settings = workspace_settings or {}

    workspace_plugins = _normalize_plugins(workspace_settings.get("enabledPlugins"))
    sandbox_plugins = _normalize_plugins(sandbox_settings.get("enabledPlugins"))
    missing_plugins = sorted([p for p in sandbox_plugins if p not in workspace_plugins])

    workspace_marketplaces = _normalize_marketplaces(
        workspace_settings.get("extraKnownMarketplaces")
    )
    sandbox_marketplaces = _normalize_marketplaces(sandbox_settings.get("extraKnownMarketplaces"))
    missing_marketplaces = {
        name: config
        for name, config in sandbox_marketplaces.items()
        if name not in workspace_marketplaces
    }

    return missing_plugins, missing_marketplaces


def merge_sandbox_imports(
    workspace_settings: dict[str, Any],
    missing_plugins: list[str],
    missing_marketplaces: dict[str, Any],
) -> dict[str, Any]:
    if not missing_plugins and not missing_marketplaces:
        return workspace_settings

    merged = dict(workspace_settings)

    plugins_value = merged.get("enabledPlugins")
    if isinstance(plugins_value, list):
        plugins_map = {str(p): True for p in plugins_value}
    elif isinstance(plugins_value, dict):
        plugins_map = dict(plugins_value)
    else:
        plugins_map = {}

    for plugin in missing_plugins:
        plugins_map[plugin] = True
    if plugins_map:
        merged["enabledPlugins"] = plugins_map

    marketplaces_value = merged.get("extraKnownMarketplaces")
    if isinstance(marketplaces_value, dict):
        marketplaces_map = dict(marketplaces_value)
    else:
        marketplaces_map = {}
    marketplaces_map.update(missing_marketplaces)
    if marketplaces_map:
        merged["extraKnownMarketplaces"] = marketplaces_map

    return merged


def build_diff_text(label: str, before: dict[str, Any], after: dict[str, Any]) -> str:
    import difflib

    before_text = json.dumps(before, indent=2, sort_keys=True).splitlines()
    after_text = json.dumps(after, indent=2, sort_keys=True).splitlines()
    diff_lines = difflib.unified_diff(
        before_text,
        after_text,
        fromfile=f"{label} (current)",
        tofile=f"{label} (personal)",
        lineterm="",
    )
    return "\n".join(diff_lines)


@dataclass
class DiffItem:
    """A single diff item for the TUI overlay."""

    name: str
    status: str  # "added" (+), "removed" (-), "modified" (~)
    section: str  # "plugins", "mcp_servers", "marketplaces"


@dataclass
class StructuredDiff:
    """Structured diff for TUI display."""

    items: list[DiffItem]
    total_count: int

    @property
    def is_empty(self) -> bool:
        return len(self.items) == 0


def compute_structured_diff(
    workspace_settings: dict[str, Any] | None,
    profile_settings: dict[str, Any] | None,
    workspace_mcp: dict[str, Any] | None,
    profile_mcp: dict[str, Any] | None,
) -> StructuredDiff:
    """Compute structured diff between workspace and profile for TUI display.

    Args:
        workspace_settings: Current workspace settings (settings.local.json)
        profile_settings: Saved profile settings
        workspace_mcp: Current workspace MCP config (.mcp.json)
        profile_mcp: Saved profile MCP config

    Returns:
        StructuredDiff with items showing additions, removals, modifications
    """
    items: list[DiffItem] = []

    workspace_settings = workspace_settings or {}
    profile_settings = profile_settings or {}
    workspace_mcp = workspace_mcp or {}
    profile_mcp = profile_mcp or {}

    # Compare plugins
    ws_plugins = _normalize_plugins(workspace_settings.get("enabledPlugins"))
    prof_plugins = _normalize_plugins(profile_settings.get("enabledPlugins"))

    # Plugins in profile but not workspace (would be added on apply)
    for plugin in sorted(prof_plugins.keys()):
        if plugin not in ws_plugins:
            items.append(DiffItem(name=plugin, status="added", section="plugins"))

    # Plugins in workspace but not profile (would be removed on apply)
    for plugin in sorted(ws_plugins.keys()):
        if plugin not in prof_plugins:
            items.append(DiffItem(name=plugin, status="removed", section="plugins"))

    # Compare marketplaces
    ws_markets = _normalize_marketplaces(workspace_settings.get("extraKnownMarketplaces"))
    prof_markets = _normalize_marketplaces(profile_settings.get("extraKnownMarketplaces"))

    for name in sorted(prof_markets.keys()):
        if name not in ws_markets:
            items.append(DiffItem(name=name, status="added", section="marketplaces"))
        elif prof_markets[name] != ws_markets[name]:
            items.append(DiffItem(name=name, status="modified", section="marketplaces"))

    for name in sorted(ws_markets.keys()):
        if name not in prof_markets:
            items.append(DiffItem(name=name, status="removed", section="marketplaces"))

    # Compare MCP servers
    ws_servers = workspace_mcp.get("mcpServers", {})
    prof_servers = profile_mcp.get("mcpServers", {})

    for name in sorted(prof_servers.keys()):
        if name not in ws_servers:
            items.append(DiffItem(name=name, status="added", section="mcp_servers"))
        elif prof_servers[name] != ws_servers[name]:
            items.append(DiffItem(name=name, status="modified", section="mcp_servers"))

    for name in sorted(ws_servers.keys()):
        if name not in prof_servers:
            items.append(DiffItem(name=name, status="removed", section="mcp_servers"))

    return StructuredDiff(items=items, total_count=len(items))


def get_profile_status(workspace: Path) -> ProfileStatus:
    """Get profile status for TUI display.

    Returns a ProfileStatus with:
    - exists: Whether a saved profile exists for this workspace
    - has_drift: Whether workspace has drifted from last-applied profile
    - import_count: Number of sandbox plugins available for import
    - saved_at: When the profile was last saved (ISO format)
    """
    profile = load_personal_profile(workspace)

    if not profile:
        return ProfileStatus(
            exists=False,
            has_drift=False,
            import_count=0,
            saved_at=None,
        )

    # Check for drift
    has_drift = detect_drift(workspace)

    # Check for sandbox import candidates
    import_count = 0
    try:
        from ..docker.launch import get_sandbox_settings

        sandbox_settings = get_sandbox_settings()
        if sandbox_settings:
            workspace_settings = load_workspace_settings(workspace) or {}
            missing_plugins, missing_marketplaces = compute_sandbox_import_candidates(
                workspace_settings, sandbox_settings
            )
            import_count = len(missing_plugins) + len(missing_marketplaces)
    except Exception:
        # If docker is unavailable or errors, just return 0 imports
        pass

    return ProfileStatus(
        exists=True,
        has_drift=has_drift,
        import_count=import_count,
        saved_at=profile.saved_at,
    )
