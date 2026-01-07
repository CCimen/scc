"""Tests for personal profile export/import sync."""

import json
from pathlib import Path

from scc_cli import config as config_module
from scc_cli.core import personal_profiles


def _write_profile(workspace: Path, settings: dict, mcp: dict) -> None:
    personal_profiles.save_personal_profile(workspace, settings, mcp)


def _read_index(repo_path: Path) -> dict:
    index_path = personal_profiles.get_repo_index_path(repo_path)
    return json.loads(index_path.read_text())


def test_export_and_import_profiles(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)

    workspace_a = tmp_path / "ws-a"
    workspace_b = tmp_path / "ws-b"
    workspace_a.mkdir()
    workspace_b.mkdir()

    _write_profile(workspace_a, {"enabledPlugins": {"a@b": True}}, {})
    _write_profile(workspace_b, {"enabledPlugins": {"c@d": True}}, {})

    repo_path = tmp_path / "profiles-repo"
    result = personal_profiles.export_profiles_to_repo(repo_path)

    assert result.exported == 2
    index = _read_index(repo_path)
    assert "profiles" in index
    assert len(index["profiles"]) == 2

    # New config dir to import into
    new_config = tmp_path / "config-import"
    new_config.mkdir()
    monkeypatch.setattr(config_module, "CONFIG_DIR", new_config)

    import_result = personal_profiles.import_profiles_from_repo(repo_path)
    assert import_result.imported == 2

    saved = list(personal_profiles.list_personal_profiles())
    assert len(saved) == 2


def test_import_scans_missing_index(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)

    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_profile(workspace, {"enabledPlugins": {"x@y": True}}, {})

    repo_path = tmp_path / "repo"
    personal_profiles.export_profiles_to_repo(repo_path)

    # Remove index to force scan
    personal_profiles.get_repo_index_path(repo_path).unlink()

    new_config = tmp_path / "config-import"
    new_config.mkdir()
    monkeypatch.setattr(config_module, "CONFIG_DIR", new_config)

    result = personal_profiles.import_profiles_from_repo(repo_path)
    assert result.imported == 1


def test_import_preview_does_not_write(monkeypatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setattr(config_module, "CONFIG_DIR", config_dir)

    workspace = tmp_path / "ws"
    workspace.mkdir()
    _write_profile(workspace, {"enabledPlugins": {"x@y": True}}, {})

    repo_path = tmp_path / "repo"
    personal_profiles.export_profiles_to_repo(repo_path)

    new_config = tmp_path / "config-import"
    new_config.mkdir()
    monkeypatch.setattr(config_module, "CONFIG_DIR", new_config)

    preview = personal_profiles.import_profiles_from_repo(repo_path, dry_run=True)
    assert preview.imported == 1
    assert list(personal_profiles.list_personal_profiles()) == []
