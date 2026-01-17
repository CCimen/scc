from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from scc_cli.application.start_session import (
    StartSessionDependencies,
    StartSessionPlan,
    StartSessionRequest,
    prepare_start_session,
    start_session,
)
from scc_cli.application.sync_marketplace import SyncError, SyncResult
from scc_cli.application.workspace import WorkspaceContext
from scc_cli.core.constants import AGENT_CONFIG_DIR, SANDBOX_IMAGE
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.models import MountSpec, SandboxSpec
from tests.fakes.fake_agent_runner import FakeAgentRunner
from tests.fakes.fake_sandbox_runtime import FakeSandboxRuntime


class FakeGitClient:
    def __init__(self, branch: str | None = "main", is_repo: bool = True) -> None:
        self._branch = branch
        self._is_repo = is_repo

    def check_available(self) -> None:
        return None

    def check_installed(self) -> bool:
        return True

    def get_version(self) -> str | None:
        return "fake-git"

    def is_git_repo(self, path: Path) -> bool:
        return self._is_repo

    def init_repo(self, path: Path) -> bool:
        return True

    def create_empty_initial_commit(self, path: Path) -> tuple[bool, str | None]:
        return True, None

    def detect_workspace_root(self, start_dir: Path) -> tuple[Path | None, Path]:
        return None, start_dir

    def get_current_branch(self, path: Path) -> str | None:
        return self._branch


def _build_resolver_result(workspace_path: Path) -> ResolverResult:
    resolved = workspace_path.resolve()
    return ResolverResult(
        workspace_root=resolved,
        entry_dir=resolved,
        mount_root=resolved,
        container_workdir=str(resolved),
        is_auto_detected=False,
        is_suspicious=False,
        reason="test",
    )


def _build_dependencies(git_client: FakeGitClient) -> StartSessionDependencies:
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=git_client,
        agent_runner=FakeAgentRunner(),
        sandbox_runtime=FakeSandboxRuntime(),
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
    )


def test_prepare_start_session_builds_plan_with_sync_result(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    request = StartSessionRequest(
        workspace_path=workspace_path,
        workspace_arg=str(workspace_path),
        entry_dir=workspace_path,
        team="alpha",
        session_name="session-1",
        resume=False,
        fresh=False,
        offline=False,
        standalone=False,
        dry_run=False,
        allow_suspicious=False,
        org_config={
            "defaults": {"network_policy": "restricted"},
            "profiles": {"alpha": {}},
        },
    )
    sync_result = SyncResult(success=True, rendered_settings={"plugins": []})
    resolver_result = _build_resolver_result(workspace_path)
    dependencies = _build_dependencies(FakeGitClient(branch="main"))

    with (
        patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ),
        patch(
            "scc_cli.application.start_session.sync_marketplace_settings",
            return_value=sync_result,
        ) as sync_mock,
    ):
        plan = prepare_start_session(request, dependencies=dependencies)

    sync_mock.assert_called_once()
    assert sync_mock.call_args.kwargs["write_to_workspace"] is False
    assert sync_mock.call_args.kwargs["container_path_prefix"] == str(workspace_path)
    assert plan.sync_result is sync_result
    assert plan.sync_error_message is None
    assert plan.current_branch == "main"
    assert plan.agent_settings is not None
    assert plan.agent_settings.content == {"plugins": []}
    assert plan.agent_settings.path == Path("/home/agent") / AGENT_CONFIG_DIR / "settings.json"
    assert plan.sandbox_spec is not None
    assert plan.sandbox_spec.image == SANDBOX_IMAGE
    assert plan.sandbox_spec.network_policy == "restricted"


def test_prepare_start_session_captures_sync_error(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    request = StartSessionRequest(
        workspace_path=workspace_path,
        workspace_arg=str(workspace_path),
        entry_dir=workspace_path,
        team="alpha",
        session_name=None,
        resume=False,
        fresh=False,
        offline=False,
        standalone=False,
        dry_run=False,
        allow_suspicious=False,
        org_config={
            "defaults": {},
            "profiles": {"alpha": {}},
        },
    )
    resolver_result = _build_resolver_result(workspace_path)
    dependencies = _build_dependencies(FakeGitClient())

    with (
        patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ),
        patch(
            "scc_cli.application.start_session.sync_marketplace_settings",
            side_effect=SyncError("sync failed"),
        ),
    ):
        plan = prepare_start_session(request, dependencies=dependencies)

    assert plan.sync_result is None
    assert plan.sync_error_message == "sync failed"
    assert plan.agent_settings is None
    assert plan.sandbox_spec is not None


def test_start_session_runs_sandbox_runtime(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    resolver_result = _build_resolver_result(workspace_path)
    sandbox_spec = SandboxSpec(
        image="test-image",
        workspace_mount=MountSpec(source=workspace_path, target=workspace_path),
        workdir=workspace_path,
    )
    plan = StartSessionPlan(
        resolver_result=resolver_result,
        workspace_path=workspace_path,
        team=None,
        session_name=None,
        resume=False,
        fresh=False,
        current_branch=None,
        effective_config=None,
        sync_result=None,
        sync_error_message=None,
        agent_settings=None,
        sandbox_spec=sandbox_spec,
    )
    runtime = FakeSandboxRuntime()
    dependencies = StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=FakeGitClient(),
        agent_runner=FakeAgentRunner(),
        sandbox_runtime=runtime,
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
    )

    handle = start_session(plan, dependencies=dependencies)

    assert handle.sandbox_id == "sandbox-1"
