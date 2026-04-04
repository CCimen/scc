"""Cross-provider render plan equivalence and pipeline integration tests.

Exercises the full planning→rendering pipeline:
    NormalizedOrgConfig → resolve_render_plan → render_*_artifacts → verify

1. Same org config + same team → same shared artifacts (skills, MCP) in both plans
2. Provider-specific bindings appear only for the matching provider
3. Switching provider re-renders from same plan, produces different native outputs
4. End-to-end: NormalizedOrgConfig → resolve → render → verify file outputs
5. Backward compatibility: teams without governed_artifacts → empty plans, no error
6. Pipeline seam: bundle_resolver + renderer boundary contracts verified
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scc_cli.adapters.claude_renderer import (
    SCC_MANAGED_DIR as CLAUDE_SCC_DIR,
)
from scc_cli.adapters.claude_renderer import (
    render_claude_artifacts,
)
from scc_cli.adapters.codex_renderer import (
    SKILLS_DIR as CODEX_SKILLS_DIR,
)
from scc_cli.adapters.codex_renderer import (
    render_codex_artifacts,
)
from scc_cli.core.bundle_resolver import (
    BundleResolutionResult,
    resolve_render_plan,
)
from scc_cli.core.governed_artifacts import (
    ArtifactBundle,
    ArtifactInstallIntent,
    ArtifactKind,
    ArtifactRenderPlan,
    GovernedArtifact,
    ProviderArtifactBinding,
)
from scc_cli.ports.config_models import (
    GovernedArtifactsCatalog,
    NormalizedOrgConfig,
    NormalizedTeamConfig,
    OrganizationInfo,
)

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _org(
    *,
    profiles: dict[str, NormalizedTeamConfig] | None = None,
    catalog: GovernedArtifactsCatalog | None = None,
) -> NormalizedOrgConfig:
    return NormalizedOrgConfig(
        organization=OrganizationInfo(name="integration-test-org"),
        profiles=profiles or {},
        governed_artifacts=catalog or GovernedArtifactsCatalog(),
    )


def _team(name: str, bundles: tuple[str, ...] = ()) -> NormalizedTeamConfig:
    return NormalizedTeamConfig(name=name, enabled_bundles=bundles)


def _skill(
    name: str,
    intent: ArtifactInstallIntent = ArtifactInstallIntent.REQUIRED,
) -> GovernedArtifact:
    return GovernedArtifact(kind=ArtifactKind.SKILL, name=name, install_intent=intent)


def _mcp(
    name: str,
    intent: ArtifactInstallIntent = ArtifactInstallIntent.REQUIRED,
) -> GovernedArtifact:
    return GovernedArtifact(kind=ArtifactKind.MCP_SERVER, name=name, install_intent=intent)


def _native(
    name: str,
    intent: ArtifactInstallIntent = ArtifactInstallIntent.AVAILABLE,
) -> GovernedArtifact:
    return GovernedArtifact(
        kind=ArtifactKind.NATIVE_INTEGRATION, name=name, install_intent=intent
    )


# ---------------------------------------------------------------------------
# Shared realistic catalog — skills + MCP + provider-specific natives
# ---------------------------------------------------------------------------

_SHARED_CATALOG = GovernedArtifactsCatalog(
    artifacts={
        "review-skill": _skill("review-skill"),
        "lint-skill": _skill("lint-skill"),
        "github-mcp": _mcp("github-mcp"),
        "slack-mcp": _mcp("slack-mcp"),
        "claude-hooks": _native("claude-hooks"),
        "codex-rules": _native("codex-rules"),
    },
    bindings={
        # Shared skill — both providers
        "review-skill": (
            ProviderArtifactBinding(provider="claude", native_ref="skills/review"),
            ProviderArtifactBinding(provider="codex", native_ref="skills/review"),
        ),
        # Shared skill — both providers
        "lint-skill": (
            ProviderArtifactBinding(provider="claude", native_ref="skills/lint"),
            ProviderArtifactBinding(provider="codex", native_ref="skills/lint"),
        ),
        # Shared MCP — both providers via SSE
        "github-mcp": (
            ProviderArtifactBinding(
                provider="claude",
                native_ref="mcp/github",
                transport_type="sse",
                native_config={"url": "http://github-mcp:8080/sse"},
            ),
            ProviderArtifactBinding(
                provider="codex",
                native_ref="mcp/github",
                transport_type="sse",
                native_config={"url": "http://github-mcp:8080/sse"},
            ),
        ),
        # Shared MCP — both providers via stdio
        "slack-mcp": (
            ProviderArtifactBinding(
                provider="claude",
                native_ref="mcp/slack",
                transport_type="stdio",
                native_config={"command": "slack-mcp-server", "args": "--port 9090"},
            ),
            ProviderArtifactBinding(
                provider="codex",
                native_ref="mcp/slack",
                transport_type="stdio",
                native_config={"command": "slack-mcp-server", "args": "--port 9090"},
            ),
        ),
        # Claude-only native integration
        "claude-hooks": (
            ProviderArtifactBinding(
                provider="claude",
                native_config={"hooks": "./claude/hooks.json"},
            ),
        ),
        # Codex-only native integration
        "codex-rules": (
            ProviderArtifactBinding(
                provider="codex",
                native_config={"rules": "./codex/safety.rules"},
            ),
        ),
    },
    bundles={
        "core-tools": ArtifactBundle(
            name="core-tools",
            description="Shared skills and MCP servers",
            artifacts=("review-skill", "lint-skill", "github-mcp", "slack-mcp"),
        ),
        "provider-native": ArtifactBundle(
            name="provider-native",
            description="Provider-specific native integrations",
            artifacts=("claude-hooks", "codex-rules"),
        ),
        "mixed-bundle": ArtifactBundle(
            name="mixed-bundle",
            description="Skills + MCP + natives",
            artifacts=(
                "review-skill",
                "github-mcp",
                "claude-hooks",
                "codex-rules",
            ),
        ),
    },
)


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Fresh temporary workspace for renderer output."""
    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════
