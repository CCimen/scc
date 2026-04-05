from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.application.compute_effective_config import EffectiveConfig, MCPServer
from scc_cli.application.start_session import _DOCKER_DESKTOP_CLAUDE_IMAGE as SANDBOX_IMAGE
from scc_cli.application.start_session import (
    StartSessionDependencies,
    StartSessionPlan,
    StartSessionRequest,
    prepare_start_session,
    start_session,
)
from scc_cli.application.sync_marketplace import SyncError, SyncResult
from scc_cli.application.workspace import WorkspaceContext
from scc_cli.core.contracts import AgentLaunchSpec, RenderArtifactsResult, RuntimeInfo
from scc_cli.core.errors import InvalidProviderError, MaterializationError
from scc_cli.core.governed_artifacts import (
    ArtifactBundle,
    ArtifactInstallIntent,
    ArtifactKind,
    ArtifactRenderPlan,
    GovernedArtifact,
    ProviderArtifactBinding,
)
from scc_cli.core.image_contracts import SCC_CLAUDE_IMAGE_REF, SCC_CODEX_IMAGE_REF
from scc_cli.core.workspace import ResolverResult
from scc_cli.ports.config_models import GovernedArtifactsCatalog, NormalizedOrgConfig
from scc_cli.ports.models import MountSpec, SandboxSpec
from tests.fakes.fake_agent_provider import FakeAgentProvider
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
        agent_provider=FakeAgentProvider(),
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
        org_config=NormalizedOrgConfig.from_dict({
            "defaults": {"network_policy": "restricted"},
            "profiles": {"alpha": {}},
        }),
        raw_org_config={
            "defaults": {"network_policy": "restricted"},
            "profiles": {"alpha": {}},
        },
        provider_id="claude",
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
    import json as _json

    parsed = _json.loads(plan.agent_settings.rendered_bytes)
    assert parsed == {"plugins": []}
    assert plan.agent_settings.path == Path("/home/agent") / ".claude" / "settings.json"
    assert plan.sandbox_spec is not None
    assert plan.sandbox_spec.image == SANDBOX_IMAGE
    assert plan.sandbox_spec.network_policy == "restricted"


def test_prepare_start_session_captures_sync_error(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    _raw = {
        "defaults": {},
        "profiles": {"alpha": {}},
    }
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
        org_config=NormalizedOrgConfig.from_dict(_raw),
        raw_org_config=_raw,
        provider_id="claude",
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


def test_prepare_start_session_injects_mcp_servers(tmp_path: Path) -> None:
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    _raw = {
        "defaults": {},
        "profiles": {"alpha": {}},
    }
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
        org_config=NormalizedOrgConfig.from_dict(_raw),
        raw_org_config=_raw,
        provider_id="claude",
    )
    sync_result = SyncResult(
        success=True,
        rendered_settings={"enabledPlugins": {"tool@market": True}},
    )
    resolver_result = _build_resolver_result(workspace_path)
    dependencies = _build_dependencies(FakeGitClient(branch="main"))
    effective_config = EffectiveConfig(
        mcp_servers=[MCPServer(name="gis-internal", type="sse", url="https://gis.example.com/mcp")]
    )

    with (
        patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ),
        patch(
            "scc_cli.application.start_session.compute_effective_config",
            return_value=effective_config,
        ),
        patch(
            "scc_cli.application.start_session.sync_marketplace_settings",
            return_value=sync_result,
        ),
    ):
        plan = prepare_start_session(request, dependencies=dependencies)

    assert plan.agent_settings is not None
    import json as _json

    parsed = _json.loads(plan.agent_settings.rendered_bytes)
    assert "mcpServers" in parsed
    assert "gis-internal" in parsed["mcpServers"]


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


