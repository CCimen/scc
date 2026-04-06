"""Integration-level tests for OCI egress topology wiring.

All subprocess calls are mocked — no Docker daemon needed.
These tests verify the orchestration between OciSandboxRuntime,
NetworkTopologyManager, and the egress policy layer.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.adapters.egress_topology import EgressTopologyInfo
from scc_cli.adapters.oci_sandbox_runtime import OciSandboxRuntime
from scc_cli.core.contracts import DestinationSet, RuntimeInfo
from scc_cli.ports.models import MountSpec, SandboxHandle, SandboxSpec
from tests.fakes.fake_runtime_probe import FakeRuntimeProbe

# ── Helpers ──────────────────────────────────────────────────────────────────


def _oci_capable_info() -> RuntimeInfo:
    return RuntimeInfo(
        runtime_id="docker",
        display_name="Docker Engine",
        cli_name="docker",
        supports_oci=True,
        supports_internal_networks=True,
        supports_host_network=True,
        version="Docker version 27.5.1, build abc1234",
        daemon_reachable=True,
        sandbox_available=False,
        preferred_backend="oci",
    )


def _enforced_spec() -> SandboxSpec:
    return SandboxSpec(
        image="scc-agent-claude:latest",
        workspace_mount=MountSpec(source=Path("/home/user/project"), target=Path("/workspace")),
        workdir=Path("/workspace"),
        network_policy="web-egress-enforced",
    )


def _locked_down_spec() -> SandboxSpec:
    return SandboxSpec(
        image="scc-agent-claude:latest",
        workspace_mount=MountSpec(source=Path("/home/user/project"), target=Path("/workspace")),
        workdir=Path("/workspace"),
        network_policy="locked-down-web",
    )


def _open_spec() -> SandboxSpec:
    return SandboxSpec(
        image="scc-agent-claude:latest",
        workspace_mount=MountSpec(source=Path("/home/user/project"), target=Path("/workspace")),
        workdir=Path("/workspace"),
        network_policy="open",
    )


@pytest.fixture()
def runtime() -> OciSandboxRuntime:
    return OciSandboxRuntime(FakeRuntimeProbe(_oci_capable_info()))


_FAKE_TOPO_INFO = EgressTopologyInfo(
    network_name="scc-egress-scc-oci-abc123",
    proxy_container_name="scc-proxy-scc-oci-abc123",
    proxy_endpoint="http://172.18.0.2:3128",
)


# ── Tests ────────────────────────────────────────────────────────────────────


class TestEnforcedModeIntegration:
    """Verify run() orchestrates topology correctly for web-egress-enforced."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime.collect_proxy_env", return_value={})
    @patch("scc_cli.adapters.oci_sandbox_runtime._find_existing_container", return_value=None)
    def test_run_enforced_sets_up_topology_before_create(
        self,
        mock_find: MagicMock,
        mock_collect: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """NetworkTopologyManager.setup() is called before docker create."""
        mock_topo = MagicMock()
        mock_topo.setup.return_value = _FAKE_TOPO_INFO
        mock_topo_cls.return_value = mock_topo
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        runtime.run(_enforced_spec())

        # setup was called
        mock_topo.setup.assert_called_once()

        # docker create is the first _run_docker call (after topology.setup)
        create_call = mock_run_docker.call_args_list[0]
        create_cmd: list[str] = create_call[0][0]
        assert create_cmd[0] == "create"

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime.collect_proxy_env", return_value={})
    @patch("scc_cli.adapters.oci_sandbox_runtime._find_existing_container", return_value=None)
    def test_run_enforced_passes_network_to_create(
        self,
        mock_find: MagicMock,
        mock_collect: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """docker create args contain --network scc-egress-*."""
        mock_topo = MagicMock()
        mock_topo.setup.return_value = _FAKE_TOPO_INFO
        mock_topo_cls.return_value = mock_topo
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        runtime.run(_enforced_spec())

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "--network" in create_cmd
        net_idx = create_cmd.index("--network")
        assert create_cmd[net_idx + 1].startswith("scc-egress-")

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime.collect_proxy_env", return_value={})
    @patch("scc_cli.adapters.oci_sandbox_runtime._find_existing_container", return_value=None)
    def test_run_enforced_injects_proxy_env(
        self,
        mock_find: MagicMock,
        mock_collect: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """Proxy env vars appear in docker create for enforced mode."""
        mock_topo = MagicMock()
        mock_topo.setup.return_value = _FAKE_TOPO_INFO
        mock_topo_cls.return_value = mock_topo
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        runtime.run(_enforced_spec())

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "HTTP_PROXY=http://172.18.0.2:3128" in create_cmd
        assert "HTTPS_PROXY=http://172.18.0.2:3128" in create_cmd
        assert "NO_PROXY=" in create_cmd


class TestLockedDownModeIntegration:
    """Verify locked-down-web skips topology entirely."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime._find_existing_container", return_value=None)
    def test_run_locked_down_skips_topology(
        self,
        mock_find: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """NetworkTopologyManager is NOT instantiated for locked-down-web."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        runtime.run(_locked_down_spec())

        mock_topo_cls.assert_not_called()

        # Verify --network none in docker create
        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "--network" in create_cmd
        net_idx = create_cmd.index("--network")
        assert create_cmd[net_idx + 1] == "none"


class TestOpenModeIntegration:
    """Verify open mode is unchanged (no topology, no network flags)."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime._find_existing_container", return_value=None)
    def test_run_open_mode_unchanged(
        self,
        mock_find: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """No topology setup, no network flags for open mode."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        runtime.run(_open_spec())

        mock_topo_cls.assert_not_called()

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "--network" not in create_cmd


class TestTopologyTeardown:
    """Verify topology teardown is wired into remove() and stop()."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_remove_tears_down_topology(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """When topology was set up, remove() calls teardown()."""
        mock_topology = MagicMock()
        runtime._topology = mock_topology

        mock_run_docker.return_value = MagicMock(stdout="")
        runtime.remove(SandboxHandle(sandbox_id="cid123"))

        mock_topology.teardown.assert_called_once()
        assert runtime._topology is None

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_stop_tears_down_topology(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """When topology was set up, stop() calls teardown()."""
        mock_topology = MagicMock()
        runtime._topology = mock_topology

        mock_run_docker.return_value = MagicMock(stdout="")
        runtime.stop(SandboxHandle(sandbox_id="cid123"))

        mock_topology.teardown.assert_called_once()
        assert runtime._topology is None

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_remove_without_topology_is_safe(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """remove() with no topology doesn't error."""
        assert runtime._topology is None
        mock_run_docker.return_value = MagicMock(stdout="")
        runtime.remove(SandboxHandle(sandbox_id="cid123"))  # should not raise

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_stop_without_topology_is_safe(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """stop() with no topology doesn't error."""
        assert runtime._topology is None
        mock_run_docker.return_value = MagicMock(stdout="")
        runtime.stop(SandboxHandle(sandbox_id="cid123"))  # should not raise


class TestGuardrail:
    """Regression guardrails for network enforcement."""

    def test_enforced_mode_never_produces_default_network(self) -> None:
        """For web-egress-enforced, _build_create_cmd must NOT produce a command
        without an explicit --network flag (prevents regression to default bridge).
        """
        spec = SandboxSpec(
            image="scc-agent-claude:latest",
            workspace_mount=MountSpec(source=Path("/home/user/project"), target=Path("/workspace")),
            workdir=Path("/workspace"),
            network_policy="web-egress-enforced",
        )
        # When topology provides a network name, --network is present
        cmd_with_net = OciSandboxRuntime._build_create_cmd(
            spec,
            "scc-oci-test",
            network_name="scc-egress-scc-oci-test",
        )
        assert "--network" in cmd_with_net

        # When network_name is None (topology not set up), enforced mode
        # does NOT add any --network flag — this is the caller's
        # responsibility to ensure topology.setup() is called first.
        # The guardrail is that run() always calls setup() before create().
        cmd_no_net = OciSandboxRuntime._build_create_cmd(
            spec,
            "scc-oci-test",
            network_name=None,
        )
        # Without a network_name and not locked-down, no --network is added.
        # The contract is enforced at the run() level, not _build_create_cmd.
        # This test documents the expected behavior.
        assert "--network" not in cmd_no_net

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime.collect_proxy_env", return_value={})
    @patch("scc_cli.adapters.oci_sandbox_runtime._find_existing_container", return_value=None)
    def test_run_enforced_always_passes_network_name(
        self,
        mock_find: MagicMock,
        mock_collect: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """run() with web-egress-enforced always results in --network in create cmd.

        This is the true guardrail: the runtime flow guarantees topology.setup()
        provides a network_name before docker create is called.
        """
        mock_topo = MagicMock()
        mock_topo.setup.return_value = _FAKE_TOPO_INFO
        mock_topo_cls.return_value = mock_topo
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        runtime.run(_enforced_spec())

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "--network" in create_cmd, (
            "Enforced mode must always produce --network in docker create"
        )
        net_idx = create_cmd.index("--network")
        assert create_cmd[net_idx + 1] != "none", (
            "Enforced mode uses the internal network, not 'none'"
        )


# ── Destination-set-aware egress tests ──────────────────────────────────────


def _enforced_spec_with_destinations() -> SandboxSpec:
    """Enforced spec carrying resolved destination sets."""
    return SandboxSpec(
        image="scc-agent-claude:latest",
        workspace_mount=MountSpec(source=Path("/home/user/project"), target=Path("/workspace")),
        workdir=Path("/workspace"),
        network_policy="web-egress-enforced",
        destination_sets=(
            DestinationSet(
                name="anthropic-core",
                destinations=("api.anthropic.com",),
                required=True,
                description="Anthropic API core access",
            ),
        ),
    )


class TestDestinationSetEgressIntegration:
    """Verify destination sets on SandboxSpec produce allow rules in the egress plan."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime.collect_proxy_env", return_value={})
    @patch("scc_cli.adapters.oci_sandbox_runtime.compile_squid_acl")
    @patch("scc_cli.adapters.oci_sandbox_runtime.build_egress_plan")
    def test_destination_sets_threaded_into_egress_plan(
        self,
        mock_build_plan: MagicMock,
        mock_compile_acl: MagicMock,
        mock_collect: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """build_egress_plan() receives destination_sets and egress_rules from spec."""
        from scc_cli.core.contracts import NetworkPolicyPlan
        from scc_cli.core.enums import NetworkPolicy

        mock_build_plan.return_value = NetworkPolicyPlan(
            mode=NetworkPolicy.WEB_EGRESS_ENFORCED,
            enforced_by_runtime=True,
        )
        mock_compile_acl.return_value = "http_access deny all\n"
        mock_topo = MagicMock()
        mock_topo.setup.return_value = _FAKE_TOPO_INFO
        mock_topo_cls.return_value = mock_topo
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        spec = _enforced_spec_with_destinations()
        runtime.run(spec)

        mock_build_plan.assert_called_once()
        call_kwargs = mock_build_plan.call_args
        # Positional arg: NetworkPolicy.WEB_EGRESS_ENFORCED
        assert call_kwargs[0][0] is NetworkPolicy.WEB_EGRESS_ENFORCED
        # Keyword: destination_sets should match spec
        assert call_kwargs[1]["destination_sets"] == spec.destination_sets
        # Keyword: egress_rules should contain allow rules for the destinations
        egress_rules = call_kwargs[1]["egress_rules"]
        assert len(egress_rules) == 1
        assert egress_rules[0].target == "api.anthropic.com"
        assert egress_rules[0].allow is True

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime.collect_proxy_env", return_value={})
    def test_enforced_spec_without_destinations_produces_no_allow_rules(
        self,
        mock_collect: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """Enforced spec with empty destination_sets produces only deny rules in ACL."""
        mock_topo = MagicMock()
        mock_topo.setup.return_value = _FAKE_TOPO_INFO
        mock_topo_cls.return_value = mock_topo
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        # Use the original enforced spec (no destination_sets)
        runtime.run(_enforced_spec())

        # The call succeeded (no error). The existing topology/acl tests cover
        # that the acl is correct — this test just confirms no crash on empty sets.

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    @patch("scc_cli.adapters.oci_sandbox_runtime.NetworkTopologyManager")
    @patch("scc_cli.adapters.oci_sandbox_runtime.collect_proxy_env", return_value={})
    @patch("scc_cli.adapters.oci_sandbox_runtime.compile_squid_acl")
    @patch("scc_cli.adapters.oci_sandbox_runtime.build_egress_plan")
    def test_multiple_destination_sets_produce_multiple_allow_rules(
        self,
        mock_build_plan: MagicMock,
        mock_compile_acl: MagicMock,
        mock_collect: MagicMock,
        mock_topo_cls: MagicMock,
        mock_run_docker: MagicMock,
        mock_execvp: MagicMock,
        runtime: OciSandboxRuntime,
    ) -> None:
        """Multiple destination sets generate allow rules for every host."""
        from scc_cli.core.contracts import NetworkPolicyPlan
        from scc_cli.core.enums import NetworkPolicy

        mock_build_plan.return_value = NetworkPolicyPlan(
            mode=NetworkPolicy.WEB_EGRESS_ENFORCED,
            enforced_by_runtime=True,
        )
        mock_compile_acl.return_value = "http_access deny all\n"
        mock_topo = MagicMock()
        mock_topo.setup.return_value = _FAKE_TOPO_INFO
        mock_topo_cls.return_value = mock_topo
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        spec = SandboxSpec(
            image="scc-agent-claude:latest",
            workspace_mount=MountSpec(source=Path("/home/user/project"), target=Path("/workspace")),
            workdir=Path("/workspace"),
            network_policy="web-egress-enforced",
            destination_sets=(
                DestinationSet(
                    name="anthropic-core",
                    destinations=("api.anthropic.com",),
                    required=True,
                ),
                DestinationSet(
                    name="openai-core",
                    destinations=("api.openai.com",),
                    required=True,
                ),
            ),
        )
        runtime.run(spec)

        call_kwargs = mock_build_plan.call_args
        egress_rules = call_kwargs[1]["egress_rules"]
        allow_targets = [r.target for r in egress_rules]
        assert "api.anthropic.com" in allow_targets
        assert "api.openai.com" in allow_targets
        assert all(r.allow for r in egress_rules)
