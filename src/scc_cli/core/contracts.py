"""Typed core contracts for provider-neutral launch, runtime, network, safety, and audit planning.

These models define the M001 contract surface without forcing the existing
launch/runtime flow to migrate all at once. They are intentionally thin,
provider-neutral, and suitable for later adoption by application services,
runtime backends, and provider adapters.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .enums import NetworkPolicy, SeverityLevel


@dataclass(frozen=True)
class DestinationSet:
    """Named bundle of network destinations required or allowed for a launch plan.

    Attributes:
        name: Stable identifier for the destination bundle.
        destinations: Hostnames, domains, or named endpoints in the bundle.
        required: Whether the launch cannot proceed without this bundle.
        description: Short explanation of why the bundle exists.
    """

    name: str
    destinations: tuple[str, ...] = ()
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class EgressRule:
    """One normalized network rule in a computed egress plan.

    Attributes:
        target: Host, domain glob, CIDR, or named resource the rule applies to.
        allow: Whether the rule allows or blocks the target.
        reason: Short explanation for why the rule exists.
        protocol: Optional transport scope, such as http or https.
    """

    target: str
    allow: bool
    reason: str
    protocol: str | None = None


@dataclass(frozen=True)
class NetworkPolicyPlan:
    """Typed result of control-plane network planning.

    Attributes:
        mode: Truthful network policy mode for the launch.
        destination_sets: Named destination bundles included in the plan.
        egress_rules: Normalized ordered egress rules.
        enforced_by_runtime: Whether the runtime is expected to enforce the plan.
        notes: Additional operator-facing caveats or context.
    """

    mode: NetworkPolicy
    destination_sets: tuple[DestinationSet, ...] = ()
    egress_rules: tuple[EgressRule, ...] = ()
    enforced_by_runtime: bool = False
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeInfo:
    """Capabilities and identity of a resolved sandbox runtime backend.

    Attributes:
        runtime_id: Stable backend identifier, such as docker or podman.
        display_name: Human-readable runtime name.
        cli_name: Executable name used for subprocess invocation.
        supports_oci: Whether the backend supports OCI container workflows.
        supports_internal_networks: Whether isolated/internal networking is supported.
        supports_host_network: Whether host networking is available.
        rootless: Whether the runtime is operating in rootless mode, if known.
    """

    runtime_id: str
    display_name: str
    cli_name: str
    supports_oci: bool
    supports_internal_networks: bool
    supports_host_network: bool
    rootless: bool | None = None
    version: str | None = None
    desktop_version: str | None = None
    daemon_reachable: bool = False
    sandbox_available: bool = False
    preferred_backend: str | None = None


@dataclass(frozen=True)
class SafetyPolicy:
    """Normalized safety policy available to runtime and adapter layers.

    Attributes:
        action: Baseline action when a guarded command is matched.
        rules: Boolean or scalar rule settings keyed by stable rule name.
        source: Where the policy originated, such as org.security.safety_net.
    """

    action: str = "block"
    rules: dict[str, Any] = field(default_factory=dict)
    source: str = "org.security.safety_net"


@dataclass(frozen=True)
class SafetyVerdict:
    """Decision produced by safety evaluation for one attempted action.

    Attributes:
        allowed: Whether the action is permitted.
        reason: User-facing reason for the decision.
        matched_rule: Stable rule identifier, if any.
        command_family: High-level command family, if known.
    """

    allowed: bool
    reason: str
    matched_rule: str | None = None
    command_family: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    """Shared typed audit record for network, safety, and launch events.

    Attributes:
        event_type: Stable event identifier.
        message: Human-readable event summary.
        severity: Audit severity level.
        occurred_at: UTC timestamp of the event.
        subject: Optional subject such as plugin, server, or provider.
        metadata: Structured key-value context safe for serialization.
    """

    event_type: str
    message: str
    severity: SeverityLevel = SeverityLevel.INFO
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    subject: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderCapabilityProfile:
    """Provider-neutral description of adapter capabilities and requirements.

    Attributes:
        provider_id: Stable provider identifier.
        display_name: Human-readable provider name.
        required_destination_set: Provider-core destination bundle required to launch.
        supports_resume: Whether the provider can resume prior sessions.
        supports_skills: Whether shared skills are supported.
        supports_native_integrations: Whether provider-native hooks/plugins/rules exist.
    """

    provider_id: str
    display_name: str
    required_destination_set: str
    supports_resume: bool = False
    supports_skills: bool = False
    supports_native_integrations: bool = False


@dataclass(frozen=True)
class AgentLaunchSpec:
    """Provider-owned launch plan handed to the runtime layer.

    Attributes:
        provider_id: Stable provider identifier.
        argv: Provider launch command argv.
        env: Provider launch environment.
        workdir: Launch working directory.
        artifact_paths: Provider-owned config or credential artifact paths.
        required_destination_sets: Provider-core destination bundles required to launch.
        ux_addons: Provider-native UX integrations or sidecar artifacts.
    """

    provider_id: str
    argv: tuple[str, ...]
    env: dict[str, str] = field(default_factory=dict)
    workdir: Path | None = None
    artifact_paths: tuple[Path, ...] = ()
    required_destination_sets: tuple[str, ...] = ()
    ux_addons: tuple[str, ...] = ()
