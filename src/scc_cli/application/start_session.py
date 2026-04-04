"""Start session use case for launch workflow."""

from __future__ import annotations

import logging
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
from scc_cli.application.workspace import ResolveWorkspaceRequest, resolve_workspace
from scc_cli.core.bundle_resolver import BundleResolutionResult, resolve_render_plan
from scc_cli.core.constants import AGENT_CONFIG_DIR, SANDBOX_IMAGE
from scc_cli.core.contracts import AgentLaunchSpec, RenderArtifactsResult, RuntimeInfo
from scc_cli.core.destination_registry import resolve_destination_sets
from scc_cli.core.errors import RendererError, WorkspaceNotFoundError
from scc_cli.core.image_contracts import SCC_CLAUDE_IMAGE_REF
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.agent_provider import AgentProvider
from scc_cli.ports.agent_runner import AgentRunner
from scc_cli.ports.audit_event_sink import AuditEventSink
from scc_cli.ports.clock import Clock
from scc_cli.ports.config_models import NormalizedOrgConfig
from scc_cli.ports.filesystem import Filesystem
from scc_cli.ports.git_client import GitClient
from scc_cli.ports.models import AgentSettings, MountSpec, SandboxHandle, SandboxSpec
from scc_cli.ports.remote_fetcher import RemoteFetcher
from scc_cli.ports.sandbox_runtime import SandboxRuntime

logger = logging.getLogger(__name__)


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
    agent_provider: AgentProvider | None = None
    audit_event_sink: AuditEventSink | None = None
    runtime_info: RuntimeInfo | None = None


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
    org_config: NormalizedOrgConfig | None
    raw_org_config: dict[str, Any] | None = None
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
    agent_launch_spec: AgentLaunchSpec | None = None
    bundle_render_results: tuple[RenderArtifactsResult, ...] = ()
    bundle_render_error: str | None = None


def prepare_start_session(
    request: StartSessionRequest,
    *,
    dependencies: StartSessionDependencies,
) -> StartSessionPlan:
    """Prepare launch data and settings for a session.

    This resolves workspace context, computes config, syncs marketplace settings,
    resolves bundle render plans, renders provider-native artifacts, and builds
    the sandbox specification.
    """
    resolver_result = _resolve_workspace_context(request)
    effective_config = _compute_effective_config(request)
    sync_result, sync_error_message = sync_marketplace_settings_for_start(request, dependencies)
    agent_settings = _build_agent_settings(
        sync_result,
        dependencies.agent_runner,
        effective_config=effective_config,
    )

    # ── Bundle pipeline: resolve plans → render artifacts ─────────────────
    bundle_render_results, bundle_render_error = _render_bundle_artifacts(
        request=request,
        workspace=request.workspace_path,
        dependencies=dependencies,
    )

    current_branch = _resolve_current_branch(request.workspace_path, dependencies.git_client)
    sandbox_spec = _build_sandbox_spec(
        request=request,
        resolver_result=resolver_result,
        effective_config=effective_config,
        agent_settings=agent_settings,
        runtime_info=dependencies.runtime_info,
        agent_provider=dependencies.agent_provider,
    )
    agent_launch_spec = _build_agent_launch_spec(
        request=request,
        agent_settings=agent_settings,
        dependencies=dependencies,
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
        agent_launch_spec=agent_launch_spec,
        bundle_render_results=bundle_render_results,
        bundle_render_error=bundle_render_error,
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
    context = resolve_workspace(
        ResolveWorkspaceRequest(
            cwd=request.entry_dir,
            workspace_arg=request.workspace_arg,
            allow_suspicious=request.allow_suspicious,
        )
    )
    if context is None:
        raise WorkspaceNotFoundError(path=str(request.workspace_path))
    return context.resolver_result


def _compute_effective_config(request: StartSessionRequest) -> EffectiveConfig | None:
    if request.org_config is None or request.team is None:
        return None
    return compute_effective_config(
        request.org_config,
        request.team,
        workspace_path=request.workspace_path,
    )


def sync_marketplace_settings_for_start(
    request: StartSessionRequest,
    dependencies: StartSessionDependencies,
) -> tuple[SyncResult | None, str | None]:
    """Sync marketplace settings for a start session.

    **Transitional:** This function predates the governed-artifact bundle
    pipeline (M005).  It syncs legacy marketplace plugin/MCP definitions
    that are not yet expressed as governed artifacts.  Once all team
    config surfaces are migrated to the bundle pipeline
    (``_render_bundle_artifacts``), this function and its call sites can
    be removed.  Until then, both paths run: marketplace sync first,
    then bundle rendering, with the bundle pipeline as the canonical path.

    Invariants:
        - Skips syncing in dry-run, offline, or standalone modes.
        - Uses the same sync path as start session preparation.

    Args:
        request: Start session request data.
        dependencies: Dependencies used to perform the sync.

    Returns:
        Tuple of sync result and optional error message.
    """
    if request.dry_run or request.offline or request.standalone:
        return None, None
    if request.raw_org_config is None or request.team is None:
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
            org_config_data=request.raw_org_config,
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
    *,
    effective_config: EffectiveConfig | None,
) -> AgentSettings | None:
    settings: dict[str, Any] | None = None
    if sync_result and sync_result.rendered_settings:
        settings = dict(sync_result.rendered_settings)

    if effective_config:
        from scc_cli.bootstrap import merge_mcp_servers

        settings = merge_mcp_servers(settings, effective_config)

    if not settings:
        return None

    settings_path = Path("/home/agent") / AGENT_CONFIG_DIR / "settings.json"
    return agent_runner.build_settings(settings, path=settings_path)


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
    runtime_info: RuntimeInfo | None = None,
    agent_provider: AgentProvider | None = None,
) -> SandboxSpec | None:
    if request.dry_run:
        return None

    # Route image: SCC-owned image for OCI backend, Docker Desktop template otherwise.
    if runtime_info is not None and runtime_info.preferred_backend == "oci":
        image = SCC_CLAUDE_IMAGE_REF
    else:
        image = SANDBOX_IMAGE

    # Resolve provider destination sets for OCI backend.
    from scc_cli.core.contracts import DestinationSet

    destination_sets: tuple[DestinationSet, ...] = ()
    if (
        agent_provider is not None
        and runtime_info is not None
        and runtime_info.preferred_backend == "oci"
    ):
        profile = agent_provider.capability_profile()
        if profile.required_destination_set:
            destination_sets = resolve_destination_sets(
                (profile.required_destination_set,)
            )

    return SandboxSpec(
        image=image,
        workspace_mount=MountSpec(
            source=resolver_result.mount_root,
            target=resolver_result.mount_root,
        ),
        workdir=Path(resolver_result.container_workdir),
        network_policy=effective_config.network_policy if effective_config else None,
        destination_sets=destination_sets,
        continue_session=request.resume,
        force_new=request.fresh,
        agent_settings=agent_settings,
        org_config=request.raw_org_config,
    )


