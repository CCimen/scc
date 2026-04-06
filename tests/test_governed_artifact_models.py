"""Unit tests for governed artifact type hierarchy (spec-06).

Covers construction, immutability, enum membership, defaults, and re-exports.
"""

from __future__ import annotations

import dataclasses

import pytest

from scc_cli.core.governed_artifacts import (
    ArtifactBundle,
    ArtifactInstallIntent,
    ArtifactKind,
    ArtifactRenderPlan,
    GovernedArtifact,
    ProviderArtifactBinding,
)

# ---------------------------------------------------------------------------
# ArtifactKind enum
# ---------------------------------------------------------------------------


class TestArtifactKind:
    def test_all_members_present(self) -> None:
        expected = {"skill", "mcp_server", "native_integration", "bundle"}
        assert {m.value for m in ArtifactKind} == expected

    def test_str_comparison(self) -> None:
        assert ArtifactKind.SKILL == "skill"
        assert ArtifactKind.MCP_SERVER == "mcp_server"
        assert ArtifactKind.NATIVE_INTEGRATION == "native_integration"
        assert ArtifactKind.BUNDLE == "bundle"

    def test_member_count(self) -> None:
        assert len(ArtifactKind) == 4


# ---------------------------------------------------------------------------
# ArtifactInstallIntent enum
# ---------------------------------------------------------------------------


class TestArtifactInstallIntent:
    def test_all_members_present(self) -> None:
        expected = {"required", "available", "disabled", "request-only"}
        assert {m.value for m in ArtifactInstallIntent} == expected

    def test_str_comparison(self) -> None:
        assert ArtifactInstallIntent.REQUIRED == "required"
        assert ArtifactInstallIntent.AVAILABLE == "available"
        assert ArtifactInstallIntent.DISABLED == "disabled"
        assert ArtifactInstallIntent.REQUEST_ONLY == "request-only"

    def test_member_count(self) -> None:
        assert len(ArtifactInstallIntent) == 4


# ---------------------------------------------------------------------------
# GovernedArtifact
# ---------------------------------------------------------------------------


