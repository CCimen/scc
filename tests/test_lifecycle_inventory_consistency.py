"""Guardrail: verify lifecycle command surfaces use consistent SCC inventory sources.

Active user-facing command surfaces (list, stop, dashboard) must use the
label-based ``list_scc_containers()`` / ``list_running_scc_containers()``
inventory, not the image-based ``_list_all_sandbox_containers()`` or
``list_running_sandboxes()`` which include non-SCC Docker Desktop containers.

``prune_cmd`` and ``cache_cleanup`` intentionally use the broader image-based
inventory because cleanup should catch orphaned Desktop containers too.

This test prevents regression to the wrong inventory source.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "scc_cli"

# Label-based SCC inventory functions (the correct source for active commands)
LABEL_INVENTORY = {"list_scc_containers", "list_running_scc_containers"}

# Image-based broader inventory (allowed only in cleanup/prune)
IMAGE_INVENTORY = {"_list_all_sandbox_containers", "list_running_sandboxes"}


def _collect_called_names(source: str) -> set[str]:
    """Return all Name and Attribute nodes that look like function calls."""
    names: set[str] = set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
    return names


class TestListCmdUsesLabelInventory:
    """scc list must use list_scc_containers (label-based)."""

    def test_list_cmd_calls_label_inventory(self) -> None:
        source = (SRC / "commands" / "worktree" / "container_commands.py").read_text()
        # Extract just the list_cmd function body
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "list_cmd":
                func_source = ast.get_source_segment(source, node)
                assert func_source is not None
                names = _collect_called_names(func_source)
                assert names & LABEL_INVENTORY, (
                    "list_cmd should call list_scc_containers or list_running_scc_containers"
                )
                assert not (names & IMAGE_INVENTORY), (
                    "list_cmd must not use image-based inventory (_list_all_sandbox_containers)"
                )
                return
        raise AssertionError("list_cmd function not found in container_commands.py")


class TestStopCmdUsesLabelInventory:
    """scc stop must use list_running_scc_containers (label-based)."""

    def test_stop_cmd_calls_label_inventory(self) -> None:
        source = (SRC / "commands" / "worktree" / "container_commands.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "stop_cmd":
                func_source = ast.get_source_segment(source, node)
                assert func_source is not None
                names = _collect_called_names(func_source)
                assert names & LABEL_INVENTORY, (
                    "stop_cmd should call list_scc_containers or list_running_scc_containers"
                )
                assert not (names & IMAGE_INVENTORY), "stop_cmd must not use image-based inventory"
                return
        raise AssertionError("stop_cmd function not found in container_commands.py")


class TestDashboardUsesLabelInventory:
    """Dashboard container loaders must use list_scc_containers."""

    def test_dashboard_status_loader(self) -> None:
        source = (SRC / "application" / "dashboard_loaders.py").read_text()
        names = _collect_called_names(source)
        assert "list_scc_containers" in names, "dashboard_loaders must call list_scc_containers"
        assert not (names & IMAGE_INVENTORY), "dashboard_loaders must not use image-based inventory"


class TestPickerUsesLabelInventory:
    """UI picker for containers must use list_scc_containers."""

    def test_picker_calls_label_inventory(self) -> None:
        source = (SRC / "ui" / "picker.py").read_text()
        names = _collect_called_names(source)
        assert "list_scc_containers" in names, (
            "picker.py must call list_scc_containers for container selection"
        )
        assert not (names & IMAGE_INVENTORY), "picker.py must not use image-based inventory"


class TestPruneCmdUsesImageInventory:
    """prune_cmd intentionally uses broader image-based inventory for cleanup."""

    def test_prune_cmd_uses_image_inventory(self) -> None:
        source = (SRC / "commands" / "worktree" / "container_commands.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "prune_cmd":
                func_source = ast.get_source_segment(source, node)
                assert func_source is not None
                names = _collect_called_names(func_source)
                assert "_list_all_sandbox_containers" in names, (
                    "prune_cmd should use _list_all_sandbox_containers for broad cleanup"
                )
                return
        raise AssertionError("prune_cmd function not found in container_commands.py")


class TestLabelFilterExcludesNonSCC:
    """list_scc_containers uses label filter that excludes non-SCC containers."""

    def test_label_filter_uses_scc_managed(self) -> None:
        source = (SRC / "docker" / "core.py").read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "list_scc_containers":
                func_source = ast.get_source_segment(source, node)
                assert func_source is not None
                assert "scc" in func_source.lower() and "managed" in func_source.lower(), (
                    "list_scc_containers must filter by scc.managed label"
                )
                return
        raise AssertionError("list_scc_containers function not found in docker/core.py")