def _render_bundle_artifacts(
    *,
    request: StartSessionRequest,
    workspace: Path,
    dependencies: StartSessionDependencies,
) -> tuple[tuple[RenderArtifactsResult, ...], str | None]:
    """Resolve bundle render plans and render provider-native artifacts.

    Skips bundle resolution when preconditions aren't met (no org config,
    no team, no provider, or dry-run/offline/standalone modes).

    In fail-closed mode, RendererError propagates as a captured error message
    on the StartSessionPlan so the presentation layer can display diagnostics.

    Returns:
        Tuple of (render_results, error_message).  On success error_message
        is None.  On failure render_results is empty.
    """
    # Gate: skip bundle pipeline when prerequisites are absent
    if request.dry_run or request.offline or request.standalone:
        return (), None
    if request.org_config is None or request.team is None:
        return (), None
    provider = dependencies.agent_provider
    if provider is None:
        return (), None

    provider_id = provider.capability_profile().provider_id

    # 1. Resolve render plans from org config + team + provider
    try:
        resolution: BundleResolutionResult = resolve_render_plan(
            org_config=request.org_config,
            team_name=request.team,
            provider=provider_id,
            fail_closed=True,
        )
    except (ValueError, RendererError) as exc:
        logger.warning("Bundle resolution failed: %s", exc)
        return (), str(exc)

    if not resolution.plans:
        if resolution.diagnostics:
            diag_msgs = [d.reason for d in resolution.diagnostics]
            logger.info("Bundle resolution produced no plans: %s", diag_msgs)
        return (), None

    # Log diagnostics from resolution
    for diag in resolution.diagnostics:
        logger.info("Bundle resolution diagnostic: %s — %s", diag.artifact_name, diag.reason)

    # 2. Render each plan through the provider adapter
    all_results: list[RenderArtifactsResult] = []
    for plan in resolution.plans:
        if not plan.effective_artifacts and not plan.bindings:
            logger.info(
                "Skipping empty render plan for bundle '%s' (no effective artifacts)",
                plan.bundle_id,
            )
            continue
        try:
            result = provider.render_artifacts(plan, workspace)
        except RendererError as exc:
            # Fail-closed: capture and return the error
            logger.error(
                "Artifact rendering failed for bundle '%s': %s",
                plan.bundle_id,
                exc,
            )
            return (), str(exc)

        all_results.append(result)

        # 3. Log/audit rendered artifacts
        for path in result.rendered_paths:
            logger.info("Rendered artifact: %s", path)
        for warning in result.warnings:
            logger.warning("Renderer warning: %s", warning)
        for skipped in result.skipped_artifacts:
            logger.info("Skipped artifact: %s", skipped)

    return tuple(all_results), None


def _build_agent_launch_spec(
    *,
    request: StartSessionRequest,
    agent_settings: AgentSettings | None,
    dependencies: StartSessionDependencies,
) -> AgentLaunchSpec | None:
    """Delegate launch spec construction to the provider adapter.

    Returns None when no provider is wired (backward compat) or in dry-run mode.
    The provider resolves its own argv, env, and artifact paths from the settings
    artifact already built by the sync/build_agent_settings path.
    """
    if request.dry_run:
        return None
    provider = dependencies.agent_provider
    if provider is None:
        return None
    settings_path = agent_settings.path if agent_settings is not None else None
    config: dict[str, Any] = {}
    if agent_settings is not None:
        config = dict(agent_settings.content)
    return provider.prepare_launch(
        config=config,
        workspace=request.workspace_path,
        settings_path=settings_path,
    )