# 1. Shared artifacts appear in both providers' plans
# ═══════════════════════════════════════════════════════════════════════════


class TestSharedArtifactsInBothPlans:
    """Same org config + same team → same shared artifacts in both plans."""

    def _resolve_both(self) -> tuple[BundleResolutionResult, BundleResolutionResult]:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        claude_result = resolve_render_plan(org, "dev", "claude")
        codex_result = resolve_render_plan(org, "dev", "codex")
        return claude_result, codex_result

    def test_both_providers_produce_one_plan(self) -> None:
        claude_r, codex_r = self._resolve_both()
        assert len(claude_r.plans) == 1
        assert len(codex_r.plans) == 1

    def test_shared_skills_in_both_effective_artifacts(self) -> None:
        claude_r, codex_r = self._resolve_both()
        claude_eff = claude_r.plans[0].effective_artifacts
        codex_eff = codex_r.plans[0].effective_artifacts
        # Skills and MCP are shared
        for art in ("review-skill", "lint-skill", "github-mcp", "slack-mcp"):
            assert art in claude_eff, f"{art} missing from Claude effective_artifacts"
            assert art in codex_eff, f"{art} missing from Codex effective_artifacts"

    def test_effective_artifact_sets_identical(self) -> None:
        claude_r, codex_r = self._resolve_both()
        assert set(claude_r.plans[0].effective_artifacts) == set(
            codex_r.plans[0].effective_artifacts
        )

    def test_no_diagnostics_for_shared_bundle(self) -> None:
        claude_r, codex_r = self._resolve_both()
        assert len(claude_r.diagnostics) == 0
        assert len(codex_r.diagnostics) == 0

    def test_bindings_are_provider_filtered(self) -> None:
        """Each plan only contains bindings for its target provider."""
        claude_r, codex_r = self._resolve_both()
        for b in claude_r.plans[0].bindings:
            assert b.provider == "claude"
        for b in codex_r.plans[0].bindings:
            assert b.provider == "codex"


# ═══════════════════════════════════════════════════════════════════════════
# 2. Provider-specific bindings appear only for matching provider
# ═══════════════════════════════════════════════════════════════════════════