# ---------------------------------------------------------------------------
# S01 seam boundary — characterize target shape for T02/T03
#
# These tests describe the intended state after T02/T03 rewire the launch path:
# - StartSessionPlan should carry a typed AgentLaunchSpec from the provider.
# - StartSessionDependencies should include an AgentProvider, not just AgentRunner.
# The xfail tests will be promoted to passing in T02/T03.
# ---------------------------------------------------------------------------


def test_prepared_plan_carries_typed_agent_launch_spec(tmp_path: Path) -> None:
    """After T02, StartSessionPlan should include an AgentLaunchSpec field.

    The prepared plan carries a typed provider-owned spec so the runtime layer
    can consume it without knowing about Claude-specific settings internals.
    """
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()
    request = StartSessionRequest(
        workspace_path=workspace_path,
        workspace_arg=str(workspace_path),
        entry_dir=workspace_path,
        team=None,
        session_name=None,
        resume=False,
        fresh=False,
        offline=True,
        standalone=True,
        dry_run=False,
        allow_suspicious=False,
        org_config=None,
        provider_id="claude",
    )
    resolver_result = _build_resolver_result(workspace_path)
    dependencies = _build_dependencies(FakeGitClient())

    with patch(
        "scc_cli.application.start_session.resolve_workspace",
        return_value=WorkspaceContext(resolver_result),
    ):
        plan = prepare_start_session(request, dependencies=dependencies)

    spec = plan.agent_launch_spec
    assert isinstance(spec, AgentLaunchSpec)
    assert spec.provider_id != ""


def test_start_session_dependencies_accept_agent_provider(tmp_path: Path) -> None:
    """After T02, StartSessionDependencies should accept an AgentProvider.

    This characterizes the wiring target: the dependency container must carry a
    provider so prepare_start_session can call prepare_launch without falling back
    to AgentRunner internals.
    """
    workspace_path = tmp_path / "workspace"
    workspace_path.mkdir()

    deps = StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=FakeGitClient(),
        agent_runner=FakeAgentRunner(),
        agent_provider=FakeAgentProvider(),
        sandbox_runtime=FakeSandboxRuntime(),
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
    )

    assert deps.agent_provider is not None


# ---------------------------------------------------------------------------
# S04/T05 — Bundle pipeline wiring through AgentProvider.render_artifacts
# ---------------------------------------------------------------------------


def _build_org_config_with_bundles(
    team_name: str = "alpha",
    bundle_id: str = "security-pack",
    *,
    provider: str = "fake",
) -> NormalizedOrgConfig:
    """Build a NormalizedOrgConfig with governed artifacts and bundles."""
    catalog = GovernedArtifactsCatalog(
        artifacts={
            "safety-net": GovernedArtifact(
                kind=ArtifactKind.SKILL,
                name="safety-net",
                install_intent=ArtifactInstallIntent.REQUIRED,
            ),
        },
        bindings={
            "safety-net": (
                ProviderArtifactBinding(
                    provider=provider,
                    native_ref="safety-net-skill",
                ),
            ),
        },
        bundles={
            bundle_id: ArtifactBundle(
                name=bundle_id,
                description="Security bundle",
                artifacts=("safety-net",),
                install_intent=ArtifactInstallIntent.REQUIRED,
            ),
        },
    )
    from scc_cli.ports.config_models import NormalizedTeamConfig

    return NormalizedOrgConfig(
        organization=MagicMock(name="test-org"),
        profiles={
            team_name: NormalizedTeamConfig(
                name=team_name,
                enabled_bundles=(bundle_id,),
            ),
        },
        governed_artifacts=catalog,
    )


def _build_bundle_request(
    workspace_path: Path,
    *,
    team: str = "alpha",
    org_config: NormalizedOrgConfig | None = None,
    dry_run: bool = False,
    offline: bool = False,
    standalone: bool = False,
) -> StartSessionRequest:
    """Build a StartSessionRequest suitable for bundle pipeline tests."""
    if org_config is None:
        org_config = _build_org_config_with_bundles(team)
    return StartSessionRequest(
        workspace_path=workspace_path,
        workspace_arg=str(workspace_path),
        entry_dir=workspace_path,
        team=team,
        session_name=None,
        resume=False,
        fresh=False,
        offline=offline,
        standalone=standalone,
        dry_run=dry_run,
        allow_suspicious=False,
        org_config=org_config,
        raw_org_config=None,  # Prevents marketplace sync (intentional),
        provider_id="claude",
    )


