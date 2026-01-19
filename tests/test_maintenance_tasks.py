from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from scc_cli import config, contexts, sessions
from scc_cli.docker.core import ContainerInfo
from scc_cli.maintenance.cache_cleanup import (
    cleanup_expired_exceptions,
    clear_cache,
    clear_contexts,
    prune_containers,
)
from scc_cli.maintenance.migrations import (
    factory_reset,
    reset_config,
    reset_exceptions,
)
from scc_cli.maintenance.repair_sessions import (
    delete_all_sessions,
    prune_sessions,
)
from scc_cli.maintenance.types import ResetResult, RiskTier
from scc_cli.models.exceptions import AllowTargets, Exception, ExceptionFile
from scc_cli.ports.session_models import SessionRecord
from scc_cli.stores.exception_store import RepoStore, UserStore


def _make_exception(exc_id: str, expires_at: datetime) -> Exception:
    return Exception(
        id=exc_id,
        created_at=(expires_at - timedelta(days=2)).isoformat(),
        expires_at=expires_at.isoformat(),
        reason="test",
        scope="local",
        allow=AllowTargets(plugins=["scc-test"]),
    )


def _write_exceptions(store: UserStore | RepoStore, exceptions: list[Exception]) -> None:
    store.write(ExceptionFile(exceptions=exceptions))


def test_clear_cache_dry_run_keeps_files(temp_config_dir: Path) -> None:
    cache_dir = config.CACHE_DIR
    cache_file = cache_dir / "cache.txt"
    cache_file.write_text("data")

    result = clear_cache(dry_run=True)

    assert result.removed_count == 1
    assert cache_file.exists()


def test_clear_cache_removes_files(temp_config_dir: Path) -> None:
    cache_dir = config.CACHE_DIR
    cache_file = cache_dir / "cache.txt"
    cache_file.write_text("data")

    result = clear_cache(dry_run=False)

    assert result.success is True
    assert result.removed_count == 1
    assert cache_dir.exists()
    assert not cache_file.exists()


def test_cleanup_expired_exceptions_prunes(temp_config_dir: Path) -> None:
    now = datetime.now(timezone.utc)
    expired = _make_exception("expired", now - timedelta(days=1))
    active = _make_exception("active", now + timedelta(days=1))
    user_store = UserStore()
    _write_exceptions(user_store, [expired, active])

    result = cleanup_expired_exceptions(dry_run=False)

    assert result.removed_count == 1
    remaining = user_store.read()
    assert [exc.id for exc in remaining.exceptions] == ["active"]


def test_clear_contexts_clears_cache(temp_config_dir: Path, tmp_path: Path) -> None:
    workspace = tmp_path / "repo"
    context = contexts.WorkContext(
        team=None,
        repo_root=workspace,
        worktree_path=workspace,
        worktree_name="main",
    )
    contexts.record_context(context)

    result = clear_contexts(dry_run=False)

    assert result.removed_count == 1
    assert contexts.load_recent_contexts(limit=10) == []


def test_prune_containers_removes_stopped(monkeypatch) -> None:
    containers = [
        ContainerInfo(id="abc", name="scc-one", status="Exited"),
        ContainerInfo(id="def", name="scc-two", status="running"),
        ContainerInfo(id="", name="scc-three", status="Stopped"),
    ]
    removed: list[str] = []

    from scc_cli import docker

    monkeypatch.setattr(docker, "_list_all_sandbox_containers", lambda: containers)

    def _fake_remove(container_id: str) -> None:
        removed.append(container_id)

    monkeypatch.setattr(docker, "remove_container", _fake_remove)

    result = prune_containers(dry_run=False)

    assert result.removed_count == 2
    assert set(removed) == {"abc", "scc-three"}


def test_prune_sessions_removes_old_entries(temp_config_dir: Path) -> None:
    now = datetime.now(timezone.utc)
    store = sessions.get_session_store()
    store.save_sessions(
        [
            SessionRecord(workspace="one", last_used=(now - timedelta(days=1)).isoformat()),
            SessionRecord(workspace="two", last_used=(now - timedelta(days=60)).isoformat()),
            SessionRecord(workspace="three", last_used=(now - timedelta(days=45)).isoformat()),
        ]
    )

    result = prune_sessions(older_than_days=30, keep_n=1, dry_run=False)

    assert result.removed_count == 2
    remaining = store.load_sessions()
    assert [session.workspace for session in remaining] == ["one"]


def test_delete_all_sessions_creates_backup(temp_config_dir: Path) -> None:
    store = sessions.get_session_store()
    store.save_sessions(
        [
            SessionRecord(workspace="one", last_used="2024-01-01T00:00:00+00:00"),
            SessionRecord(workspace="two", last_used="2024-01-02T00:00:00+00:00"),
        ]
    )

    result = delete_all_sessions(dry_run=False, create_backup=True)

    assert result.removed_count == 2
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert store.load_sessions() == []


def test_reset_exceptions_resets_user_and_repo(temp_config_dir: Path, tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    user_store = UserStore()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    repo_store = RepoStore(repo_root)

    _write_exceptions(
        user_store,
        [_make_exception("user-1", now + timedelta(days=1))],
    )
    _write_exceptions(
        repo_store,
        [_make_exception("repo-1", now + timedelta(days=2))],
    )

    result = reset_exceptions(scope="all", repo_root=repo_root, create_backup=True)

    assert result.removed_count == 2
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert not user_store.path.exists()
    assert not repo_store.path.exists()


def test_reset_config_creates_backup(temp_config_dir: Path) -> None:
    config.CONFIG_FILE.write_text('{"profile": "dev"}')

    result = reset_config(dry_run=False, create_backup=True)

    assert result.success is True
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert not config.CONFIG_FILE.exists()


def test_factory_reset_stops_on_failure(monkeypatch) -> None:
    def _make_result(action_id: str, success: bool = True) -> ResetResult:
        return ResetResult(
            success=success,
            action_id=action_id,
            risk_tier=RiskTier.FACTORY_RESET,
            message="ok",
        )

    monkeypatch.setattr(
        "scc_cli.maintenance.migrations.reset_config",
        lambda **_: _make_result("reset_config"),
    )
    monkeypatch.setattr(
        "scc_cli.maintenance.migrations.delete_all_sessions",
        lambda **_: _make_result("delete_all_sessions", success=False),
    )
    monkeypatch.setattr(
        "scc_cli.maintenance.migrations.reset_exceptions",
        lambda **_: _make_result("reset_exceptions"),
    )
    monkeypatch.setattr(
        "scc_cli.maintenance.migrations.clear_contexts",
        lambda **_: _make_result("clear_contexts"),
    )
    monkeypatch.setattr(
        "scc_cli.maintenance.migrations.clear_cache",
        lambda **_: _make_result("clear_cache"),
    )
    monkeypatch.setattr(
        "scc_cli.maintenance.migrations.prune_containers",
        lambda **_: _make_result("prune_containers"),
    )

    results = factory_reset()

    assert [result.action_id for result in results] == ["reset_config", "delete_all_sessions"]

    results = factory_reset(continue_on_error=True)

    assert [result.action_id for result in results] == [
        "reset_config",
        "delete_all_sessions",
        "reset_exceptions",
        "clear_contexts",
        "clear_cache",
        "prune_containers",
    ]