class TestProviderSpecificBindingsFiltered:
    """Native integrations with single-provider bindings are routed correctly."""

    def _resolve_both(self) -> tuple[BundleResolutionResult, BundleResolutionResult]:
        org = _org(
            profiles={"dev": _team("dev", bundles=("provider-native",))},
            catalog=_SHARED_CATALOG,
        )
        return (
            resolve_render_plan(org, "dev", "claude"),
            resolve_render_plan(org, "dev", "codex"),
        )

    def test_claude_hooks_in_claude_plan_only(self) -> None:
        claude_r, codex_r = self._resolve_both()
        assert "claude-hooks" in claude_r.plans[0].effective_artifacts
        assert "claude-hooks" not in codex_r.plans[0].effective_artifacts

    def test_codex_rules_in_codex_plan_only(self) -> None:
        claude_r, codex_r = self._resolve_both()
        assert "codex-rules" not in claude_r.plans[0].effective_artifacts
        assert "codex-rules" in codex_r.plans[0].effective_artifacts

    def test_claude_hooks_skipped_in_codex_with_diagnostic(self) -> None:
        _, codex_r = self._resolve_both()
        assert "claude-hooks" in codex_r.plans[0].skipped
        diag_names = {d.artifact_name for d in codex_r.diagnostics}
        assert "claude-hooks" in diag_names

    def test_codex_rules_skipped_in_claude_with_diagnostic(self) -> None:
        claude_r, _ = self._resolve_both()
        assert "codex-rules" in claude_r.plans[0].skipped
        diag_names = {d.artifact_name for d in claude_r.diagnostics}
        assert "codex-rules" in diag_names

    def test_bindings_contain_only_matching_provider(self) -> None:
        claude_r, codex_r = self._resolve_both()
        for b in claude_r.plans[0].bindings:
            assert b.provider == "claude"
        for b in codex_r.plans[0].bindings:
            assert b.provider == "codex"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Switching provider re-renders different native outputs
# ═══════════════════════════════════════════════════════════════════════════


