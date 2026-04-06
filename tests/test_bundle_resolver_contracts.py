"""Contract tests for bundle resolution and render plan computation.

These tests exercise the public contract of ``resolve_render_plan()`` and
``_resolve_single_bundle()`` to ensure the planning pipeline meets its
documented behavior guarantees:

1. Happy path → complete ArtifactRenderPlan with correct bindings
2. Multi-bundle → artifacts per-bundle, ordered as declared
3. Shared artifacts → skill + MCP in plan for both providers
4. Provider-specific → native_integration appears for matching provider only
5. Install intent filtering → disabled excluded, required included, available preserved
6. Missing bundle → clear error with available bundles
7. Missing artifact in bundle → partial resolution with skip report
8. Empty team config → empty plan, no error
9. Structural contracts → return types, immutability, tuple shapes
"""

from __future__ import annotations

import pytest

from scc_cli.core.bundle_resolver import (
    BundleResolutionDiagnostic,
    BundleResolutionResult,
    _resolve_single_bundle,
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
# Fixture helpers
# ---------------------------------------------------------------------------


def _org(
    *,
    profiles: dict[str, NormalizedTeamConfig] | None = None,
    catalog: GovernedArtifactsCatalog | None = None,
) -> NormalizedOrgConfig:
    return NormalizedOrgConfig(
        organization=OrganizationInfo(name="contract-test-org"),
        profiles=profiles or {},
        governed_artifacts=catalog or GovernedArtifactsCatalog(),
    )


def _team(name: str, bundles: tuple[str, ...] = ()) -> NormalizedTeamConfig:
    return NormalizedTeamConfig(name=name, enabled_bundles=bundles)


def _skill(
    name: str, intent: ArtifactInstallIntent = ArtifactInstallIntent.REQUIRED
) -> GovernedArtifact:
    return GovernedArtifact(kind=ArtifactKind.SKILL, name=name, install_intent=intent)


def _mcp(
    name: str, intent: ArtifactInstallIntent = ArtifactInstallIntent.REQUIRED
) -> GovernedArtifact:
    return GovernedArtifact(kind=ArtifactKind.MCP_SERVER, name=name, install_intent=intent)


def _native(
    name: str, intent: ArtifactInstallIntent = ArtifactInstallIntent.AVAILABLE
) -> GovernedArtifact:
    return GovernedArtifact(kind=ArtifactKind.NATIVE_INTEGRATION, name=name, install_intent=intent)


# ---------------------------------------------------------------------------
# Reusable catalog: a realistic bundle with all artifact kinds
# ---------------------------------------------------------------------------

_FULL_CATALOG = GovernedArtifactsCatalog(
    artifacts={
        "review-skill": _skill("review-skill"),
        "lint-skill": _skill("lint-skill"),
        "github-mcp": _mcp("github-mcp"),
        "jira-mcp": _mcp("jira-mcp"),
        "claude-hooks": _native("claude-hooks"),
        "codex-rules": _native("codex-rules"),
        "shared-native": _native("shared-native"),
    },
    bindings={
        "review-skill": (
            ProviderArtifactBinding(provider="claude", native_ref="skills/review"),
            ProviderArtifactBinding(provider="codex", native_ref="skills/review"),
        ),
        "github-mcp": (ProviderArtifactBinding(provider="claude", native_ref="mcp/github"),),
        "claude-hooks": (
            ProviderArtifactBinding(
                provider="claude",
                native_config={"hooks": "./claude/hooks.json"},
            ),
        ),
        "codex-rules": (
            ProviderArtifactBinding(
                provider="codex",
                native_config={"rules": "./codex/github.rules"},
            ),
        ),
        "shared-native": (
            ProviderArtifactBinding(
                provider="claude",
                native_config={"hooks": "./claude/shared-hooks.json"},
            ),
            ProviderArtifactBinding(
                provider="codex",
                native_config={"rules": "./codex/shared.rules"},
            ),
        ),
    },
    bundles={
        "dev-essentials": ArtifactBundle(
            name="dev-essentials",
            artifacts=("review-skill", "lint-skill", "github-mcp"),
            install_intent=ArtifactInstallIntent.AVAILABLE,
        ),
        "github-integration": ArtifactBundle(
            name="github-integration",
            artifacts=("github-mcp", "claude-hooks", "codex-rules", "shared-native"),
            install_intent=ArtifactInstallIntent.AVAILABLE,
        ),
        "empty-bundle": ArtifactBundle(
            name="empty-bundle",
            artifacts=(),
            install_intent=ArtifactInstallIntent.AVAILABLE,
        ),
    },
)


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 1: Happy path — complete ArtifactRenderPlan
# ═══════════════════════════════════════════════════════════════════════════════


class TestHappyPathContract:
    """Team with enabled bundles → complete ArtifactRenderPlan with correct
    bindings and effective_artifacts."""

    def test_plan_has_correct_bundle_id(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert result.plans[0].bundle_id == "dev-essentials"

    def test_plan_has_correct_provider(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert result.plans[0].provider == "claude"

    def test_effective_artifacts_match_bundle_contents(self) -> None:
        """All artifacts with compatible intent appear as effective."""
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        plan = result.plans[0]
        # dev-essentials has: review-skill, lint-skill, github-mcp — all REQUIRED
        assert plan.effective_artifacts == ("review-skill", "lint-skill", "github-mcp")

    def test_bindings_match_provider(self) -> None:
        """Every binding in the plan targets the requested provider."""
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        for binding in result.plans[0].bindings:
            assert binding.provider == "claude"

    def test_bindings_count_matches_provider_bindings(self) -> None:
        """Binding count equals catalog bindings for the provider."""
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        plan = result.plans[0]
        # review-skill has claude binding, lint-skill has none, github-mcp has claude binding
        assert len(plan.bindings) == 2

    def test_no_diagnostics_on_clean_resolution(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert result.diagnostics == ()

    def test_no_skipped_artifacts_on_clean_resolution(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert result.plans[0].skipped == ()


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 2: Multi-bundle — artifacts per bundle, ordered
# ═══════════════════════════════════════════════════════════════════════════════


class TestMultiBundleContract:
    """Team enables multiple bundles → one plan per bundle, artifacts ordered
    as declared in the bundle definition."""

    def test_one_plan_per_enabled_bundle(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials", "github-integration"))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert len(result.plans) == 2

    def test_plans_ordered_as_enabled_bundles(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("github-integration", "dev-essentials"))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert result.plans[0].bundle_id == "github-integration"
        assert result.plans[1].bundle_id == "dev-essentials"

    def test_artifacts_ordered_as_declared_in_bundle(self) -> None:
        """Effective artifacts preserve the order from the bundle definition."""
        org = _org(
            profiles={"team": _team("team", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        plan = result.plans[0]
        # Bundle declares: review-skill, lint-skill, github-mcp
        assert plan.effective_artifacts == ("review-skill", "lint-skill", "github-mcp")

    def test_each_bundle_resolves_independently(self) -> None:
        """Same artifact in two bundles appears in both plans (no cross-bundle dedup)."""
        catalog = GovernedArtifactsCatalog(
            artifacts={"shared": _skill("shared")},
            bindings={},
            bundles={
                "a": ArtifactBundle(name="a", artifacts=("shared",)),
                "b": ArtifactBundle(name="b", artifacts=("shared",)),
            },
        )
        org = _org(
            profiles={"team": _team("team", bundles=("a", "b"))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert result.plans[0].effective_artifacts == ("shared",)
        assert result.plans[1].effective_artifacts == ("shared",)

    def test_diagnostics_aggregated_across_bundles(self) -> None:
        """Diagnostics from multiple bundles are collected into one result."""
        catalog = GovernedArtifactsCatalog(
            artifacts={},
            bindings={},
            bundles={
                "a": ArtifactBundle(name="a", artifacts=("ghost-1",)),
                "b": ArtifactBundle(name="b", artifacts=("ghost-2",)),
            },
        )
        org = _org(
            profiles={"team": _team("team", bundles=("a", "b"))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert len(result.diagnostics) == 2
        names = {d.artifact_name for d in result.diagnostics}
        assert names == {"ghost-1", "ghost-2"}


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 3: Shared artifacts — portable across providers
# ═══════════════════════════════════════════════════════════════════════════════


class TestSharedArtifactContract:
    """Skill and MCP artifacts appear in plan for both providers — they are
    portable and do not require provider-specific bindings."""

    def test_skill_effective_for_both_providers(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"portable-skill": _skill("portable-skill")},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("portable-skill",))},
        )
        org = _org(
            profiles={"team": _team("team", bundles=("b",))},
            catalog=catalog,
        )
        claude = resolve_render_plan(org, "team", "claude")
        codex = resolve_render_plan(org, "team", "codex")
        assert claude.plans[0].effective_artifacts == ("portable-skill",)
        assert codex.plans[0].effective_artifacts == ("portable-skill",)

    def test_mcp_effective_for_both_providers(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"portable-mcp": _mcp("portable-mcp")},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("portable-mcp",))},
        )
        org = _org(
            profiles={"team": _team("team", bundles=("b",))},
            catalog=catalog,
        )
        claude = resolve_render_plan(org, "team", "claude")
        codex = resolve_render_plan(org, "team", "codex")
        assert claude.plans[0].effective_artifacts == ("portable-mcp",)
        assert codex.plans[0].effective_artifacts == ("portable-mcp",)

    def test_skill_without_binding_has_empty_bindings_list(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"no-bind-skill": _skill("no-bind-skill")},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("no-bind-skill",))},
        )
        org = _org(
            profiles={"team": _team("team", bundles=("b",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "team", "claude")
        assert result.plans[0].bindings == ()
        assert result.plans[0].effective_artifacts == ("no-bind-skill",)

    def test_mcp_with_one_provider_binding_collects_only_matching(self) -> None:
        """MCP with only a claude binding: effective for both, but codex gets
        no bindings while claude gets one."""
        catalog = GovernedArtifactsCatalog(
            artifacts={"github-mcp": _mcp("github-mcp")},
            bindings={
                "github-mcp": (
                    ProviderArtifactBinding(provider="claude", native_ref="mcp/github"),
                ),
            },
            bundles={"b": ArtifactBundle(name="b", artifacts=("github-mcp",))},
        )
        org = _org(
            profiles={"team": _team("team", bundles=("b",))},
            catalog=catalog,
        )
        claude = resolve_render_plan(org, "team", "claude")
        codex = resolve_render_plan(org, "team", "codex")
        # Both see the artifact as effective (MCP is portable)
        assert claude.plans[0].effective_artifacts == ("github-mcp",)
        assert codex.plans[0].effective_artifacts == ("github-mcp",)
        # Only claude gets the binding
        assert len(claude.plans[0].bindings) == 1
        assert len(codex.plans[0].bindings) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 4: Provider-specific — native_integration binding
# ═══════════════════════════════════════════════════════════════════════════════


class TestProviderSpecificContract:
    """Native integrations require a provider-specific binding. They appear
    for the matching provider and are skipped for others."""

    def test_native_with_claude_binding_effective_for_claude(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("github-integration",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        plan = result.plans[0]
        assert "claude-hooks" in plan.effective_artifacts
        assert "claude-hooks" not in plan.skipped

    def test_native_with_claude_binding_skipped_for_codex(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("github-integration",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "codex")
        plan = result.plans[0]
        assert "claude-hooks" in plan.skipped
        assert "claude-hooks" not in plan.effective_artifacts

    def test_native_with_codex_binding_effective_for_codex(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("github-integration",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "codex")
        plan = result.plans[0]
        assert "codex-rules" in plan.effective_artifacts

    def test_native_with_codex_binding_skipped_for_claude(self) -> None:
        org = _org(
            profiles={"team": _team("team", bundles=("github-integration",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "claude")
        plan = result.plans[0]
        assert "codex-rules" in plan.skipped

    def test_native_with_both_bindings_effective_for_both(self) -> None:
        """shared-native has bindings for both claude and codex."""
        org = _org(
            profiles={"team": _team("team", bundles=("github-integration",))},
            catalog=_FULL_CATALOG,
        )
        claude = resolve_render_plan(org, "team", "claude")
        codex = resolve_render_plan(org, "team", "codex")
        assert "shared-native" in claude.plans[0].effective_artifacts
        assert "shared-native" in codex.plans[0].effective_artifacts

    def test_skip_diagnostic_mentions_provider(self) -> None:
        """Diagnostic for skipped native integration names the provider."""
        org = _org(
            profiles={"team": _team("team", bundles=("github-integration",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "team", "codex")
        claude_only_diags = [d for d in result.diagnostics if d.artifact_name == "claude-hooks"]
        assert len(claude_only_diags) == 1
        assert "codex" in claude_only_diags[0].reason


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 5: Install intent filtering
# ═══════════════════════════════════════════════════════════════════════════════


class TestInstallIntentContract:
    """Disabled artifacts excluded, required auto-included, available preserved,
    request-only skipped."""

    def test_required_is_effective(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"r": _skill("r", ArtifactInstallIntent.REQUIRED)},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("r",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert "r" in result.plans[0].effective_artifacts

    def test_available_is_effective(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"a": _skill("a", ArtifactInstallIntent.AVAILABLE)},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("a",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert "a" in result.plans[0].effective_artifacts

    def test_disabled_is_skipped(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"d": _skill("d", ArtifactInstallIntent.DISABLED)},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("d",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert result.plans[0].effective_artifacts == ()
        assert "d" in result.plans[0].skipped

    def test_request_only_is_skipped(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"ro": _skill("ro", ArtifactInstallIntent.REQUEST_ONLY)},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("ro",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert result.plans[0].effective_artifacts == ()
        assert "ro" in result.plans[0].skipped

    def test_disabled_diagnostic_reason(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"d": _skill("d", ArtifactInstallIntent.DISABLED)},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("d",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert any("disabled" in d.reason for d in result.diagnostics)

    def test_request_only_diagnostic_reason(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"ro": _skill("ro", ArtifactInstallIntent.REQUEST_ONLY)},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("ro",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert any("request-only" in d.reason for d in result.diagnostics)

    def test_mixed_intents_only_effective_included(self) -> None:
        """Bundle with mixed intents: only required + available in effective."""
        catalog = GovernedArtifactsCatalog(
            artifacts={
                "req": _skill("req", ArtifactInstallIntent.REQUIRED),
                "avail": _skill("avail", ArtifactInstallIntent.AVAILABLE),
                "dis": _skill("dis", ArtifactInstallIntent.DISABLED),
                "ro": _skill("ro", ArtifactInstallIntent.REQUEST_ONLY),
            },
            bindings={},
            bundles={
                "mixed": ArtifactBundle(
                    name="mixed",
                    artifacts=("req", "avail", "dis", "ro"),
                ),
            },
        )
        org = _org(
            profiles={"t": _team("t", bundles=("mixed",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ("req", "avail")
        assert set(plan.skipped) == {"dis", "ro"}

    def test_disabled_bundle_intent_skips_all_artifacts(self) -> None:
        """A disabled bundle skips resolution entirely, even for required artifacts."""
        catalog = GovernedArtifactsCatalog(
            artifacts={"s": _skill("s", ArtifactInstallIntent.REQUIRED)},
            bindings={},
            bundles={
                "dis-bundle": ArtifactBundle(
                    name="dis-bundle",
                    artifacts=("s",),
                    install_intent=ArtifactInstallIntent.DISABLED,
                ),
            },
        )
        org = _org(
            profiles={"t": _team("t", bundles=("dis-bundle",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ()
        assert plan.bindings == ()


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 6: Missing bundle reference
# ═══════════════════════════════════════════════════════════════════════════════


class TestMissingBundleContract:
    """Missing bundle → clear error message listing available bundles."""

    def test_soft_mode_produces_diagnostic(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={"real-bundle": ArtifactBundle(name="real-bundle")},
        )
        org = _org(
            profiles={"t": _team("t", bundles=("nonexistent",))},
            catalog=catalog,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert len(result.diagnostics) == 1
        assert "not found" in result.diagnostics[0].reason
        assert "real-bundle" in result.diagnostics[0].reason

    def test_soft_mode_still_returns_plan_shell(self) -> None:
        """Even a missing bundle produces a plan (with empty effective_artifacts)."""
        org = _org(profiles={"t": _team("t", bundles=("ghost",))})
        result = resolve_render_plan(org, "t", "claude")
        assert len(result.plans) == 1
        assert result.plans[0].bundle_id == "ghost"
        assert result.plans[0].effective_artifacts == ()

    def test_fail_closed_raises_bundle_resolution_error(self) -> None:
        org = _org(profiles={"t": _team("t", bundles=("missing",))})
        with pytest.raises(BundleResolutionError) as exc_info:
            resolve_render_plan(org, "t", "claude", fail_closed=True)
        assert exc_info.value.bundle_id == "missing"

    def test_fail_closed_error_lists_available_bundles(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={
                "alpha": ArtifactBundle(name="alpha"),
                "beta": ArtifactBundle(name="beta"),
                "gamma": ArtifactBundle(name="gamma"),
            },
        )
        org = _org(
            profiles={"t": _team("t", bundles=("missing",))},
            catalog=catalog,
        )
        with pytest.raises(BundleResolutionError) as exc_info:
            resolve_render_plan(org, "t", "claude", fail_closed=True)
        err = exc_info.value
        assert set(err.available_bundles) == {"alpha", "beta", "gamma"}

    def test_fail_closed_error_available_bundles_sorted(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={
                "zebra": ArtifactBundle(name="zebra"),
                "alpha": ArtifactBundle(name="alpha"),
                "middle": ArtifactBundle(name="middle"),
            },
        )
        org = _org(
            profiles={"t": _team("t", bundles=("ghost",))},
            catalog=catalog,
        )
        with pytest.raises(BundleResolutionError) as exc_info:
            resolve_render_plan(org, "t", "claude", fail_closed=True)
        assert list(exc_info.value.available_bundles) == ["alpha", "middle", "zebra"]

    def test_fail_closed_error_user_message_is_actionable(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={"real": ArtifactBundle(name="real")},
        )
        org = _org(
            profiles={"t": _team("t", bundles=("fake",))},
            catalog=catalog,
        )
        with pytest.raises(BundleResolutionError) as exc_info:
            resolve_render_plan(org, "t", "claude", fail_closed=True)
        msg = str(exc_info.value)
        assert "fake" in msg
        assert "real" in msg


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 7: Missing artifact in bundle — partial resolution
# ═══════════════════════════════════════════════════════════════════════════════


class TestMissingArtifactContract:
    """Missing artifact in bundle → partial resolution with skip report."""

    def test_valid_artifacts_still_effective(self) -> None:
        """Good artifacts resolve; only the missing one is skipped."""
        catalog = GovernedArtifactsCatalog(
            artifacts={"good": _skill("good")},
            bindings={},
            bundles={
                "b": ArtifactBundle(name="b", artifacts=("good", "ghost")),
            },
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert plan.effective_artifacts == ("good",)
        assert plan.skipped == ("ghost",)

    def test_diagnostic_names_missing_artifact(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("phantom",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert len(result.diagnostics) == 1
        assert result.diagnostics[0].artifact_name == "phantom"
        assert "not found" in result.diagnostics[0].reason

    def test_fail_closed_raises_for_missing_artifact(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"good": _skill("good")},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("good", "bad"))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        with pytest.raises(InvalidArtifactReferenceError) as exc_info:
            resolve_render_plan(org, "t", "claude", fail_closed=True)
        assert exc_info.value.artifact_name == "bad"
        assert exc_info.value.bundle_id == "b"

    def test_multiple_missing_artifacts_produce_multiple_diagnostics(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("miss-1", "miss-2", "miss-3"))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert len(result.diagnostics) == 3
        names = {d.artifact_name for d in result.diagnostics}
        assert names == {"miss-1", "miss-2", "miss-3"}


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 8: Empty team config
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmptyTeamConfigContract:
    """Empty team config → empty plan, no error."""

    def test_no_enabled_bundles(self) -> None:
        org = _org(profiles={"t": _team("t")})
        result = resolve_render_plan(org, "t", "claude")
        assert result.plans == ()
        assert result.diagnostics == ()

    def test_empty_enabled_bundles_tuple(self) -> None:
        org = _org(profiles={"t": _team("t", bundles=())})
        result = resolve_render_plan(org, "t", "claude")
        assert result.plans == ()
        assert result.diagnostics == ()

    def test_team_with_empty_bundle(self) -> None:
        """Bundle exists but has no artifacts → empty plan, no error."""
        org = _org(
            profiles={"t": _team("t", bundles=("empty-bundle",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert len(result.plans) == 1
        assert result.plans[0].effective_artifacts == ()
        assert result.plans[0].skipped == ()
        assert result.diagnostics == ()

    def test_missing_team_raises_value_error(self) -> None:
        org = _org(profiles={"alpha": _team("alpha")})
        with pytest.raises(ValueError, match="not found"):
            resolve_render_plan(org, "nonexistent", "claude")

    def test_missing_team_error_lists_available_profiles(self) -> None:
        org = _org(profiles={"dev": _team("dev"), "ops": _team("ops")})
        with pytest.raises(ValueError, match="dev"):
            resolve_render_plan(org, "ghost", "claude")


# ═══════════════════════════════════════════════════════════════════════════════
# Contract 9: Structural contracts — types, immutability, purity
# ═══════════════════════════════════════════════════════════════════════════════


class TestStructuralContract:
    """Return types, tuple immutability, and pure function guarantees."""

    def test_result_is_bundle_resolution_result(self) -> None:
        org = _org(profiles={"t": _team("t")})
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result, BundleResolutionResult)

    def test_plans_are_tuples(self) -> None:
        org = _org(
            profiles={"t": _team("t", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result.plans, tuple)

    def test_diagnostics_are_tuples(self) -> None:
        org = _org(profiles={"t": _team("t")})
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result.diagnostics, tuple)

    def test_plan_is_artifact_render_plan(self) -> None:
        org = _org(
            profiles={"t": _team("t", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result.plans[0], ArtifactRenderPlan)

    def test_plan_bindings_are_tuples(self) -> None:
        org = _org(
            profiles={"t": _team("t", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result = resolve_render_plan(org, "t", "claude")
        plan = result.plans[0]
        assert isinstance(plan.bindings, tuple)
        assert isinstance(plan.skipped, tuple)
        assert isinstance(plan.effective_artifacts, tuple)

    def test_diagnostic_is_typed(self) -> None:
        catalog = GovernedArtifactsCatalog(
            bundles={"b": ArtifactBundle(name="b", artifacts=("missing",))},
        )
        org = _org(profiles={"t": _team("t", bundles=("b",))}, catalog=catalog)
        result = resolve_render_plan(org, "t", "claude")
        assert isinstance(result.diagnostics[0], BundleResolutionDiagnostic)

    def test_pure_function_no_state_mutation(self) -> None:
        """Calling resolve_render_plan twice returns identical results."""
        org = _org(
            profiles={"t": _team("t", bundles=("dev-essentials",))},
            catalog=_FULL_CATALOG,
        )
        result_1 = resolve_render_plan(org, "t", "claude")
        result_2 = resolve_render_plan(org, "t", "claude")
        assert result_1.plans == result_2.plans
        assert result_1.diagnostics == result_2.diagnostics

    def test_different_providers_produce_different_plans(self) -> None:
        """Same config, different providers → different plan contents."""
        org = _org(
            profiles={"t": _team("t", bundles=("github-integration",))},
            catalog=_FULL_CATALOG,
        )
        claude = resolve_render_plan(org, "t", "claude")
        codex = resolve_render_plan(org, "t", "codex")
        # Plans are structurally different (different effective/skipped sets)
        assert claude.plans[0].effective_artifacts != codex.plans[0].effective_artifacts


# ═══════════════════════════════════════════════════════════════════════════════
# Internal function contract: _resolve_single_bundle
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveSingleBundleContract:
    """Direct tests on _resolve_single_bundle for edge cases."""

    def test_returns_plan_and_diagnostics_tuple(self) -> None:
        plan, diags = _resolve_single_bundle("dev-essentials", "claude", _FULL_CATALOG)
        assert isinstance(plan, ArtifactRenderPlan)
        assert isinstance(diags, list)

    def test_missing_bundle_soft_returns_empty_plan(self) -> None:
        plan, diags = _resolve_single_bundle("nonexistent", "claude", _FULL_CATALOG)
        assert plan.effective_artifacts == ()
        assert len(diags) == 1

    def test_missing_bundle_fail_closed_raises(self) -> None:
        with pytest.raises(BundleResolutionError):
            _resolve_single_bundle("nonexistent", "claude", _FULL_CATALOG, fail_closed=True)

    def test_disabled_bundle_returns_empty_plan(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={"s": _skill("s")},
            bindings={},
            bundles={
                "dis": ArtifactBundle(
                    name="dis",
                    artifacts=("s",),
                    install_intent=ArtifactInstallIntent.DISABLED,
                ),
            },
        )
        plan, diags = _resolve_single_bundle("dis", "claude", catalog)
        assert plan.effective_artifacts == ()
        assert len(diags) == 1
        assert "disabled" in diags[0].reason

    def test_invalid_artifact_soft_mode_skips(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("ghost",))},
        )
        plan, diags = _resolve_single_bundle("b", "claude", catalog)
        assert plan.skipped == ("ghost",)
        assert len(diags) == 1

    def test_invalid_artifact_fail_closed_raises(self) -> None:
        catalog = GovernedArtifactsCatalog(
            artifacts={},
            bindings={},
            bundles={"b": ArtifactBundle(name="b", artifacts=("ghost",))},
        )
        with pytest.raises(InvalidArtifactReferenceError):
            _resolve_single_bundle("b", "claude", catalog, fail_closed=True)