class TestBundlePipelineWiring:
    """Tests for the bundle render pipeline wired through prepare_start_session."""

    def test_bundle_pipeline_renders_artifacts_into_plan(self, tmp_path: Path) -> None:
        """When org config has bundles, the plan carries render results."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = _build_bundle_request(workspace_path)
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies(FakeGitClient())

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.bundle_render_error is None
        assert len(plan.bundle_render_results) == 1
        result = plan.bundle_render_results[0]
        assert isinstance(result, RenderArtifactsResult)

    def test_bundle_pipeline_skipped_when_no_team(self, tmp_path: Path) -> None:
        """When no team is set, the bundle pipeline is skipped."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = _build_bundle_request(workspace_path, team=None)  # type: ignore[arg-type]
        # Need a valid request without team
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=False,
            standalone=False,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies(FakeGitClient())

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.bundle_render_results == ()
        assert plan.bundle_render_error is None

    def test_bundle_pipeline_skipped_when_dry_run(self, tmp_path: Path) -> None:
        """Dry-run mode skips bundle rendering."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = _build_bundle_request(workspace_path, dry_run=True)
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies(FakeGitClient())

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.bundle_render_results == ()
        assert plan.bundle_render_error is None

    def test_bundle_pipeline_skipped_when_offline(self, tmp_path: Path) -> None:
        """Offline mode skips bundle rendering."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = _build_bundle_request(workspace_path, offline=True)
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies(FakeGitClient())

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.bundle_render_results == ()
        assert plan.bundle_render_error is None

    def test_bundle_pipeline_skipped_when_standalone(self, tmp_path: Path) -> None:
        """Standalone mode skips bundle rendering."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = _build_bundle_request(workspace_path, standalone=True)
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies(FakeGitClient())

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.bundle_render_results == ()
        assert plan.bundle_render_error is None

    def test_bundle_pipeline_no_provider_raises_d032(self, tmp_path: Path) -> None:
        """D032: no agent_provider wired + no provider_id raises InvalidProviderError."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        # Deliberately omit provider_id to trigger fail-closed behavior
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
            org_config=_build_org_config_with_bundles("alpha"),
            raw_org_config=None,
        )
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = StartSessionDependencies(
            filesystem=MagicMock(),
            remote_fetcher=MagicMock(),
            clock=MagicMock(),
            git_client=FakeGitClient(),
            agent_runner=FakeAgentRunner(),
            agent_provider=None,  # No provider
            sandbox_runtime=FakeSandboxRuntime(),
            resolve_effective_config=MagicMock(),
            materialize_marketplace=MagicMock(),
        )

        with (
            patch(
                "scc_cli.application.start_session.resolve_workspace",
                return_value=WorkspaceContext(resolver_result),
            ),
            pytest.raises(InvalidProviderError),
        ):
            prepare_start_session(request, dependencies=dependencies)

    def test_bundle_pipeline_captures_resolution_error(self, tmp_path: Path) -> None:
        """When bundle resolution fails (missing bundle), error is captured fail-closed."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        # Reference a bundle that doesn't exist in the catalog
        org_config = _build_org_config_with_bundles(bundle_id="nonexistent")
        # But the team references a different bundle
        from scc_cli.ports.config_models import NormalizedTeamConfig

        org_config = NormalizedOrgConfig(
            organization=MagicMock(name="test-org"),
            profiles={
                "alpha": NormalizedTeamConfig(
                    name="alpha",
                    enabled_bundles=("missing-bundle",),
                ),
            },
            governed_artifacts=GovernedArtifactsCatalog(
                bundles={
                    "existing": ArtifactBundle(
                        name="existing",
                        artifacts=(),
                    ),
                },
            ),
        )
        request = _build_bundle_request(workspace_path, org_config=org_config)
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies(FakeGitClient())

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        # Fail-closed: error is captured, not raised
        assert plan.bundle_render_error is not None
        assert "missing-bundle" in plan.bundle_render_error
        assert plan.bundle_render_results == ()

    def test_bundle_pipeline_captures_renderer_error(self, tmp_path: Path) -> None:
        """When renderer raises MaterializationError, error is captured fail-closed."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        org_config = _build_org_config_with_bundles()
        request = _build_bundle_request(workspace_path, org_config=org_config)
        resolver_result = _build_resolver_result(workspace_path)

        # Create a provider that raises on render_artifacts
        provider = FakeAgentProvider()

        def _exploding_render(
            plan: ArtifactRenderPlan, workspace: Path
        ) -> RenderArtifactsResult:
            raise MaterializationError(
                bundle_id="security-pack",
                artifact_name="safety-net",
                target_path="/tmp/boom",
                reason="disk full",
            )

        provider.render_artifacts = _exploding_render  # type: ignore[assignment]
        dependencies = StartSessionDependencies(
            filesystem=MagicMock(),
            remote_fetcher=MagicMock(),
            clock=MagicMock(),
            git_client=FakeGitClient(),
            agent_runner=FakeAgentRunner(),
            agent_provider=provider,
            sandbox_runtime=FakeSandboxRuntime(),
            resolve_effective_config=MagicMock(),
            materialize_marketplace=MagicMock(),
        )

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.bundle_render_error is not None
        assert "disk full" in plan.bundle_render_error
        assert plan.bundle_render_results == ()

    def test_bundle_pipeline_empty_bundles_no_error(self, tmp_path: Path) -> None:
        """When team has no enabled bundles, pipeline succeeds with empty results."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        from scc_cli.ports.config_models import NormalizedTeamConfig

        org_config = NormalizedOrgConfig(
            organization=MagicMock(name="test-org"),
            profiles={
                "alpha": NormalizedTeamConfig(
                    name="alpha",
                    enabled_bundles=(),  # No bundles
                ),
            },
        )
        request = _build_bundle_request(workspace_path, org_config=org_config)
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies(FakeGitClient())

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.bundle_render_results == ()
        assert plan.bundle_render_error is None

    def test_fake_provider_records_render_calls(self, tmp_path: Path) -> None:
        """FakeAgentProvider.render_artifacts records calls for test assertions."""
        provider = FakeAgentProvider()
        plan = ArtifactRenderPlan(
            bundle_id="test-bundle",
            provider="fake",
            bindings=(
                ProviderArtifactBinding(provider="fake", native_ref="test-skill"),
            ),
            effective_artifacts=("test-artifact",),
        )
        result = provider.render_artifacts(plan, tmp_path)

        assert len(provider.render_artifacts_calls) == 1
        assert provider.render_artifacts_calls[0] == (plan, tmp_path)
        assert isinstance(result, RenderArtifactsResult)


class TestAgentProviderRenderArtifacts:
    """Tests for the render_artifacts method on concrete provider adapters."""

    def test_claude_provider_render_artifacts(self, tmp_path: Path) -> None:
        """ClaudeAgentProvider.render_artifacts delegates to claude_renderer."""
        from scc_cli.adapters.claude_agent_provider import ClaudeAgentProvider

        provider = ClaudeAgentProvider()
        plan = ArtifactRenderPlan(
            bundle_id="test-bundle",
            provider="claude",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="safety-net-skill",
                ),
            ),
            effective_artifacts=("safety-net",),
        )
        result = provider.render_artifacts(plan, tmp_path)

        assert isinstance(result, RenderArtifactsResult)
        # Skill binding should produce a rendered path
        assert len(result.rendered_paths) == 1
        assert result.rendered_paths[0].name == "skill.json"

    def test_codex_provider_render_artifacts(self, tmp_path: Path) -> None:
        """CodexAgentProvider.render_artifacts delegates to codex_renderer."""
        from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

        provider = CodexAgentProvider()
        plan = ArtifactRenderPlan(
            bundle_id="test-bundle",
            provider="codex",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="safety-net-skill",
                ),
            ),
            effective_artifacts=("safety-net",),
        )
        result = provider.render_artifacts(plan, tmp_path)

        assert isinstance(result, RenderArtifactsResult)
        # Skill binding should produce a rendered path
        assert len(result.rendered_paths) == 1
        assert result.rendered_paths[0].name == "skill.json"

    def test_claude_provider_returns_settings_fragment(self, tmp_path: Path) -> None:
        """Claude renderer's settings_fragment is propagated through the provider."""
        from scc_cli.adapters.claude_agent_provider import ClaudeAgentProvider

        provider = ClaudeAgentProvider()
        plan = ArtifactRenderPlan(
            bundle_id="mcp-bundle",
            provider="claude",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="gis-server",
                    transport_type="sse",
                    native_config={"url": "https://gis.example.com/mcp"},
                ),
            ),
            effective_artifacts=("gis-mcp",),
        )
        result = provider.render_artifacts(plan, tmp_path)

        assert isinstance(result, RenderArtifactsResult)
        assert "mcpServers" in result.settings_fragment
        assert "gis-server" in result.settings_fragment["mcpServers"]

    def test_codex_provider_maps_mcp_fragment_to_settings_fragment(self, tmp_path: Path) -> None:
        """Codex renderer's mcp_fragment is mapped to settings_fragment in the unified result."""
        from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

        provider = CodexAgentProvider()
        plan = ArtifactRenderPlan(
            bundle_id="mcp-bundle",
            provider="codex",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="gis-server",
                    transport_type="sse",
                    native_config={"url": "https://gis.example.com/mcp"},
                ),
            ),
            effective_artifacts=("gis-mcp",),
        )
        result = provider.render_artifacts(plan, tmp_path)

        assert isinstance(result, RenderArtifactsResult)
        # Codex mcp_fragment mapped to settings_fragment
        assert "mcpServers" in result.settings_fragment
        assert "gis-server" in result.settings_fragment["mcpServers"]

    def test_claude_provider_wrong_provider_returns_warnings(self, tmp_path: Path) -> None:
        """Claude renderer skips plans targeting a different provider."""
        from scc_cli.adapters.claude_agent_provider import ClaudeAgentProvider

        provider = ClaudeAgentProvider()
        plan = ArtifactRenderPlan(
            bundle_id="test",
            provider="codex",  # Wrong provider
            effective_artifacts=("something",),
        )
        result = provider.render_artifacts(plan, tmp_path)

        assert len(result.warnings) > 0
        assert "codex" in result.warnings[0]


