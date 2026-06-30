from __future__ import annotations

from pathlib import Path

import pytest

from scc_cli.core.runtime_mounts import WORKSPACE_PATH_MAP_ENV, resolve_runtime_mount_source


def test_runtime_mount_source_defaults_to_mount_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(WORKSPACE_PATH_MAP_ENV, raising=False)
    mount_root = Path("/workspaces/app")

    assert resolve_runtime_mount_source(mount_root, None) == mount_root


def test_runtime_mount_source_maps_exact_devcontainer_path() -> None:
    mount_root = Path("/workspaces/app")

    assert resolve_runtime_mount_source(mount_root, "/workspaces/app:/Users/dev/app") == Path(
        "/Users/dev/app"
    )


def test_runtime_mount_source_maps_nested_mount_path() -> None:
    mount_root = Path("/workspaces/app/worktrees/feature-a")

    assert resolve_runtime_mount_source(mount_root, "/workspaces/app:/Users/dev/app") == Path(
        "/Users/dev/app/worktrees/feature-a"
    )


@pytest.mark.parametrize(
    "path_map",
    [
        "",
        "/workspaces/app",
        ":/Users/dev/app",
        "/workspaces/app:",
        "workspaces/app:/Users/dev/app",
        "/workspaces/app:Users/dev/app",
        "/workspaces/app/..:/Users/dev/app",
        "/workspaces/app:/Users/dev/app/..",
    ],
)
def test_runtime_mount_source_ignores_invalid_path_maps(path_map: str) -> None:
    mount_root = Path("/workspaces/app")

    assert resolve_runtime_mount_source(mount_root, path_map) == mount_root


def test_runtime_mount_source_ignores_non_matching_path_map() -> None:
    mount_root = Path("/workspace/app")

    assert resolve_runtime_mount_source(mount_root, "/workspaces/app:/Users/dev/app") == mount_root


def test_runtime_mount_source_does_not_map_parent_escape() -> None:
    mount_root = Path("/workspaces/app/../other")

    assert resolve_runtime_mount_source(mount_root, "/workspaces/app:/Users/dev/app") == mount_root