class TestGovernedArtifact:
    def test_construction_all_fields(self) -> None:
        artifact = GovernedArtifact(
            kind=ArtifactKind.SKILL,
            name="code-review-skill",
            version="1.4.2",
            publisher="ai-team",
            pinned=True,
            source_type="git",
            source_url="https://git.example.se/ai/agent-artifacts.git",
            source_path="skills/code-review",
            source_ref="v1.4.2",
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        assert artifact.kind == ArtifactKind.SKILL
        assert artifact.name == "code-review-skill"
        assert artifact.version == "1.4.2"
        assert artifact.publisher == "ai-team"
        assert artifact.pinned is True
        assert artifact.source_type == "git"
        assert artifact.source_url == "https://git.example.se/ai/agent-artifacts.git"
        assert artifact.source_path == "skills/code-review"
        assert artifact.source_ref == "v1.4.2"
        assert artifact.install_intent == ArtifactInstallIntent.REQUIRED

    def test_defaults(self) -> None:
        artifact = GovernedArtifact(kind=ArtifactKind.MCP_SERVER, name="github-mcp")
        assert artifact.version is None
        assert artifact.publisher is None
        assert artifact.pinned is False
        assert artifact.source_type is None
        assert artifact.source_url is None
        assert artifact.source_path is None
        assert artifact.source_ref is None
        assert artifact.install_intent == ArtifactInstallIntent.AVAILABLE

    def test_frozen_immutability(self) -> None:
        artifact = GovernedArtifact(kind=ArtifactKind.SKILL, name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            artifact.name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ProviderArtifactBinding
# ---------------------------------------------------------------------------


class TestProviderArtifactBinding:
    def test_construction_all_fields(self) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="./claude/github-hooks.json",
            native_config={
                "hooks": "./claude/github-hooks.json",
                "marketplace_bundle": "./claude/github-marketplace",
            },
            transport_type="stdio",
        )
        assert binding.provider == "claude"
        assert binding.native_ref == "./claude/github-hooks.json"
        assert binding.native_config["hooks"] == "./claude/github-hooks.json"
        assert binding.transport_type == "stdio"

    def test_defaults(self) -> None:
        binding = ProviderArtifactBinding(provider="codex")
        assert binding.native_ref is None
        assert binding.native_config == {}
        assert binding.transport_type is None

    def test_frozen_immutability(self) -> None:
        binding = ProviderArtifactBinding(provider="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):
            binding.provider = "codex"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ArtifactBundle
# ---------------------------------------------------------------------------


class TestArtifactBundle:
    def test_construction_all_fields(self) -> None:
        bundle = ArtifactBundle(
            name="github-dev",
            description="GitHub development workflow bundle",
            artifacts=("code-review-skill", "github-mcp", "github-native", "team-guidance"),
            install_intent=ArtifactInstallIntent.AVAILABLE,
        )
        assert bundle.name == "github-dev"
        assert bundle.description == "GitHub development workflow bundle"
        assert len(bundle.artifacts) == 4
        assert "code-review-skill" in bundle.artifacts
        assert bundle.install_intent == ArtifactInstallIntent.AVAILABLE

    def test_defaults(self) -> None:
        bundle = ArtifactBundle(name="minimal")
        assert bundle.description == ""
        assert bundle.artifacts == ()
        assert bundle.install_intent == ArtifactInstallIntent.AVAILABLE

    def test_frozen_immutability(self) -> None:
        bundle = ArtifactBundle(name="test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            bundle.name = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ArtifactRenderPlan
# ---------------------------------------------------------------------------


class TestArtifactRenderPlan:
    def test_construction_all_fields(self) -> None:
        binding = ProviderArtifactBinding(provider="claude", native_ref="./hooks.json")
        plan = ArtifactRenderPlan(
            bundle_id="github-dev",
            provider="claude",
            bindings=(binding,),
            skipped=("codex-only-rule",),
            effective_artifacts=("code-review-skill", "github-mcp"),
        )
        assert plan.bundle_id == "github-dev"
        assert plan.provider == "claude"
        assert len(plan.bindings) == 1
        assert plan.bindings[0].provider == "claude"
        assert plan.skipped == ("codex-only-rule",)
        assert "code-review-skill" in plan.effective_artifacts

    def test_defaults(self) -> None:
        plan = ArtifactRenderPlan(bundle_id="empty", provider="codex")
        assert plan.bindings == ()
        assert plan.skipped == ()
        assert plan.effective_artifacts == ()

    def test_frozen_immutability(self) -> None:
        plan = ArtifactRenderPlan(bundle_id="test", provider="claude")
        with pytest.raises(dataclasses.FrozenInstanceError):
            plan.bundle_id = "mutated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Re-exports from contracts module
# ---------------------------------------------------------------------------


class TestContractsReExports:
    """Verify that all governed artifact models are importable from contracts."""

    def test_import_from_contracts(self) -> None:
        from scc_cli.core.contracts import ArtifactBundle as ContractsArtifactBundle
        from scc_cli.core.contracts import ArtifactInstallIntent as ContractsArtifactInstallIntent
        from scc_cli.core.contracts import ArtifactKind as ContractsArtifactKind
        from scc_cli.core.contracts import ArtifactRenderPlan as ContractsArtifactRenderPlan
        from scc_cli.core.contracts import GovernedArtifact as ContractsGovernedArtifact
        from scc_cli.core.contracts import (
            ProviderArtifactBinding as ContractsProviderArtifactBinding,
        )

        # Quick smoke — just verify they're the same class objects
        assert ContractsArtifactKind is ArtifactKind
        assert ContractsArtifactInstallIntent is ArtifactInstallIntent
        assert ContractsGovernedArtifact is GovernedArtifact
        assert ContractsProviderArtifactBinding is ProviderArtifactBinding
        assert ContractsArtifactBundle is ArtifactBundle
        assert ContractsArtifactRenderPlan is ArtifactRenderPlan


# ---------------------------------------------------------------------------
# Cross-model integration
# ---------------------------------------------------------------------------


class TestCrossModelIntegration:
    """End-to-end construction matching spec-06 YAML example."""

    def test_spec_example_round_trip(self) -> None:
        """Build the spec-06 example model graph and verify relationships."""
        skill = GovernedArtifact(
            kind=ArtifactKind.SKILL,
            name="code-review-skill",
            source_type="git",
            source_url="https://git.example.se/ai/agent-artifacts.git",
            source_path="skills/code-review",
            source_ref="v1.4.2",
            install_intent=ArtifactInstallIntent.AVAILABLE,
        )
        mcp = GovernedArtifact(
            kind=ArtifactKind.MCP_SERVER,
            name="github-mcp",
            source_type="git",
            source_url="https://git.example.se/ai/agent-artifacts.git",
            source_path="mcp/github.json",
            source_ref="v1.4.2",
            install_intent=ArtifactInstallIntent.REQUIRED,
        )
        native = GovernedArtifact(
            kind=ArtifactKind.NATIVE_INTEGRATION,
            name="github-native",
            install_intent=ArtifactInstallIntent.AVAILABLE,
        )

        claude_binding = ProviderArtifactBinding(
            provider="claude",
            native_config={
                "hooks": "./claude/github-hooks.json",
                "marketplace_bundle": "./claude/github-marketplace",
            },
        )
        codex_binding = ProviderArtifactBinding(
            provider="codex",
            native_config={
                "plugin_bundle": "./codex/github-plugin",
                "rules": "./codex/rules/github.rules",
            },
        )

        bundle = ArtifactBundle(
            name="github-dev",
            artifacts=(skill.name, mcp.name, native.name),
            install_intent=ArtifactInstallIntent.AVAILABLE,
        )

        render_plan = ArtifactRenderPlan(
            bundle_id=bundle.name,
            provider="claude",
            bindings=(claude_binding,),
            skipped=(),
            effective_artifacts=(skill.name, mcp.name, native.name),
        )

        assert render_plan.bundle_id == bundle.name
        assert len(render_plan.effective_artifacts) == 3
        assert codex_binding.provider == "codex"