# ---------------------------------------------------------------------------
# S02/T02 — Provider-aware image selection and agent_argv propagation
# ---------------------------------------------------------------------------

_OCI_RUNTIME_INFO = RuntimeInfo(
    runtime_id="docker",
    display_name="Docker (OCI)",
    cli_name="docker",
    supports_oci=True,
    supports_internal_networks=True,
    supports_host_network=True,
    version="Docker version 27.5.1, build abc1234",
    daemon_reachable=True,
    sandbox_available=True,
    preferred_backend="oci",
)


def _build_dependencies_with_runtime(
    *,
    provider: FakeAgentProvider | None = None,
    runtime_info: RuntimeInfo | None = None,
) -> StartSessionDependencies:
    return StartSessionDependencies(
        filesystem=MagicMock(),
        remote_fetcher=MagicMock(),
        clock=MagicMock(),
        git_client=FakeGitClient(),
        agent_runner=FakeAgentRunner(),
        agent_provider=provider or FakeAgentProvider(),
        sandbox_runtime=FakeSandboxRuntime(),
        resolve_effective_config=MagicMock(),
        materialize_marketplace=MagicMock(),
        runtime_info=runtime_info,
    )


class TestProviderAwareImageSelection:
    """_build_sandbox_spec selects image by provider_id on OCI backend."""

    def test_codex_image_for_oci_backend(self, tmp_path: Path) -> None:
        """Codex provider on OCI backend gets SCC_CODEX_IMAGE_REF."""
        from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        codex_provider = CodexAgentProvider()
        dependencies = _build_dependencies_with_runtime(
            provider=codex_provider,  # type: ignore[arg-type]
            runtime_info=_OCI_RUNTIME_INFO,
        )

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.image == SCC_CODEX_IMAGE_REF

    def test_claude_image_for_oci_backend(self, tmp_path: Path) -> None:
        """Claude provider on OCI backend gets SCC_CLAUDE_IMAGE_REF."""
        from scc_cli.adapters.claude_agent_provider import ClaudeAgentProvider

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        claude_provider = ClaudeAgentProvider()
        dependencies = _build_dependencies_with_runtime(
            provider=claude_provider,  # type: ignore[arg-type]
            runtime_info=_OCI_RUNTIME_INFO,
        )

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.image == SCC_CLAUDE_IMAGE_REF

    def test_docker_sandbox_backend_uses_sandbox_image(self, tmp_path: Path) -> None:
        """Non-OCI backend (docker-sandbox) falls back to SANDBOX_IMAGE."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        docker_sandbox_info = RuntimeInfo(
            runtime_id="docker",
            display_name="Docker Desktop",
            cli_name="docker",
            supports_oci=True,
            supports_internal_networks=True,
            supports_host_network=True,
            version="Docker version 27.5.1",
            daemon_reachable=True,
            sandbox_available=True,
            preferred_backend="docker-sandbox",
        )
        dependencies = _build_dependencies_with_runtime(runtime_info=docker_sandbox_info)

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.image == SANDBOX_IMAGE

    def test_unknown_provider_raises_invalid_provider_error(self, tmp_path: Path) -> None:
        """Unknown provider_id on OCI backend raises InvalidProviderError."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        # FakeAgentProvider has provider_id="fake" which is not in the registry
        dependencies = _build_dependencies_with_runtime(runtime_info=_OCI_RUNTIME_INFO)

        with (
            patch(
                "scc_cli.application.start_session.resolve_workspace",
                return_value=WorkspaceContext(resolver_result),
            ),
            patch(
                "scc_cli.application.start_session.resolve_destination_sets",
                return_value=(),
            ),
            pytest.raises(InvalidProviderError),
        ):
            prepare_start_session(request, dependencies=dependencies)


