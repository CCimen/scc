"""Workspace-local config for per-checkout UX preferences.

This file stores non-sensitive state under ``.scc/config.local.json`` inside a
workspace. The primary use is remembering the last provider used in that
workspace without leaking the preference into global config or version control.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

WORKSPACE_CONFIG_DIRNAME = ".scc"
WORKSPACE_CONFIG_FILENAME = "config.local.json"
_GIT_EXCLUDE_PATTERN = f"{WORKSPACE_CONFIG_DIRNAME}/"


def get_workspace_local_config_path(workspace_root: str | Path) -> Path:
    """Return the local SCC config path for a workspace root."""
    root = Path(workspace_root).expanduser()
    return root / WORKSPACE_CONFIG_DIRNAME / WORKSPACE_CONFIG_FILENAME


def load_workspace_local_config(workspace_root: str | Path) -> dict[str, Any]:
    """Load workspace-local config, returning an empty dict when absent."""
    path = get_workspace_local_config_path(workspace_root)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {}
    return cast(dict[str, Any], data)


def save_workspace_local_config(workspace_root: str | Path, config: dict[str, Any]) -> None:
    """Persist workspace-local config atomically."""
    path = get_workspace_local_config_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=path.parent,
        delete=False,
        suffix=".tmp",
        encoding="utf-8",
    ) as tmp:
        json.dump(config, tmp, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.chmod(0o600)
    tmp_path.replace(path)


def get_workspace_last_used_provider(workspace_root: str | Path) -> str | None:
    """Return the workspace-local last-used provider, if present."""
    config = load_workspace_local_config(workspace_root)
    provider = config.get("last_used_provider")
    return provider if isinstance(provider, str) else None


def set_workspace_last_used_provider(workspace_root: str | Path, provider_id: str) -> None:
    """Persist the workspace-local last-used provider.

    Best-effort also appends ``.scc/`` to the effective Git exclude file so the
    local config stays untracked without mutating the repository's tracked
    ``.gitignore``.
    """
    config = load_workspace_local_config(workspace_root)
    config["last_used_provider"] = provider_id
    save_workspace_local_config(workspace_root, config)
    _ensure_workspace_local_config_excluded(Path(workspace_root))


def _ensure_workspace_local_config_excluded(workspace_root: Path) -> None:
    """Best-effort add ``.scc/`` to the effective Git exclude file."""
    try:
        exclude_result = subprocess.run(
            [
                "git",
                "-C",
                str(workspace_root),
                "rev-parse",
                "--git-path",
                "info/exclude",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return

    if exclude_result.returncode != 0:
        return

    exclude_path = Path(exclude_result.stdout.strip())
    if not exclude_path.is_absolute():
        exclude_path = workspace_root / exclude_path

    try:
        exclude_path.parent.mkdir(parents=True, exist_ok=True)
        if exclude_path.exists():
            existing = exclude_path.read_text(encoding="utf-8").splitlines()
        else:
            existing = []
        if _GIT_EXCLUDE_PATTERN not in existing:
            with open(exclude_path, "a", encoding="utf-8") as handle:
                handle.write(f"{_GIT_EXCLUDE_PATTERN}\n")
    except OSError:
        return
