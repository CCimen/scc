"""Governed artifact type hierarchy from spec-06.

These models define the provider-neutral bundle architecture's type surface.
They are pure data definitions — no behavioral logic, no provider-specific
assumptions.

Terminology:
    GovernedArtifact   – one approved reusable unit in SCC policy
    ArtifactBundle     – team-facing selection unit (a named group of artifacts)
    ProviderArtifactBinding – provider-native rendering detail for one artifact
    ArtifactRenderPlan – effective per-session materialization plan after policy merge
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ArtifactKind(str, Enum):
    """Kind of governed artifact.

    Values:
        SKILL: open Agent Skills package, shared across providers.
        MCP_SERVER: provider-neutral MCP definition plus transport metadata.
        NATIVE_INTEGRATION: provider-specific hooks, rules, plugin folders, etc.
        BUNDLE: named grouping of skills, MCP servers, and native integrations.
    """

    SKILL = "skill"
    MCP_SERVER = "mcp_server"
    NATIVE_INTEGRATION = "native_integration"
    BUNDLE = "bundle"


class ArtifactInstallIntent(str, Enum):
    """Installation intent for a governed artifact or bundle.

    Values:
        REQUIRED: render/install automatically for the selected provider.
        AVAILABLE: expose for opt-in or browsing, not auto-enabled.
        DISABLED: explicitly not allowed in the effective session.
        REQUEST_ONLY: visible as an approved request target, not effective until promoted.
    """

    REQUIRED = "required"
    AVAILABLE = "available"
    DISABLED = "disabled"
    REQUEST_ONLY = "request-only"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GovernedArtifact:
    """One approved reusable unit in SCC policy.

    Carries kind, identity, provenance, and pinning metadata.  Bindings for
    native integrations are held separately in ProviderArtifactBinding.

    Attributes:
        kind: What category this artifact belongs to.
        name: Stable human-readable identifier.
        version: Pinned version or source ref, if known.
        publisher: Owner or publisher metadata for audit purposes.
        pinned: Whether the artifact version is locked.
        source_type: Origin kind — ``git``, ``url``, ``local``, etc.
        source_url: Remote location of the artifact source.
        source_path: Path within the source tree, if applicable.
        source_ref: Git ref, tag, or commit for pinning.
        install_intent: Operator expectation for this artifact.
    """

    kind: ArtifactKind
    name: str
    version: str | None = None
    publisher: str | None = None
    pinned: bool = False
    source_type: str | None = None
    source_url: str | None = None
    source_path: str | None = None
    source_ref: str | None = None
    install_intent: ArtifactInstallIntent = ArtifactInstallIntent.AVAILABLE


@dataclass(frozen=True)
class ProviderArtifactBinding:
    """Provider-native rendering details for one governed artifact.

    Each binding is provider-specific — Claude and Codex are NOT flattened
    into a shared shape.  The ``native_config`` dict holds arbitrary
    provider-scoped key-value pairs (hooks paths, plugin bundle paths,
    rules file references, etc.).

    Attributes:
        provider: Target provider identifier (e.g. ``claude``, ``codex``).
        native_ref: Primary native reference for the binding, if any.
        native_config: Flexible key-value config for provider-specific detail.
        transport_type: Transport hint for MCP or integration bindings.
    """

    provider: str
    native_ref: str | None = None
    native_config: dict[str, str] = field(default_factory=dict)
    transport_type: str | None = None


@dataclass(frozen=True)
class ArtifactBundle:
    """Team-facing selection unit — a named approved grouping.

    Teams enable bundles, not raw provider plugin references.

    Attributes:
        name: Stable bundle identifier.
        description: Human-readable explanation of the bundle purpose.
        artifacts: Ordered artifact names that compose this bundle.
        install_intent: Operator expectation for the bundle as a whole.
    """

    name: str
    description: str = ""
    artifacts: tuple[str, ...] = ()
    install_intent: ArtifactInstallIntent = ArtifactInstallIntent.AVAILABLE


@dataclass(frozen=True)
class ArtifactRenderPlan:
    """Effective per-session materialization plan after policy merge.

    Produced by core after org/team/project/user policy merge, consumed by
    the selected provider adapter for projection into native files.

    Attributes:
        bundle_id: Source bundle identifier this plan was derived from.
        provider: Target provider for this render pass.
        bindings: Provider-native bindings to render.
        skipped: Artifact names that could not be rendered for this provider.
        effective_artifacts: Artifact names included in the effective plan.
    """

    bundle_id: str
    provider: str
    bindings: tuple[ProviderArtifactBinding, ...] = ()
    skipped: tuple[str, ...] = ()
    effective_artifacts: tuple[str, ...] = ()


__all__ = [
    "ArtifactBundle",
    "ArtifactInstallIntent",
    "ArtifactKind",
    "ArtifactRenderPlan",
    "GovernedArtifact",
    "ProviderArtifactBinding",
]
