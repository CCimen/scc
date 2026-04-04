"""Tests for NetworkTopologyManager — all Docker calls are mocked."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.adapters.egress_topology import (
    _PROXY_IMAGE,
    _PROXY_LABEL,
    EgressTopologyInfo,
    NetworkTopologyManager,
)
from scc_cli.core.errors import SandboxLaunchError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SESSION_ID = "abc123"
NETWORK_NAME = f"scc-egress-{SESSION_ID}"
PROXY_NAME = f"scc-proxy-{SESSION_ID}"
PROXY_IP = "172.20.0.2"
ACL_CONFIG = "http_access deny all\n"


@pytest.fixture()
def manager() -> NetworkTopologyManager:
    return NetworkTopologyManager(session_id=SESSION_ID)


def _ok(stdout: str = "") -> subprocess.CompletedProcess[str]:
    """Return a successful CompletedProcess stub."""
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")


# ---------------------------------------------------------------------------
# setup() — happy path
# ---------------------------------------------------------------------------


class TestSetupHappyPath:
    """Verify that setup() orchestrates Docker calls in the right order."""

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_creates_internal_network(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        mock_run.return_value = _ok(PROXY_IP)
        manager.setup(ACL_CONFIG)

        # First call must be network create --internal
        first_call = mock_run.call_args_list[0]
        cmd = first_call[0][0]
        assert cmd[:2] == ["docker", "network"]
        assert "create" in cmd
        assert "--internal" in cmd
        assert NETWORK_NAME in cmd

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_starts_proxy_container(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        mock_run.return_value = _ok(PROXY_IP)
        manager.setup(ACL_CONFIG)

        # Second call is docker run for the proxy
        second_call = mock_run.call_args_list[1]
        cmd = second_call[0][0]
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "-d" in cmd
        assert PROXY_NAME in cmd
        assert _PROXY_IMAGE in cmd
        assert _PROXY_LABEL in cmd

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_connects_proxy_to_bridge(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        mock_run.return_value = _ok(PROXY_IP)
        manager.setup(ACL_CONFIG)

        # Third call connects proxy to bridge
        third_call = mock_run.call_args_list[2]
        cmd = third_call[0][0]
        assert "network" in cmd
        assert "connect" in cmd
        assert "bridge" in cmd
        assert PROXY_NAME in cmd

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_returns_topology_info(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        mock_run.return_value = _ok(PROXY_IP)
        info = manager.setup(ACL_CONFIG)

        assert isinstance(info, EgressTopologyInfo)
        assert info.network_name == NETWORK_NAME
        assert info.proxy_container_name == PROXY_NAME
        assert info.proxy_endpoint == f"http://{PROXY_IP}:3128"

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_writes_acl_config_to_temp_file(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        """The docker run command should volume-mount an ACL temp file."""
        mock_run.return_value = _ok(PROXY_IP)
        manager.setup(ACL_CONFIG)

        # The run call (second) should have a -v flag with acl-rules.conf
        run_call = mock_run.call_args_list[1]
        cmd = run_call[0][0]
        vol_args = [arg for arg in cmd if "/etc/squid/acl-rules.conf:ro" in arg]
        assert len(vol_args) == 1, f"Expected volume mount with acl-rules.conf, got: {cmd}"


# ---------------------------------------------------------------------------
# teardown()
# ---------------------------------------------------------------------------


class TestTeardown:
    """Verify teardown is idempotent and cleans up resources."""

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_removes_proxy_and_network(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        mock_run.return_value = _ok()
        manager.teardown()

        cmds = [c[0][0] for c in mock_run.call_args_list]
        # Should have docker rm -f for proxy
        rm_calls = [c for c in cmds if "rm" in c and PROXY_NAME in c]
        assert len(rm_calls) >= 1
        # Should have docker network rm for network
        net_rm_calls = [c for c in cmds if "network" in c and "rm" in c and NETWORK_NAME in c]
        assert len(net_rm_calls) >= 1

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_idempotent_on_missing_resources(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        """Teardown succeeds even when docker rm / network rm fail."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="docker", stderr="No such container"
        )
        # Should not raise
        manager.teardown()


