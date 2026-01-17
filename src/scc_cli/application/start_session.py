"""Start session use case for launch workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scc_cli.application.compute_effective_config import EffectiveConfig, compute_effective_config
from scc_cli.application.sync_marketplace import (
    EffectiveConfigResolver,
    MarketplaceMaterializer,
    SyncError,
    SyncMarketplaceDependencies,
    SyncResult,
    sync_marketplace_settings,
)
from scc_cli.core.constants import AGENT_CONFIG_DIR, SANDBOX_IMAGE
from scc_cli.core.errors import WorkspaceNotFoundError
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.agent_runner import AgentRunner
from scc_cli.ports.clock import Clock
from scc_cli.ports.filesystem import Filesystem
from scc_cli.ports.git_client import GitClient
from scc_cli.ports.models import AgentSettings, MountSpec, SandboxHandle, SandboxSpec
from scc_cli.ports.remote_fetcher import RemoteFetcher
from scc_cli.ports.sandbox_runtime import SandboxRuntime
from scc_cli.services.workspace import resolve_launch_context


@dataclass(frozen=True)
class StartSessionDependencies:
    """Dependencies for the start session use case."""

    filesystem: Filesystem
    remote_fetcher: RemoteFetcher
    clock: Clock
    git_client: GitClient
    agent_runner: AgentRunner
    sandbox_runtime: SandboxRuntime
    resolve_effective_config: EffectiveConfigResolver
    materialize_marketplace: MarketplaceMaterializer


@dataclass(frozen=True)
class StartSessionRequest:
    """Input data for preparing a start session."""

    workspace_path: Path
    workspace_arg: str | None
    entry_dir: Path
    team: str | None
    session_name: str | None
    resume: bool
    fresh: bool
    offline: bool
    standalone: bool
    dry_run: bool
    allow_suspicious: bool
    org_config: dict[str, Any] | None
    org_config_url: str | None = None


@dataclass(frozen=True)
class StartSessionPlan:
    """Prepared data needed to launch a session."""

    resolver_result: ResolverResult
    workspace_path: Path
    team: str | None
    session_name: str | None
    resume: bool
    fresh: bool
    current_branch: str | None
    effective_config: EffectiveConfig | None
    sync_result: SyncResult | None
    sync_error_message: str | None
    agent_settings: AgentSettings | None
    sandbox_spec: SandboxSpec | None


def prepare_start_session(
    request: StartSessionRequest,
    *,
    dependencies: StartSessionDependencies,
) -> StartSessionPlan:
    """Prepare launch data and settings for a session.

    This resolves workspace context, computes config, syncs marketplace settings,
    and builds the sandbox specification.
    """
    resolver_result = _resolve_workspace_context(request)
    effective_config = _compute_effective_config(request)
    sync_result, sync_error_message = _sync_marketplace_settings(request, dependencies)
    agent_settings = _build_agent_settings(sync_result, dependencies.agent_runner)
    current_branch = _resolve_current_branch(request.workspace_path, dependencies.git_client)
    sandbox_spec = _build_sandbox_spec(
        request=request,
        resolver_result=resolver_result,
        effective_config=effective_config,
        agent_settings=agent_settings,
    )
    return StartSessionPlan(
        resolver_result=resolver_result,
        workspace_path=request.workspace_path,
        team=request.team,
        session_name=request.session_name,
        resume=request.resume,
        fresh=request.fresh,
        current_branch=current_branch,
        effective_config=effective_config,
        sync_result=sync_result,
        sync_error_message=sync_error_message,
        agent_settings=agent_settings,
        sandbox_spec=sandbox_spec,
    )


def start_session(
    plan: StartSessionPlan,
    *,
    dependencies: StartSessionDependencies,
) -> SandboxHandle:
    """Launch the sandbox runtime for a prepared session."""
    if plan.sandbox_spec is None:
        raise ValueError("Sandbox spec is required to start a session")
    return dependencies.sandbox_runtime.run(plan.sandbox_spec)


def _resolve_workspace_context(request: StartSessionRequest) -> ResolverResult:
    result = resolve_launch_context(
        request.entry_dir,
        request.workspace_arg,
        allow_suspicious=request.allow_suspicious,
    )
    if result is None:
        raise WorkspaceNotFoundError(path=str(request.workspace_path))
    return result


def _compute_effective_config(request: StartSessionRequest) -> EffectiveConfig | None:
    if request.org_config is None or request.team is None:
        return None
    return compute_effective_config(
        request.org_config,
        request.team,
        workspace_path=request.workspace_path,
    )


def _sync_marketplace_settings(
    request: StartSessionRequest,
    dependencies: StartSessionDependencies,
) -> tuple[SyncResult | None, str | None]:
    if request.dry_run or request.offline or request.standalone:
        return None, None
    if request.org_config is None or request.team is None:
        return None, None
    sync_dependencies = SyncMarketplaceDependencies(
        filesystem=dependencies.filesystem,
        remote_fetcher=dependencies.remote_fetcher,
        clock=dependencies.clock,
        resolve_effective_config=dependencies.resolve_effective_config,
        materialize_marketplace=dependencies.materialize_marketplace,
    )
    try:
        result = sync_marketplace_settings(
            project_dir=request.workspace_path,
            org_config_data=request.org_config,
            team_id=request.team,
            org_config_url=request.org_config_url,
            write_to_workspace=False,
            container_path_prefix=str(request.workspace_path),
            dependencies=sync_dependencies,
        )
    except SyncError as exc:
        return None, str(exc)
    return result, None


def _build_agent_settings(
    sync_result: SyncResult | None,
    agent_runner: AgentRunner,
) -> AgentSettings | None:
    if not sync_result or not sync_result.rendered_settings:
        return None
    settings_path = Path("/home/agent") / AGENT_CONFIG_DIR / "settings.json"
    return agent_runner.build_settings(sync_result.rendered_settings, path=settings_path)


def _resolve_current_branch(workspace_path: Path, git_client: GitClient) -> str | None:
    try:
        if not git_client.is_git_repo(workspace_path):
            return None
        return git_client.get_current_branch(workspace_path)
    except (OSError, ValueError):
        return None


def _build_sandbox_spec(
    *,
    request: StartSessionRequest,
    resolver_result: ResolverResult,
    effective_config: EffectiveConfig | None,
    agent_settings: AgentSettings | None,
) -> SandboxSpec | None:
    if request.dry_run:
        return None
    return SandboxSpec(
        image=SANDBOX_IMAGE,
        workspace_mount=MountSpec(
            source=resolver_result.mount_root,
            target=resolver_result.mount_root,
        ),
        workdir=Path(resolver_result.container_workdir),
        network_policy=effective_config.network_policy if effective_config else None,
        continue_session=request.resume,
        force_new=request.fresh,
        agent_settings=agent_settings,
        org_config=request.org_config,
    )
