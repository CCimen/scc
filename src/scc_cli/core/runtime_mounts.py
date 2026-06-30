"""Runtime mount path helpers."""

from __future__ import annotations

import os
from pathlib import Path

WORKSPACE_PATH_MAP_ENV = "SCC_WORKSPACE_PATH_MAP"


def _has_parent_reference(path: Path) -> bool:
    return ".." in path.parts


def _normalize_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def parse_workspace_path_map(path_map: str | None) -> tuple[Path, Path] | None:
    """Parse ``SCC_WORKSPACE_PATH_MAP`` into container and host prefixes."""
    if not path_map:
        return None

    container_prefix_raw, separator, host_prefix_raw = path_map.partition(":")
    if separator != ":" or not container_prefix_raw or not host_prefix_raw:
        return None

    container_prefix = Path(container_prefix_raw).expanduser()
    host_prefix = Path(host_prefix_raw).expanduser()
    if not container_prefix.is_absolute() or not host_prefix.is_absolute():
        return None
    if _has_parent_reference(container_prefix) or _has_parent_reference(host_prefix):
        return None

    return _normalize_path(container_prefix), _normalize_path(host_prefix)


def resolve_runtime_mount_source(mount_root: Path, path_map: str | None = None) -> Path:
    """Return the host-visible mount source for the runtime daemon."""
    configured_map = os.environ.get(WORKSPACE_PATH_MAP_ENV) if path_map is None else path_map
    parsed_map = parse_workspace_path_map(configured_map)
    if parsed_map is None:
        return mount_root

    container_prefix, host_prefix = parsed_map
    normalized_mount_root = _normalize_path(mount_root)
    try:
        relative_mount = normalized_mount_root.relative_to(container_prefix)
    except ValueError:
        return mount_root

    return host_prefix / relative_mount