class TestSwitchProviderDifferentOutputs:
    """Same plan input → different native file structures per provider."""

    def test_skill_rendered_to_different_directories(self, workspace: Path) -> None:
        """Skill binding → different base dirs (.claude/.scc-managed vs .agents)."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        claude_plans = resolve_render_plan(org, "dev", "claude").plans
        codex_plans = resolve_render_plan(org, "dev", "codex").plans

        # Use separate workspaces to avoid file collisions
        ws_claude = workspace / "claude-ws"
        ws_codex = workspace / "codex-ws"
        ws_claude.mkdir()
        ws_codex.mkdir()

        claude_result = render_claude_artifacts(claude_plans[0], ws_claude)
        codex_result = render_codex_artifacts(codex_plans[0], ws_codex)

        # Claude skills go under .claude/.scc-managed/skills/
        claude_skill_paths = [
            p for p in claude_result.rendered_paths if "skills" in str(p)
        ]
        # Codex skills go under .agents/skills/
        codex_skill_paths = [
            p for p in codex_result.rendered_paths if "skills" in str(p)
        ]

        assert len(claude_skill_paths) > 0
        assert len(codex_skill_paths) > 0

        for p in claude_skill_paths:
            assert CLAUDE_SCC_DIR in str(p.relative_to(ws_claude))
        for p in codex_skill_paths:
            assert CODEX_SKILLS_DIR in str(p.relative_to(ws_codex))

    def test_mcp_rendered_to_different_config_surfaces(self, workspace: Path) -> None:
        """MCP bindings → settings_fragment (Claude) vs mcp_fragment (Codex)."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        claude_plans = resolve_render_plan(org, "dev", "claude").plans
        codex_plans = resolve_render_plan(org, "dev", "codex").plans

        ws_claude = workspace / "claude-ws"
        ws_codex = workspace / "codex-ws"
        ws_claude.mkdir()
        ws_codex.mkdir()

        claude_result = render_claude_artifacts(claude_plans[0], ws_claude)
        codex_result = render_codex_artifacts(codex_plans[0], ws_codex)

        # Claude: settings_fragment has mcpServers
        assert "mcpServers" in claude_result.settings_fragment
        claude_servers = claude_result.settings_fragment["mcpServers"]
        assert "mcp/github" in claude_servers
        assert "mcp/slack" in claude_servers

        # Codex: mcp_fragment has mcpServers
        assert "mcpServers" in codex_result.mcp_fragment
        codex_servers = codex_result.mcp_fragment["mcpServers"]
        assert "mcp/github" in codex_servers
        assert "mcp/slack" in codex_servers

    def test_native_hooks_rendered_only_by_claude(self, workspace: Path) -> None:
        """claude-hooks native binding → only Claude renderer produces hook files."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        claude_plans = resolve_render_plan(org, "dev", "claude").plans
        codex_plans = resolve_render_plan(org, "dev", "codex").plans

        ws_claude = workspace / "claude-ws"
        ws_codex = workspace / "codex-ws"
        ws_claude.mkdir()
        ws_codex.mkdir()

        claude_result = render_claude_artifacts(claude_plans[0], ws_claude)
        codex_result = render_codex_artifacts(codex_plans[0], ws_codex)

        # Claude should have rendered hooks (filter on relative path to avoid
        # tmp_path containing test name like "hooks" in the directory)
        claude_hook_paths = [
            p
            for p in claude_result.rendered_paths
            if "hooks" in str(p.relative_to(ws_claude))
        ]
        assert len(claude_hook_paths) > 0

        # Codex should NOT have rendered hooks (claude-hooks has no codex binding)
        codex_hook_paths = [
            p
            for p in codex_result.rendered_paths
            if "hooks" in str(p.relative_to(ws_codex))
        ]
        assert len(codex_hook_paths) == 0

    def test_native_rules_rendered_only_by_codex(self, workspace: Path) -> None:
        """codex-rules native binding → only Codex renderer produces rule files."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        claude_plans = resolve_render_plan(org, "dev", "claude").plans
        codex_plans = resolve_render_plan(org, "dev", "codex").plans

        ws_claude = workspace / "claude-ws"
        ws_codex = workspace / "codex-ws"
        ws_claude.mkdir()
        ws_codex.mkdir()

        claude_result = render_claude_artifacts(claude_plans[0], ws_claude)
        codex_result = render_codex_artifacts(codex_plans[0], ws_codex)

        # Codex should have rendered rules (filter on relative path)
        codex_rule_paths = [
            p
            for p in codex_result.rendered_paths
            if "rules" in str(p.relative_to(ws_codex))
        ]
        assert len(codex_rule_paths) > 0

        # Claude should NOT have rendered rules (codex-rules has no claude binding)
        claude_rule_paths = [
            p
            for p in claude_result.rendered_paths
            if "rules" in str(p.relative_to(ws_claude))
        ]
        assert len(claude_rule_paths) == 0


# ═══════════════════════════════════════════════════════════════════════════
# 4. End-to-end: NormalizedOrgConfig → resolve → render → verify files
# ═══════════════════════════════════════════════════════════════════════════