class TestAgentArgvPropagation:
    """agent_argv from AgentLaunchSpec flows into SandboxSpec."""

    def test_agent_argv_from_launch_spec(self, tmp_path: Path) -> None:
        """agent_argv populated from provider's prepare_launch argv."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = _build_dependencies_with_runtime()

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        # FakeAgentProvider.prepare_launch returns argv=("fake-agent",)
        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.agent_argv == ["fake-agent"]

    def test_no_provider_no_provider_id_raises(self, tmp_path: Path) -> None:
        """D032: no provider wired + no provider_id raises InvalidProviderError."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        # Deliberately omit provider_id to trigger fail-closed behavior
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
        )
        resolver_result = _build_resolver_result(workspace_path)
        dependencies = StartSessionDependencies(
            filesystem=MagicMock(),
            remote_fetcher=MagicMock(),
            clock=MagicMock(),
            git_client=FakeGitClient(),
            agent_runner=FakeAgentRunner(),
            agent_provider=None,
            sandbox_runtime=FakeSandboxRuntime(),
            resolve_effective_config=MagicMock(),
            materialize_marketplace=MagicMock(),
        )

        with (
            patch(
                "scc_cli.application.start_session.resolve_workspace",
                return_value=WorkspaceContext(resolver_result),
            ),
            pytest.raises(InvalidProviderError),
        ):
            prepare_start_session(request, dependencies=dependencies)

    def test_codex_agent_argv_is_codex(self, tmp_path: Path) -> None:
        """Codex provider produces 'codex' in agent_argv."""
        from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        codex_provider = CodexAgentProvider()
        dependencies = _build_dependencies_with_runtime(
            provider=codex_provider,  # type: ignore[arg-type]
        )

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.agent_argv == ["codex"]


