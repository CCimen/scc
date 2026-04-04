"""Tests for bundle resolution: compute ArtifactRenderPlan from NormalizedOrgConfig.

Covers:
- Basic resolution of single and multiple bundles
- Provider filtering (bindings present vs missing)
- Install intent filtering (disabled, request-only, required, available)
- Missing bundle / missing artifact diagnostics
- Portable artifacts (skills, MCP) with no binding still count as effective
- Native integrations without binding are skipped
- Team not found raises ValueError
- Empty enabled_bundles produces empty result
- Disabled bundle is skipped entirely
"""

from __future__ import annotations

import pytest

from scc_cli.core.bundle_resolver import (
    BundleResolutionDiagnostic,
    BundleResolutionResult,
    resolve_render_plan,
)
from scc_cli.core.errors import (
    BundleResolutionError,
    InvalidArtifactReferenceError,
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
# Helpers
# ---------------------------------------------------------------------------


def _make_org(
    *,
    profiles: dict[str, NormalizedTeamConfig] | None = None,
    catalog: GovernedArtifactsCatalog | None = None,
) -> NormalizedOrgConfig:
    return NormalizedOrgConfig(
        organization=OrganizationInfo(name="test-org"),
        profiles=profiles or {},
        governed_artifacts=catalog or GovernedArtifactsCatalog(),
    )


def _make_team(name: str, bundles: tuple[str, ...] = ()) -> NormalizedTeamConfig:
    return NormalizedTeamConfig(name=name, enabled_bundles=bundles)


# ---------------------------------------------------------------------------
# Team lookup
# ---------------------------------------------------------------------------


class TestTeamLookup:
    def test_missing_team_raises_value_error(self) -> None:
        org = _make_org(profiles={"alpha": _make_team("alpha")})
        with pytest.raises(ValueError, match="not found"):
            resolve_render_plan(org, "nonexistent", "claude")

    def test_missing_team_lists_available(self) -> None:
        org = _make_org(profiles={"alpha": _make_team("alpha"), "beta": _make_team("beta")})
        with pytest.raises(ValueError, match="alpha.*beta"):
            resolve_render_plan(org, "nonexistent", "claude")


# ---------------------------------------------------------------------------
# Empty / no bundles
# ---------------------------------------------------------------------------


class TestEmptyBundles:
    def test_no_enabled_bundles_returns_empty(self) -> None:
        org = _make_org(profiles={"team-a": _make_team("team-a")})
        result = resolve_render_plan(org, "team-a", "claude")
        assert result.plans == ()
        assert result.diagnostics == ()

    def test_empty_catalog_with_bundle_ref(self) -> None:
        """Team references a bundle but catalog is empty."""
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("missing-bundle",))},
        )
        result = resolve_render_plan(org, "team-a", "claude")
        assert len(result.plans) == 1
        assert result.plans[0].effective_artifacts == ()
        assert len(result.diagnostics) == 1
        assert "not found" in result.diagnostics[0].reason


# ---------------------------------------------------------------------------
# Basic resolution
# ---------------------------------------------------------------------------