class TestEndToEndPipelineClaude:
    """Full pipeline for Claude: org config → file outputs on disk."""

    def test_skill_files_written_with_correct_metadata(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans
        result = render_claude_artifacts(plans[0], workspace)

        # Find skill metadata files
        skill_files = list(
            (workspace / CLAUDE_SCC_DIR / "skills").rglob("skill.json")
        )
        assert len(skill_files) == 2  # review-skill, lint-skill

        for sf in skill_files:
            data = json.loads(sf.read_text())
            assert data["provider"] == "claude"
            assert data["bundle_id"] == "core-tools"
            assert data["managed_by"] == "scc"
            assert "native_ref" in data

        assert len(result.warnings) == 0

    def test_mcp_settings_fragment_has_correct_transport(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans
        result = render_claude_artifacts(plans[0], workspace)

        servers = result.settings_fragment["mcpServers"]
        # github-mcp is SSE
        assert servers["mcp/github"]["type"] == "sse"
        assert servers["mcp/github"]["url"] == "http://github-mcp:8080/sse"
        # slack-mcp is stdio
        assert servers["mcp/slack"]["type"] == "stdio"
        assert servers["mcp/slack"]["command"] == "slack-mcp-server"

    def test_settings_audit_file_written(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans
        render_claude_artifacts(plans[0], workspace)

        audit_file = workspace / ".claude" / ".scc-settings-core-tools.json"
        assert audit_file.exists()
        audit_data = json.loads(audit_file.read_text())
        assert "mcpServers" in audit_data

    def test_native_hooks_file_written(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans
        render_claude_artifacts(plans[0], workspace)

        hook_files = list(
            (workspace / CLAUDE_SCC_DIR / "hooks").rglob("*.json")
        )
        assert len(hook_files) == 1
        data = json.loads(hook_files[0].read_text())
        assert data["managed_by"] == "scc"
        assert data["source"] == "./claude/hooks.json"


class TestEndToEndPipelineCodex:
    """Full pipeline for Codex: org config → file outputs on disk."""

    def test_skill_files_written_with_correct_metadata(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "codex").plans
        result = render_codex_artifacts(plans[0], workspace)

        skill_files = list(
            (workspace / CODEX_SKILLS_DIR).rglob("skill.json")
        )
        assert len(skill_files) == 2  # review-skill, lint-skill

        for sf in skill_files:
            data = json.loads(sf.read_text())
            assert data["provider"] == "codex"
            assert data["bundle_id"] == "core-tools"
            assert data["managed_by"] == "scc"
            assert "native_ref" in data

        assert len(result.warnings) == 0

    def test_mcp_fragment_has_correct_transport(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "codex").plans
        result = render_codex_artifacts(plans[0], workspace)

        servers = result.mcp_fragment["mcpServers"]
        assert servers["mcp/github"]["type"] == "sse"
        assert servers["mcp/github"]["url"] == "http://github-mcp:8080/sse"
        assert servers["mcp/slack"]["type"] == "stdio"
        assert servers["mcp/slack"]["command"] == "slack-mcp-server"

    def test_mcp_audit_file_written(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "codex").plans
        render_codex_artifacts(plans[0], workspace)

        audit_file = workspace / ".codex" / ".scc-mcp-core-tools.json"
        assert audit_file.exists()
        audit_data = json.loads(audit_file.read_text())
        assert "mcpServers" in audit_data

    def test_native_rules_file_written(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "codex").plans
        render_codex_artifacts(plans[0], workspace)

        rule_files = list(
            (workspace / ".codex" / "rules").rglob("*.rules.json")
        )
        assert len(rule_files) == 1
        data = json.loads(rule_files[0].read_text())
        assert data["managed_by"] == "scc"
        assert data["source"] == "./codex/safety.rules"


# ═══════════════════════════════════════════════════════════════════════════
# 5. Backward compatibility: teams without governed_artifacts
# ═══════════════════════════════════════════════════════════════════════════


class TestBackwardCompatibilityNoGovernedArtifacts:
    """Teams without governed_artifacts config → empty plans, no errors."""

    def test_team_with_no_bundles_produces_empty_result(self) -> None:
        org = _org(
            profiles={"legacy": _team("legacy", bundles=())},
            catalog=_SHARED_CATALOG,
        )
        result = resolve_render_plan(org, "legacy", "claude")
        assert result.plans == ()
        assert result.diagnostics == ()

    def test_empty_catalog_with_no_bundles_produces_empty_result(self) -> None:
        org = _org(
            profiles={"legacy": _team("legacy", bundles=())},
            catalog=GovernedArtifactsCatalog(),
        )
        result = resolve_render_plan(org, "legacy", "codex")
        assert result.plans == ()
        assert result.diagnostics == ()

    def test_old_marketplace_team_fields_preserved(self) -> None:
        """Teams with marketplace/plugin fields but no bundles still work."""
        legacy_team = NormalizedTeamConfig(
            name="legacy-team",
            plugin="my-plugin",
            marketplace="my-marketplace",
            enabled_bundles=(),
        )
        org = _org(profiles={"legacy-team": legacy_team})
        result = resolve_render_plan(org, "legacy-team", "claude")
        assert result.plans == ()
        assert result.diagnostics == ()
        # The team's marketplace/plugin fields are untouched
        profile = org.get_profile("legacy-team")
        assert profile is not None
        assert profile.plugin == "my-plugin"
        assert profile.marketplace == "my-marketplace"

    def test_empty_plan_renders_to_empty_result_claude(self, workspace: Path) -> None:
        """Rendering an empty plan produces no files or fragments."""
        plan = ArtifactRenderPlan(bundle_id="empty", provider="claude")
        result = render_claude_artifacts(plan, workspace)
        assert result.rendered_paths == ()
        assert result.settings_fragment == {}
        assert result.warnings == ()

    def test_empty_plan_renders_to_empty_result_codex(self, workspace: Path) -> None:
        plan = ArtifactRenderPlan(bundle_id="empty", provider="codex")
        result = render_codex_artifacts(plan, workspace)
        assert result.rendered_paths == ()
        assert result.mcp_fragment == {}
        assert result.warnings == ()


# ═══════════════════════════════════════════════════════════════════════════
# 6. Pipeline seam: boundary contracts between resolver and renderers
# ═══════════════════════════════════════════════════════════════════════════


class TestPipelineSeamContracts:
    """Verify resolver output shape matches renderer input expectations."""

    def test_resolver_plan_provider_matches_renderer_expectation(self) -> None:
        """resolve_render_plan provider arg → plan.provider → renderer accepts."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        for provider in ("claude", "codex"):
            result = resolve_render_plan(org, "dev", provider)
            for plan in result.plans:
                assert plan.provider == provider

    def test_resolver_produces_tuples_not_lists(self) -> None:
        """Renderer relies on tuple immutability from resolver output."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        result = resolve_render_plan(org, "dev", "claude")
        assert isinstance(result.plans, tuple)
        assert isinstance(result.diagnostics, tuple)
        for plan in result.plans:
            assert isinstance(plan.bindings, tuple)
            assert isinstance(plan.skipped, tuple)
            assert isinstance(plan.effective_artifacts, tuple)

    def test_wrong_provider_plan_to_renderer_produces_warning(
        self, workspace: Path
    ) -> None:
        """Feeding a Claude plan to the Codex renderer is a no-op with warning."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        claude_result = resolve_render_plan(org, "dev", "claude")
        plan = claude_result.plans[0]

        # Feed Claude plan to Codex renderer
        codex_render = render_codex_artifacts(plan, workspace)
        assert len(codex_render.warnings) > 0
        assert any("not 'codex'" in w for w in codex_render.warnings)
        assert codex_render.rendered_paths == ()

    def test_wrong_provider_plan_to_claude_renderer_produces_warning(
        self, workspace: Path
    ) -> None:
        """Feeding a Codex plan to the Claude renderer is a no-op with warning."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        codex_result = resolve_render_plan(org, "dev", "codex")
        plan = codex_result.plans[0]

        claude_render = render_claude_artifacts(plan, workspace)
        assert len(claude_render.warnings) > 0
        assert any("not 'claude'" in w for w in claude_render.warnings)
        assert claude_render.rendered_paths == ()

    def test_bindings_have_provider_field_matching_plan(self) -> None:
        """All bindings in a resolved plan have provider == plan.provider."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        for provider in ("claude", "codex"):
            result = resolve_render_plan(org, "dev", provider)
            for plan in result.plans:
                for binding in plan.bindings:
                    assert binding.provider == provider


class TestMultiBundlePipeline:
    """Multiple bundles enabled for a single team."""

    def test_multiple_bundles_produce_multiple_plans(self) -> None:
        org = _org(
            profiles={
                "dev": _team("dev", bundles=("core-tools", "provider-native")),
            },
            catalog=_SHARED_CATALOG,
        )
        result = resolve_render_plan(org, "dev", "claude")
        assert len(result.plans) == 2
        assert result.plans[0].bundle_id == "core-tools"
        assert result.plans[1].bundle_id == "provider-native"

    def test_multi_bundle_renders_all_files(self, workspace: Path) -> None:
        """Each plan renders independently, files accumulate in workspace."""
        org = _org(
            profiles={
                "dev": _team("dev", bundles=("core-tools", "provider-native")),
            },
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans

        all_paths: list[Path] = []
        for plan in plans:
            result = render_claude_artifacts(plan, workspace)
            all_paths.extend(result.rendered_paths)

        # core-tools: 2 skills + 1 settings file = 3 paths
        # provider-native: 1 hooks file = 1 path
        assert len(all_paths) >= 3

    def test_multi_bundle_codex_renders_all_files(self, workspace: Path) -> None:
        org = _org(
            profiles={
                "dev": _team("dev", bundles=("core-tools", "provider-native")),
            },
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "codex").plans

        all_paths: list[Path] = []
        for plan in plans:
            result = render_codex_artifacts(plan, workspace)
            all_paths.extend(result.rendered_paths)

        # core-tools: 2 skills + 1 mcp audit file = 3 paths
        # provider-native: 1 rules file = 1 path
        assert len(all_paths) >= 3


class TestCrossProviderEquivalence:
    """Same bundle → same effective artifacts but different file trees."""

    def test_same_effective_artifacts_different_file_trees(
        self, workspace: Path
    ) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )
        claude_plans = resolve_render_plan(org, "dev", "claude").plans
        codex_plans = resolve_render_plan(org, "dev", "codex").plans

        # Same effective artifacts
        assert set(claude_plans[0].effective_artifacts) == set(
            codex_plans[0].effective_artifacts
        )

        ws_claude = workspace / "claude-ws"
        ws_codex = workspace / "codex-ws"
        ws_claude.mkdir()
        ws_codex.mkdir()

        claude_result = render_claude_artifacts(claude_plans[0], ws_claude)
        codex_result = render_codex_artifacts(codex_plans[0], ws_codex)

        # Both produce rendered paths, but they're different
        assert len(claude_result.rendered_paths) > 0
        assert len(codex_result.rendered_paths) > 0

        # No path overlap — different directory structures
        claude_rel = {str(p.relative_to(ws_claude)) for p in claude_result.rendered_paths}
        codex_rel = {str(p.relative_to(ws_codex)) for p in codex_result.rendered_paths}
        assert claude_rel.isdisjoint(codex_rel), (
            f"File paths should differ between providers: "
            f"overlap = {claude_rel & codex_rel}"
        )

    def test_idempotent_rendering_across_double_resolve(
        self, workspace: Path
    ) -> None:
        """Resolving + rendering twice produces identical file content."""
        org = _org(
            profiles={"dev": _team("dev", bundles=("core-tools",))},
            catalog=_SHARED_CATALOG,
        )

        ws1 = workspace / "run1"
        ws2 = workspace / "run2"
        ws1.mkdir()
        ws2.mkdir()

        for ws in (ws1, ws2):
            plans = resolve_render_plan(org, "dev", "claude").plans
            render_claude_artifacts(plans[0], ws)

        # Compare all files byte-for-byte
        files1 = sorted(ws1.rglob("*"), key=lambda p: str(p.relative_to(ws1)))
        files2 = sorted(ws2.rglob("*"), key=lambda p: str(p.relative_to(ws2)))

        file_rels_1 = [str(f.relative_to(ws1)) for f in files1 if f.is_file()]
        file_rels_2 = [str(f.relative_to(ws2)) for f in files2 if f.is_file()]
        assert file_rels_1 == file_rels_2

        for f1, f2 in zip(
            [f for f in files1 if f.is_file()],
            [f for f in files2 if f.is_file()],
        ):
            assert f1.read_bytes() == f2.read_bytes(), (
                f"Files differ: {f1.relative_to(ws1)}"
            )


class TestMixedBundleAsymmetry:
    """Mixed bundle with both shared and provider-specific artifacts."""

    def test_mixed_bundle_claude_sees_hooks_not_rules(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans
        plan = plans[0]

        assert "review-skill" in plan.effective_artifacts
        assert "github-mcp" in plan.effective_artifacts
        assert "claude-hooks" in plan.effective_artifacts
        assert "codex-rules" in plan.skipped

    def test_mixed_bundle_codex_sees_rules_not_hooks(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "codex").plans
        plan = plans[0]

        assert "review-skill" in plan.effective_artifacts
        assert "github-mcp" in plan.effective_artifacts
        assert "codex-rules" in plan.effective_artifacts
        assert "claude-hooks" in plan.skipped

    def test_mixed_bundle_full_render_claude(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans
        result = render_claude_artifacts(plans[0], workspace)

        # Should have: skill file + hooks file + settings audit file
        assert len(result.rendered_paths) >= 2
        assert len(result.warnings) == 0

    def test_mixed_bundle_full_render_codex(self, workspace: Path) -> None:
        org = _org(
            profiles={"dev": _team("dev", bundles=("mixed-bundle",))},
            catalog=_SHARED_CATALOG,
        )
        plans = resolve_render_plan(org, "dev", "codex").plans
        result = render_codex_artifacts(plans[0], workspace)

        # Should have: skill file + rules file + mcp audit file
        assert len(result.rendered_paths) >= 2
        assert len(result.warnings) == 0


class TestDisabledAndFilteredArtifacts:
    """Install intent filtering propagates through the full pipeline."""

    def test_disabled_artifact_excluded_from_both_plans(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "active-skill": _skill("active-skill"),
                "dead-skill": _skill(
                    "dead-skill", intent=ArtifactInstallIntent.DISABLED
                ),
            },
            bindings={
                "active-skill": (
                    ProviderArtifactBinding(
                        provider="claude", native_ref="skills/active"
                    ),
                    ProviderArtifactBinding(
                        provider="codex", native_ref="skills/active"
                    ),
                ),
                "dead-skill": (
                    ProviderArtifactBinding(
                        provider="claude", native_ref="skills/dead"
                    ),
                    ProviderArtifactBinding(
                        provider="codex", native_ref="skills/dead"
                    ),
                ),
            },
            bundles={
                "test-bundle": ArtifactBundle(
                    name="test-bundle",
                    artifacts=("active-skill", "dead-skill"),
                ),
            },
        )
        org = _org(
            profiles={"dev": _team("dev", bundles=("test-bundle",))},
            catalog=catalog,
        )

        for provider in ("claude", "codex"):
            result = resolve_render_plan(org, "dev", provider)
            plan = result.plans[0]
            assert "active-skill" in plan.effective_artifacts
            assert "dead-skill" not in plan.effective_artifacts
            assert "dead-skill" in plan.skipped

    def test_disabled_artifact_produces_no_files(self, workspace: Path) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "dead-skill": _skill(
                    "dead-skill", intent=ArtifactInstallIntent.DISABLED
                ),
            },
            bindings={
                "dead-skill": (
                    ProviderArtifactBinding(
                        provider="claude", native_ref="skills/dead"
                    ),
                ),
            },
            bundles={
                "test-bundle": ArtifactBundle(
                    name="test-bundle",
                    artifacts=("dead-skill",),
                ),
            },
        )
        org = _org(
            profiles={"dev": _team("dev", bundles=("test-bundle",))},
            catalog=catalog,
        )
        plans = resolve_render_plan(org, "dev", "claude").plans
        result = render_claude_artifacts(plans[0], workspace)
        # No files rendered — the only artifact was disabled
        assert result.rendered_paths == ()

    def test_request_only_excluded_from_pipeline(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "request-skill": _skill(
                    "request-skill", intent=ArtifactInstallIntent.REQUEST_ONLY
                ),
            },
            bindings={
                "request-skill": (
                    ProviderArtifactBinding(
                        provider="claude", native_ref="skills/req"
                    ),
                ),
            },
            bundles={
                "test-bundle": ArtifactBundle(
                    name="test-bundle",
                    artifacts=("request-skill",),
                ),
            },
        )
        org = _org(
            profiles={"dev": _team("dev", bundles=("test-bundle",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "dev", "claude")
        plan = result.plans[0]
        assert "request-skill" not in plan.effective_artifacts
        assert "request-skill" in plan.skipped
