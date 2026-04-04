"""Tests for the M001/M002 typed core contracts and S01 seam boundary.

These tests characterize the target shape for the S01 launch-path adoption:
- AgentLaunchSpec and AgentProvider contracts are complete and frozen.
- The S01 boundary expects the prepared launch plan to carry typed provider data,
  not Claude-shaped raw settings.
- The executed path should depend on the provider seam, not AgentRunner internals.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scc_cli.core.contracts import (
    AgentLaunchSpec,
    AuditEvent,
    DestinationSet,
    EgressRule,
    NetworkPolicyPlan,
    ProviderCapabilityProfile,
    RuntimeInfo,
    SafetyPolicy,
    SafetyVerdict,
)
from scc_cli.core.enums import NetworkPolicy, SeverityLevel
from scc_cli.ports.agent_provider import AgentProvider
from tests.fakes.fake_agent_provider import FakeAgentProvider

# ---------------------------------------------------------------------------
# Core typed contracts
# ---------------------------------------------------------------------------


def test_network_policy_plan_supports_truthful_policy_contract() -> None:
    plan = NetworkPolicyPlan(
        mode=NetworkPolicy.WEB_EGRESS_ENFORCED,
        destination_sets=(
            DestinationSet(
                name="anthropic-core",
                destinations=("api.anthropic.com",),
                required=True,
                description="Provider-core access",
            ),
        ),
        egress_rules=(
            EgressRule(
                target="api.anthropic.com",
                allow=True,
                reason="provider-core",
                protocol="https",
            ),
        ),
        enforced_by_runtime=True,
        notes=("proxy topology required",),
    )

    assert plan.mode is NetworkPolicy.WEB_EGRESS_ENFORCED
    assert plan.destination_sets[0].required is True
    assert plan.egress_rules[0].protocol == "https"
    assert plan.enforced_by_runtime is True


def test_runtime_and_safety_contracts_are_frozen() -> None:
    runtime = RuntimeInfo(
        runtime_id="docker",
        display_name="Docker Engine",
        cli_name="docker",
        supports_oci=True,
        supports_internal_networks=True,
        supports_host_network=True,
        rootless=False,
    )
    verdict = SafetyVerdict(
        allowed=False,
        reason="blocked destructive git command",
        matched_rule="git.reset_hard",
        command_family="destructive-git",
    )

    with pytest.raises(FrozenInstanceError):
        runtime.cli_name = "podman"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        verdict.reason = "changed"  # type: ignore[misc]


def test_audit_event_captures_shared_network_and_safety_shape() -> None:
    before = datetime.now(timezone.utc)
    event = AuditEvent(
        event_type="network.denied",
        message="Blocked private address",
        severity=SeverityLevel.WARNING,
        subject="169.254.169.254",
        metadata={"policy": "locked-down-web", "source": "org.defaults"},
    )
    after = datetime.now(timezone.utc)

    assert event.severity is SeverityLevel.WARNING
    assert event.subject == "169.254.169.254"
    assert event.metadata["policy"] == "locked-down-web"
    assert before <= event.occurred_at <= after


def test_agent_provider_protocol_returns_launch_spec() -> None:
    provider: AgentProvider = FakeAgentProvider()
    profile = provider.capability_profile()
    spec = provider.prepare_launch(
        config={"mode": "test"},
        workspace=Path("/tmp/workspace"),
        settings_path=Path("/tmp/workspace/.fake/settings.json"),
    )

    assert profile.provider_id == "fake"
    assert profile.required_destination_set == "fake-core"
    assert spec.provider_id == "fake"
    assert spec.argv == ("fake-agent",)
    assert spec.required_destination_sets == ("fake-core",)
    assert spec.artifact_paths == (Path("/tmp/workspace/.fake/settings.json"),)


def test_safety_policy_allows_rule_flags_without_loose_top_level_dicts() -> None:
    policy = SafetyPolicy(
        action="block",
        rules={
            "block_reset_hard": True,
            "block_force_push": True,
        },
        source="org.security.safety_net",
    )

    assert policy.action == "block"
    assert policy.rules["block_reset_hard"] is True
    assert policy.source == "org.security.safety_net"


# ---------------------------------------------------------------------------
# S01 seam boundary characterization
#
# These tests describe the intended S01 boundary contract:
# - The launch plan should be expressible in terms of AgentLaunchSpec.
# - AgentLaunchSpec carries typed provider data (argv, env, artifact_paths),
#   not raw Claude-shaped settings dicts.
# - AgentProvider.prepare_launch produces an AgentLaunchSpec that is
#   provider-neutral from the core perspective.
# ---------------------------------------------------------------------------


def test_agent_launch_spec_is_frozen_and_provider_neutral() -> None:
    """AgentLaunchSpec is immutable and carries only provider-neutral typed fields."""
    spec = AgentLaunchSpec(
        provider_id="claude",
        argv=("claude", "--dangerously-skip-permissions"),
        env={"ANTHROPIC_API_KEY": "sk-xxx"},
        workdir=Path("/workspace"),
        artifact_paths=(Path("/workspace/.claude/settings.json"),),
        required_destination_sets=("anthropic-core",),
        ux_addons=(),
    )

    assert spec.provider_id == "claude"
    assert spec.argv[0] == "claude"
    assert "ANTHROPIC_API_KEY" in spec.env
    assert spec.required_destination_sets == ("anthropic-core",)

    with pytest.raises(FrozenInstanceError):
        spec.provider_id = "codex"  # type: ignore[misc]


def test_agent_launch_spec_defaults_are_safe_empty_collections() -> None:
    """AgentLaunchSpec fields default to safe empty collections, not None."""
    spec = AgentLaunchSpec(
        provider_id="test",
        argv=("test-agent",),
    )

    assert spec.env == {}
    assert spec.workdir is None
    assert spec.artifact_paths == ()
    assert spec.required_destination_sets == ()
    assert spec.ux_addons == ()


def test_provider_capability_profile_carries_provider_core_destination() -> None:
    """ProviderCapabilityProfile identifies the provider-core destination set."""
    profile = ProviderCapabilityProfile(
        provider_id="claude",
        display_name="Claude Code",
        required_destination_set="anthropic-core",
        supports_resume=True,
        supports_skills=True,
        supports_native_integrations=True,
    )

    assert profile.required_destination_set == "anthropic-core"
    assert profile.supports_resume is True
    assert profile.supports_native_integrations is True


def test_prepare_launch_produces_spec_with_settings_artifact(tmp_path: Path) -> None:
    """AgentProvider.prepare_launch includes settings path in artifact_paths."""
    provider = FakeAgentProvider()
    settings_path = tmp_path / ".fake" / "settings.json"

    spec = provider.prepare_launch(
        config={"plugins": []},
        workspace=tmp_path,
        settings_path=settings_path,
    )

    assert spec.workdir == tmp_path
    assert settings_path in spec.artifact_paths
    assert spec.env.get("HAS_SETTINGS") == "1"


def test_prepare_launch_without_settings_produces_empty_artifact_paths(tmp_path: Path) -> None:
    """AgentProvider.prepare_launch without settings produces no artifact paths."""
    provider = FakeAgentProvider()

    spec = provider.prepare_launch(
        config={"plugins": []},
        workspace=tmp_path,
        settings_path=None,
    )

    assert spec.artifact_paths == ()


def test_agent_launch_spec_env_is_dict_not_raw_settings_payload() -> None:
    """AgentLaunchSpec.env is a plain str-to-str dict, not a raw provider settings payload.

    This characterizes the S01 contract: the runtime layer receives clean env vars,
    not a nested Claude-shaped settings blob. Provider adapters are responsible for
    translating their settings into env vars before handing back a launch spec.
    """
    provider = FakeAgentProvider()
    spec = provider.prepare_launch(
        config={"plugins": [], "mcpServers": {}},
        workspace=Path("/workspace"),
    )

    # env values must all be strings — no nested dicts or lists
    for key, value in spec.env.items():
        assert isinstance(key, str), f"env key {key!r} is not a str"
        assert isinstance(value, str), f"env[{key!r}] value {value!r} is not a str"
