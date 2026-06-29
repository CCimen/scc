"""Fixtures for hermetic CLI end-to-end tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class E2EConfigPaths:
    config_dir: Path
    config_file: Path
    sessions_file: Path
    cache_dir: Path
    audit_dir: Path
    launch_audit_file: Path
    launch_audit_lock_file: Path


@pytest.fixture
def e2e_config_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> E2EConfigPaths:
    import scc_cli.config as config_module
    import scc_cli.remote as remote_module

    config_dir = tmp_path / "home" / ".config" / "scc"
    cache_dir = tmp_path / "home" / ".cache" / "scc"
    audit_dir = config_dir / "audit"
    paths = E2EConfigPaths(
        config_dir=config_dir,
        config_file=config_dir / "config.json",
        sessions_file=config_dir / "sessions.json",
        cache_dir=cache_dir,
        audit_dir=audit_dir,
        launch_audit_file=audit_dir / "launch-events.jsonl",
        launch_audit_lock_file=audit_dir / "launch-events.lock",
    )

    monkeypatch.setattr(config_module, "CONFIG_DIR", paths.config_dir)
    monkeypatch.setattr(config_module, "CONFIG_FILE", paths.config_file)
    monkeypatch.setattr(config_module, "SESSIONS_FILE", paths.sessions_file)
    monkeypatch.setattr(config_module, "CACHE_DIR", paths.cache_dir)
    monkeypatch.setattr(config_module, "AUDIT_DIR", paths.audit_dir)
    monkeypatch.setattr(config_module, "LAUNCH_AUDIT_FILE", paths.launch_audit_file)
    monkeypatch.setattr(
        config_module,
        "LAUNCH_AUDIT_LOCK_FILE",
        paths.launch_audit_lock_file,
    )
    monkeypatch.setattr(remote_module, "CACHE_DIR", paths.cache_dir)

    return paths