class TestBasicResolution:
    def test_single_skill_required(self) -> None:
        """A required skill with claude binding resolves to effective + binding."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "review-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="review-skill",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bindings={
                "review-skill": (
                    ProviderArtifactBinding(provider="claude", native_ref="skills/review"),
                ),
            },
            bundles={
                "dev-bundle": ArtifactBundle(
                    name="dev-bundle",
                    artifacts=("review-skill",),
                    install_intent=ArtifactInstallIntent.AVAILABLE,
                ),
            },
        )
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("dev-bundle",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team-a", "claude")

        assert len(result.plans) == 1
        plan = result.plans[0]
        assert plan.bundle_id == "dev-bundle"
        assert plan.provider == "claude"
        assert plan.effective_artifacts == ("review-skill",)
        assert len(plan.bindings) == 1
        assert plan.bindings[0].provider == "claude"
        assert plan.skipped == ()
        assert result.diagnostics == ()

    def test_multiple_bundles(self) -> None:
        """Two bundles produce two plans."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "skill-a": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="skill-a",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
                "skill-b": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="skill-b",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bindings={},
            bundles={
                "bundle-1": ArtifactBundle(
                    name="bundle-1",
                    artifacts=("skill-a",),
                ),
                "bundle-2": ArtifactBundle(
                    name="bundle-2",
                    artifacts=("skill-b",),
                ),
            },
        )
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("bundle-1", "bundle-2"))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team-a", "claude")
        assert len(result.plans) == 2
        assert result.plans[0].bundle_id == "bundle-1"
        assert result.plans[1].bundle_id == "bundle-2"

    def test_multiple_artifact_kinds_in_bundle(self) -> None:
        """Bundle with skill + mcp_server + native_integration."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "my-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="my-skill",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
                "github-mcp": GovernedArtifact(
                    kind=ArtifactKind.MCP_SERVER,
                    name="github-mcp",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
                "github-native": GovernedArtifact(
                    kind=ArtifactKind.NATIVE_INTEGRATION,
                    name="github-native",
                    install_intent=ArtifactInstallIntent.AVAILABLE,
                ),
            },
            bindings={
                "my-skill": (
                    ProviderArtifactBinding(provider="claude", native_ref="skills/my"),
                ),
                "github-mcp": (
                    ProviderArtifactBinding(provider="claude", native_ref="mcp/github"),
                ),
                "github-native": (
                    ProviderArtifactBinding(
                        provider="claude",
                        native_config={"hooks": "./claude/hooks.json"},
                    ),
                ),
            },
            bundles={
                "github-dev": ArtifactBundle(
                    name="github-dev",
                    artifacts=("my-skill", "github-mcp", "github-native"),
                ),
            },
        )
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("github-dev",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team-a", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ("my-skill", "github-mcp", "github-native")
        assert len(plan.bindings) == 3
        assert plan.skipped == ()


# ---------------------------------------------------------------------------
# Provider filtering
# ---------------------------------------------------------------------------


class TestProviderFiltering:
    def test_binding_only_for_other_provider(self) -> None:
        """Native integration with only codex binding is skipped for claude."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "codex-only": GovernedArtifact(
                    kind=ArtifactKind.NATIVE_INTEGRATION,
                    name="codex-only",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bindings={
                "codex-only": (
                    ProviderArtifactBinding(provider="codex", native_ref="plugins/codex"),
                ),
            },
            bundles={
                "test-bundle": ArtifactBundle(
                    name="test-bundle",
                    artifacts=("codex-only",),
                ),
            },
        )
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("test-bundle",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team-a", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ()
        assert plan.skipped == ("codex-only",)
        assert len(result.diagnostics) == 1
        assert "no binding for provider 'claude'" in result.diagnostics[0].reason

    def test_skill_without_binding_still_effective(self) -> None:
        """Skills are portable — they count as effective even without a binding."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "portable-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="portable-skill",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bindings={},  # no bindings at all
            bundles={
                "test-bundle": ArtifactBundle(
                    name="test-bundle",
                    artifacts=("portable-skill",),
                ),
            },
        )
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("test-bundle",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team-a", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ("portable-skill",)
        assert plan.skipped == ()

    def test_mcp_server_without_binding_still_effective(self) -> None:
        """MCP servers are portable — effective even without provider binding."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "generic-mcp": GovernedArtifact(
                    kind=ArtifactKind.MCP_SERVER,
                    name="generic-mcp",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bindings={},
            bundles={
                "test-bundle": ArtifactBundle(
                    name="test-bundle",
                    artifacts=("generic-mcp",),
                ),
            },
        )
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("test-bundle",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team-a", "codex")
        plan = result.plans[0]
        assert plan.effective_artifacts == ("generic-mcp",)

    def test_both_providers_have_bindings(self) -> None:
        """Each provider gets only its own bindings."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "github-native": GovernedArtifact(
                    kind=ArtifactKind.NATIVE_INTEGRATION,
                    name="github-native",
                    install_intent=ArtifactInstallIntent.AVAILABLE,
                ),
            },
            bindings={
                "github-native": (
                    ProviderArtifactBinding(
                        provider="claude",
                        native_config={"hooks": "./claude/github-hooks.json"},
                    ),
                    ProviderArtifactBinding(
                        provider="codex",
                        native_config={"rules": "./codex/rules/github.rules"},
                    ),
                ),
            },
            bundles={
                "github": ArtifactBundle(
                    name="github",
                    artifacts=("github-native",),
                ),
            },
        )
        org = _make_org(
            profiles={"team-a": _make_team("team-a", bundles=("github",))},
            catalog=catalog,
        )

        claude_result = resolve_render_plan(org, "team-a", "claude")
        codex_result = resolve_render_plan(org, "team-a", "codex")

        assert len(claude_result.plans[0].bindings) == 1
        assert claude_result.plans[0].bindings[0].provider == "claude"

        assert len(codex_result.plans[0].bindings) == 1
        assert codex_result.plans[0].bindings[0].provider == "codex"


# ---------------------------------------------------------------------------
# Install intent filtering
# ---------------------------------------------------------------------------


class TestInstallIntentFiltering:
    def test_disabled_artifact_skipped(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "blocked-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="blocked-skill",
                    install_intent=ArtifactInstallIntent.DISABLED,
                ),
            },
            bindings={},
            bundles={
                "test": ArtifactBundle(name="test", artifacts=("blocked-skill",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("test",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ()
        assert plan.skipped == ("blocked-skill",)
        assert any("disabled" in d.reason for d in result.diagnostics)

    def test_request_only_artifact_skipped(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "pending-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="pending-skill",
                    install_intent=ArtifactInstallIntent.REQUEST_ONLY,
                ),
            },
            bindings={},
            bundles={
                "test": ArtifactBundle(name="test", artifacts=("pending-skill",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("test",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ()
        assert plan.skipped == ("pending-skill",)
        assert any("request-only" in d.reason for d in result.diagnostics)

    def test_required_artifact_included(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "req-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="req-skill",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bindings={},
            bundles={
                "test": ArtifactBundle(name="test", artifacts=("req-skill",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("test",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert result.plans[0].effective_artifacts == ("req-skill",)

    def test_available_artifact_included(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "avail-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="avail-skill",
                    install_intent=ArtifactInstallIntent.AVAILABLE,
                ),
            },
            bindings={},
            bundles={
                "test": ArtifactBundle(name="test", artifacts=("avail-skill",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("test",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert result.plans[0].effective_artifacts == ("avail-skill",)


# ---------------------------------------------------------------------------
# Disabled bundle
# ---------------------------------------------------------------------------


class TestDisabledBundle:
    def test_disabled_bundle_skipped_entirely(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "good-skill": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="good-skill",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bindings={},
            bundles={
                "disabled-bundle": ArtifactBundle(
                    name="disabled-bundle",
                    artifacts=("good-skill",),
                    install_intent=ArtifactInstallIntent.DISABLED,
                ),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("disabled-bundle",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ()
        assert plan.bindings == ()
        assert len(result.diagnostics) == 1
        assert "disabled" in result.diagnostics[0].reason


# ---------------------------------------------------------------------------
# Missing artifact in bundle
# ---------------------------------------------------------------------------


class TestMissingArtifact:
    def test_artifact_not_in_catalog(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={},
            bindings={},
            bundles={
                "test": ArtifactBundle(name="test", artifacts=("ghost-artifact",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("test",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ()
        assert plan.skipped == ("ghost-artifact",)
        assert any("not found" in d.reason for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Config normalization round-trip
# ---------------------------------------------------------------------------


class TestConfigNormalization:
    """Verify governed_artifacts and enabled_bundles survive normalization."""

    def test_normalizer_round_trip(self) -> None:
        """Raw org config with governed_artifacts section normalizes correctly."""
        raw = {
            "organization": {"name": "test-org"},
            "governed_artifacts": {
                "artifacts": {
                    "code-review-skill": {
                        "kind": "skill",
                        "source": {
                            "type": "git",
                            "url": "https://git.example.se/ai/artifacts.git",
                            "path": "skills/code-review",
                            "ref": "v1.4.2",
                        },
                        "install_intent": "required",
                    },
                    "github-native": {
                        "kind": "native_integration",
                        "install_intent": "available",
                        "bindings": {
                            "claude": {
                                "hooks": "./claude/github-hooks.json",
                                "marketplace_bundle": "./claude/github-marketplace",
                            },
                            "codex": {
                                "plugin_bundle": "./codex/github-plugin",
                                "rules": "./codex/rules/github.rules",
                            },
                        },
                    },
                },
                "bundles": {
                    "github-dev": {
                        "members": ["code-review-skill", "github-native"],
                        "install_intent": "available",
                    },
                },
            },
            "profiles": {
                "ai-team": {
                    "enabled_bundles": ["github-dev"],
                },
            },
        }
        org = NormalizedOrgConfig.from_dict(raw)

        # Catalog populated
        assert "code-review-skill" in org.governed_artifacts.artifacts
        assert "github-native" in org.governed_artifacts.artifacts
        assert "github-dev" in org.governed_artifacts.bundles

        # Artifact fields
        skill = org.governed_artifacts.artifacts["code-review-skill"]
        assert skill.kind == ArtifactKind.SKILL
        assert skill.install_intent == ArtifactInstallIntent.REQUIRED
        assert skill.source_type == "git"
        assert skill.source_ref == "v1.4.2"

        # Bindings
        native_bindings = org.governed_artifacts.bindings.get("github-native", ())
        assert len(native_bindings) == 2
        providers = {b.provider for b in native_bindings}
        assert providers == {"claude", "codex"}

        # Bundle
        bundle = org.governed_artifacts.bundles["github-dev"]
        assert bundle.artifacts == ("code-review-skill", "github-native")
        assert bundle.install_intent == ArtifactInstallIntent.AVAILABLE

        # Team enabled_bundles
        team = org.get_profile("ai-team")
        assert team is not None
        assert team.enabled_bundles == ("github-dev",)

    def test_normalizer_empty_governed_artifacts(self) -> None:
        """Org config with no governed_artifacts section produces empty catalog."""
        raw = {"organization": {"name": "test-org"}}
        org = NormalizedOrgConfig.from_dict(raw)
        assert org.governed_artifacts.artifacts == {}
        assert org.governed_artifacts.bundles == {}
        assert org.governed_artifacts.bindings == {}

    def test_full_resolution_from_raw_config(self) -> None:
        """End-to-end: raw config → normalization → bundle resolution."""
        raw = {
            "organization": {"name": "test-org"},
            "governed_artifacts": {
                "artifacts": {
                    "my-skill": {
                        "kind": "skill",
                        "install_intent": "required",
                    },
                    "claude-hooks": {
                        "kind": "native_integration",
                        "install_intent": "available",
                        "bindings": {
                            "claude": {"hooks": "./hooks.json"},
                        },
                    },
                },
                "bundles": {
                    "my-bundle": {
                        "members": ["my-skill", "claude-hooks"],
                    },
                },
            },
            "profiles": {
                "dev-team": {
                    "enabled_bundles": ["my-bundle"],
                },
            },
        }
        org = NormalizedOrgConfig.from_dict(raw)

        # Claude gets both
        claude_result = resolve_render_plan(org, "dev-team", "claude")
        assert len(claude_result.plans) == 1
        assert claude_result.plans[0].effective_artifacts == ("my-skill", "claude-hooks")

        # Codex gets skill but not claude-native integration
        codex_result = resolve_render_plan(org, "dev-team", "codex")
        assert len(codex_result.plans) == 1
        assert codex_result.plans[0].effective_artifacts == ("my-skill",)
        assert codex_result.plans[0].skipped == ("claude-hooks",)


# ---------------------------------------------------------------------------
# Return type shape
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Fail-closed mode
# ---------------------------------------------------------------------------


class TestFailClosedMissingBundle:
    def test_missing_bundle_raises_bundle_resolution_error(self) -> None:
        """fail_closed=True: missing bundle ID raises BundleResolutionError."""
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("nonexistent",))},
        )
        with pytest.raises(BundleResolutionError, match="nonexistent"):
            resolve_render_plan(org, "t", "claude", fail_closed=True)

    def test_missing_bundle_error_has_available_bundles(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={
                "alpha": ArtifactBundle(name="alpha", artifacts=()),
                "beta": ArtifactBundle(name="beta", artifacts=()),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("ghost",))},
            catalog=catalog,
        )
        with pytest.raises(BundleResolutionError) as exc_info:
            resolve_render_plan(org, "t", "codex", fail_closed=True)
        err = exc_info.value
        assert "alpha" in err.available_bundles
        assert "beta" in err.available_bundles
        assert err.bundle_id == "ghost"

    def test_missing_bundle_error_has_structured_user_message(self) -> None:
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("gone",))},
        )
        with pytest.raises(BundleResolutionError) as exc_info:
            resolve_render_plan(org, "t", "claude", fail_closed=True)
        assert "gone" in str(exc_info.value)

    def test_missing_bundle_soft_mode_still_produces_diagnostic(self) -> None:
        """Default (fail_closed=False) still returns diagnostics, not errors."""
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("missing",))},
        )
        result = resolve_render_plan(org, "t", "claude")
        assert len(result.diagnostics) == 1
        assert "not found" in result.diagnostics[0].reason


class TestFailClosedInvalidArtifact:
    def test_invalid_artifact_ref_raises_error(self) -> None:
        """fail_closed=True: artifact not in catalog → InvalidArtifactReferenceError."""
        catalog = GovernedArtifactsCatalog(
            bundles={
                "b": ArtifactBundle(name="b", artifacts=("ghost-artifact",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("b",))},
            catalog=catalog,
        )
        with pytest.raises(InvalidArtifactReferenceError, match="ghost-artifact"):
            resolve_render_plan(org, "t", "claude", fail_closed=True)

    def test_invalid_artifact_error_has_bundle_id(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={
                "my-bundle": ArtifactBundle(name="my-bundle", artifacts=("missing-art",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("my-bundle",))},
            catalog=catalog,
        )
        with pytest.raises(InvalidArtifactReferenceError) as exc_info:
            resolve_render_plan(org, "t", "claude", fail_closed=True)
        assert exc_info.value.bundle_id == "my-bundle"
        assert exc_info.value.artifact_name == "missing-art"

    def test_disabled_bundle_in_fail_closed_mode_skips_not_raises(self) -> None:
        """Disabled bundles produce diagnostics even in fail_closed mode."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "s": GovernedArtifact(
                    kind=ArtifactKind.SKILL, name="s",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bundles={
                "dis": ArtifactBundle(
                    name="dis", artifacts=("s",),
                    install_intent=ArtifactInstallIntent.DISABLED,
                ),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("dis",))},
            catalog=catalog,
        )
        # Should NOT raise — disabled is an audit skip, not a failure
        result = resolve_render_plan(org, "t", "claude", fail_closed=True)
        assert len(result.diagnostics) == 1
        assert "disabled" in result.diagnostics[0].reason