# ---------------------------------------------------------------------------
# S02/T03 — Provider-aware data_volume and config_dir population
# ---------------------------------------------------------------------------


class TestProviderAwareDataVolumeAndConfigDir:
    """_build_sandbox_spec populates data_volume and config_dir by provider_id."""

    def test_codex_data_volume(self, tmp_path: Path) -> None:
        """Codex provider on OCI backend gets codex data volume."""
        from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        codex_provider = CodexAgentProvider()
        dependencies = _build_dependencies_with_runtime(
            provider=codex_provider,  # type: ignore[arg-type]
            runtime_info=_OCI_RUNTIME_INFO,
        )

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.data_volume == "docker-codex-sandbox-data"

    def test_codex_config_dir(self, tmp_path: Path) -> None:
        """Codex provider on OCI backend gets .codex config dir."""
        from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        codex_provider = CodexAgentProvider()
        dependencies = _build_dependencies_with_runtime(
            provider=codex_provider,  # type: ignore[arg-type]
            runtime_info=_OCI_RUNTIME_INFO,
        )

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.config_dir == ".codex"

    def test_claude_data_volume(self, tmp_path: Path) -> None:
        """Claude provider on OCI backend gets claude data volume."""
        from scc_cli.adapters.claude_agent_provider import ClaudeAgentProvider

        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        claude_provider = ClaudeAgentProvider()
        dependencies = _build_dependencies_with_runtime(
            provider=claude_provider,  # type: ignore[arg-type]
            runtime_info=_OCI_RUNTIME_INFO,
        )

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.data_volume == "docker-claude-sandbox-data"
        assert plan.sandbox_spec.config_dir == ".claude"

    def test_non_oci_backend_empty_volume_and_config(self, tmp_path: Path) -> None:
        """Non-OCI backend leaves data_volume and config_dir empty."""
        workspace_path = tmp_path / "workspace"
        workspace_path.mkdir()
        request = StartSessionRequest(
            workspace_path=workspace_path,
            workspace_arg=str(workspace_path),
            entry_dir=workspace_path,
            team=None,
            session_name=None,
            resume=False,
            fresh=False,
            offline=True,
            standalone=True,
            dry_run=False,
            allow_suspicious=False,
            org_config=None,
            provider_id="claude",
        )
        resolver_result = _build_resolver_result(workspace_path)
        docker_sandbox_info = RuntimeInfo(
            runtime_id="docker",
            display_name="Docker Desktop",
            cli_name="docker",
            supports_oci=True,
            supports_internal_networks=True,
            supports_host_network=True,
            version="Docker version 27.5.1",
            daemon_reachable=True,
            sandbox_available=True,
            preferred_backend="docker-sandbox",
        )
        dependencies = _build_dependencies_with_runtime(runtime_info=docker_sandbox_info)

        with patch(
            "scc_cli.application.start_session.resolve_workspace",
            return_value=WorkspaceContext(resolver_result),
        ):
            plan = prepare_start_session(request, dependencies=dependencies)

        assert plan.sandbox_spec is not None
        assert plan.sandbox_spec.data_volume == ""
        assert plan.sandbox_spec.config_dir == ""