# ---------------------------------------------------------------------------
# setup() — failure modes
# ---------------------------------------------------------------------------


class TestSetupFailures:
    """Verify correct error handling and cleanup on setup failures."""

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_network_create_failure_raises(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="docker", stderr="network already exists"
        )

        with pytest.raises(SandboxLaunchError):
            manager.setup(ACL_CONFIG)

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_proxy_start_failure_triggers_cleanup(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        """If the proxy container fails to start, teardown should still run."""
        call_count = 0

        def side_effect(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # network create succeeds
                return _ok()
            if call_count == 2:
                # docker run fails
                raise subprocess.CalledProcessError(
                    returncode=125, cmd="docker", stderr="image not found"
                )
            # Remaining calls are teardown — succeed
            return _ok()

        mock_run.side_effect = side_effect

        with pytest.raises(SandboxLaunchError):
            manager.setup(ACL_CONFIG)

        # Teardown calls should have happened (rm -f + network rm)
        cmds = [c[0][0] for c in mock_run.call_args_list]
        teardown_cmds = cmds[2:]  # everything after the failing docker run
        rm_cmds = [c for c in teardown_cmds if "rm" in c]
        assert len(rm_cmds) >= 1, f"Expected teardown calls after failure, got: {teardown_cmds}"

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_inspect_failure_triggers_cleanup(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        """If docker inspect for proxy IP fails, full cleanup happens."""
        call_count = 0

        def side_effect(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                # network create, docker run, network connect all succeed
                return _ok()
            if call_count == 4:
                # docker inspect fails
                raise subprocess.CalledProcessError(
                    returncode=1, cmd="docker", stderr="no such container"
                )
            # Teardown calls succeed
            return _ok()

        mock_run.side_effect = side_effect

        with pytest.raises(SandboxLaunchError):
            manager.setup(ACL_CONFIG)

        # Verify teardown happened
        cmds = [c[0][0] for c in mock_run.call_args_list]
        teardown_cmds = cmds[4:]
        assert any("rm" in c for c in teardown_cmds)

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_empty_ip_raises_sandbox_launch_error(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        """If docker inspect returns empty IP, setup should fail and clean up."""
        call_count = 0

        def side_effect(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return _ok()
            if call_count == 4:
                # docker inspect returns empty IP
                return _ok(stdout="")
            return _ok()

        mock_run.side_effect = side_effect

        with pytest.raises(SandboxLaunchError, match="proxy internal IP"):
            manager.setup(ACL_CONFIG)

    @patch("scc_cli.adapters.egress_topology.subprocess.run")
    def test_timeout_on_network_create_raises(
        self, mock_run: MagicMock, manager: NetworkTopologyManager
    ) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=30)

        with pytest.raises(SandboxLaunchError, match="timed out"):
            manager.setup(ACL_CONFIG)


# ---------------------------------------------------------------------------
# EgressTopologyInfo dataclass
# ---------------------------------------------------------------------------


class TestEgressTopologyInfo:
    """Verify the data transfer object is frozen and holds expected fields."""

    def test_frozen(self) -> None:
        info = EgressTopologyInfo(
            network_name="net", proxy_container_name="proxy", proxy_endpoint="http://1.2.3.4:3128"
        )
        with pytest.raises(AttributeError):
            info.network_name = "changed"  # type: ignore[misc]

    def test_fields(self) -> None:
        info = EgressTopologyInfo(
            network_name="net", proxy_container_name="proxy", proxy_endpoint="http://1.2.3.4:3128"
        )
        assert info.network_name == "net"
        assert info.proxy_container_name == "proxy"
        assert info.proxy_endpoint == "http://1.2.3.4:3128"