# ---------------------------------------------------------------------------
# Error hierarchy structure
# ---------------------------------------------------------------------------


class TestErrorHierarchy:
    def test_bundle_resolution_error_is_renderer_error(self) -> None:
        from scc_cli.core.errors import RendererError
        err = BundleResolutionError(bundle_id="b")
        assert isinstance(err, RendererError)

    def test_invalid_artifact_error_is_renderer_error(self) -> None:
        from scc_cli.core.errors import RendererError
        err = InvalidArtifactReferenceError(bundle_id="b", artifact_name="a", reason="bad")
        assert isinstance(err, RendererError)

    def test_renderer_error_has_exit_code_4(self) -> None:
        from scc_cli.core.errors import RendererError
        err = RendererError(user_message="test")
        assert err.exit_code == 4


class TestReturnTypes:
    def test_result_is_bundle_resolution_result(self) -> None:
        org = _make_org(profiles={"t": _make_team("t")})
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result, BundleResolutionResult)

    def test_plan_is_artifact_render_plan(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "s": GovernedArtifact(
                    kind=ArtifactKind.SKILL,
                    name="s",
                    install_intent=ArtifactInstallIntent.REQUIRED,
                ),
            },
            bundles={
                "b": ArtifactBundle(name="b", artifacts=("s",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("b",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result.plans[0], ArtifactRenderPlan)

    def test_diagnostic_is_typed(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={
                "b": ArtifactBundle(name="b", artifacts=("missing",)),
            },
        )
        org = _make_org(
            profiles={"t": _make_team("t", bundles=("b",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result.diagnostics[0], BundleResolutionDiagnostic)
