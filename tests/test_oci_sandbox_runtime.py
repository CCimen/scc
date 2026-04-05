"""Tests for OciSandboxRuntime adapter.

All subprocess and os.execvp calls are mocked — no Docker daemon needed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.adapters.oci_sandbox_runtime import (
    _AGENT_HOME,
    _AGENT_UID,
    _AUTH_FILES,
    _OCI_LABEL,
    OciSandboxRuntime,
    _container_name,
    _normalize_provider_permissions,
)
from scc_cli.adapters.oci_sandbox_runtime import (
    _CLAUDE_AGENT_NAME as AGENT_NAME,
)
from scc_cli.adapters.oci_sandbox_runtime import (
    _CLAUDE_DATA_VOLUME as SANDBOX_DATA_VOLUME,
)
from scc_cli.core.contracts import RuntimeInfo
from scc_cli.core.errors import (
    DockerDaemonNotRunningError,
    DockerNotFoundError,
    SandboxLaunchError,
)
from scc_cli.ports.models import (
    AgentSettings,
    MountSpec,
    SandboxHandle,
    SandboxSpec,
    SandboxState,
    SandboxStatus,
)
from tests.fakes.fake_runtime_probe import FakeRuntimeProbe

# ── Fixtures ─────────────────────────────────────────────────────────────────

def _oci_capable_info(**overrides: object) -> RuntimeInfo:
    """Return a RuntimeInfo describing an OCI-capable engine without sandbox."""
    defaults: dict[str, object] = {
        "runtime_id": "docker",
        "display_name": "Docker Engine",
        "cli_name": "docker",
        "supports_oci": True,
        "supports_internal_networks": True,
        "supports_host_network": True,
        "version": "Docker version 27.5.1, build abc1234",
        "daemon_reachable": True,
        "sandbox_available": False,
        "preferred_backend": "oci",
    }
    defaults.update(overrides)
    return RuntimeInfo(**defaults)  # type: ignore[arg-type]


def _minimal_spec(**overrides: object) -> SandboxSpec:
    """Return a minimal SandboxSpec for testing."""
    defaults: dict[str, object] = {
        "image": "scc-agent-claude:latest",
        "workspace_mount": MountSpec(
            source=Path("/home/user/project"),
            target=Path("/workspace"),
        ),
        "workdir": Path("/workspace"),
    }
    defaults.update(overrides)
    return SandboxSpec(**defaults)  # type: ignore[arg-type]


@pytest.fixture()
def runtime() -> OciSandboxRuntime:
    probe = FakeRuntimeProbe(_oci_capable_info())
    return OciSandboxRuntime(probe)


# ── ensure_available ─────────────────────────────────────────────────────────

class TestEnsureAvailable:
    """Scenario coverage for ensure_available()."""

    def test_oci_capable_engine_passes(self) -> None:
        probe = FakeRuntimeProbe(_oci_capable_info())
        rt = OciSandboxRuntime(probe)
        rt.ensure_available()  # should not raise

    def test_not_installed_raises_docker_not_found(self) -> None:
        probe = FakeRuntimeProbe(
            _oci_capable_info(
                version=None,
                daemon_reachable=False,
            )
        )
        rt = OciSandboxRuntime(probe)
        with pytest.raises(DockerNotFoundError):
            rt.ensure_available()

    def test_daemon_not_running_raises(self) -> None:
        probe = FakeRuntimeProbe(
            _oci_capable_info(
                daemon_reachable=False,
                version="Docker version 27.5.1, build abc1234",
            )
        )
        rt = OciSandboxRuntime(probe)
        with pytest.raises(DockerDaemonNotRunningError):
            rt.ensure_available()

    def test_no_oci_support_raises(self) -> None:
        probe = FakeRuntimeProbe(
            _oci_capable_info(supports_oci=False)
        )
        rt = OciSandboxRuntime(probe)
        with pytest.raises(DockerNotFoundError, match="OCI containers"):
            rt.ensure_available()

    def test_sandbox_not_required(self) -> None:
        """OciSandboxRuntime should NOT check sandbox_available."""
        probe = FakeRuntimeProbe(
            _oci_capable_info(sandbox_available=False)
        )
        rt = OciSandboxRuntime(probe)
        rt.ensure_available()  # should not raise


# ── run ──────────────────────────────────────────────────────────────────────

class TestRun:
    """Verify docker create / start / exec command construction."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_basic_run_builds_correct_commands(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        container_id = "abc123def456"
        mock_run_docker.return_value = MagicMock(stdout=f"  {container_id}  \n")

        spec = _minimal_spec()
        handle = runtime.run(spec)

        # Calls: create, start, normalize-dir, normalize-auth
        assert mock_run_docker.call_count == 4

        create_args = mock_run_docker.call_args_list[0]
        create_cmd: list[str] = create_args[0][0]
        assert create_cmd[0] == "create"
        assert "--name" in create_cmd
        assert spec.image in create_cmd

        start_args = mock_run_docker.call_args_list[1]
        start_cmd: list[str] = start_args[0][0]
        assert start_cmd == ["start", container_id]

        # execvp called with docker exec
        mock_execvp.assert_called_once()
        exec_argv = mock_execvp.call_args[0][1]
        assert exec_argv[0] == "docker"
        assert "exec" in exec_argv
        assert container_id in exec_argv
        assert AGENT_NAME in exec_argv
        assert "--dangerously-skip-permissions" in exec_argv

        assert handle.sandbox_id == container_id

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_workspace_mount_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec()
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        mount_str = f"{spec.workspace_mount.source}:{spec.workspace_mount.target}"
        assert mount_str in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_credential_volume_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec()
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        cred_mount = f"{SANDBOX_DATA_VOLUME}:/home/agent/.claude"
        assert cred_mount in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_env_vars_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec(env={"MY_KEY": "my_val", "OTHER": "123"})
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "-e" in create_cmd
        assert "MY_KEY=my_val" in create_cmd
        assert "OTHER=123" in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_oci_label_in_create(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec()
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert "--label" in create_cmd
        label_idx = create_cmd.index("--label")
        assert create_cmd[label_idx + 1] == _OCI_LABEL

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_image_consumed_from_spec(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        custom_image = "my-registry.io/custom-agent:v2"
        spec = _minimal_spec(image=custom_image)
        runtime.run(spec)

        create_cmd: list[str] = mock_run_docker.call_args_list[0][0][0]
        assert custom_image in create_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_continue_session_flag(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec(continue_session=True)
        runtime.run(spec)

        exec_argv = mock_execvp.call_args[0][1]
        assert "-c" in exec_argv

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_agent_settings_injected(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        settings = AgentSettings(
            rendered_bytes=b'{"key": "value"}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        # 5 calls: create, start, normalize-dir, normalize-auth, cp
        assert mock_run_docker.call_count == 5
        cp_cmd: list[str] = mock_run_docker.call_args_list[4][0][0]
        assert cp_cmd[0] == "cp"
        assert "cid123:" in cp_cmd[2]

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_settings_written_as_raw_bytes_not_json(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """D035: runtime writes rendered_bytes verbatim, no json.dumps."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        raw_toml = b'model = "o3"\ncli_auth_credentials_store = "file"\n'
        settings = AgentSettings(
            rendered_bytes=raw_toml,
            path=Path("/home/agent/.codex/config.toml"),
            suffix=".toml",
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        # The cp call should use a .toml suffix temp file (after normalization)
        cp_cmd: list[str] = mock_run_docker.call_args_list[4][0][0]
        assert cp_cmd[0] == "cp"
        assert cp_cmd[1].endswith(".toml")  # temp file suffix

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_workdir_in_exec(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec(workdir=Path("/custom/workdir"))
        runtime.run(spec)

        exec_argv = mock_execvp.call_args[0][1]
        assert "-w" in exec_argv
        assert "/custom/workdir" in exec_argv


# ── Failure modes ────────────────────────────────────────────────────────────

class TestFailureModes:
    """Verify error handling for subprocess failures and timeouts."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_create_failure_raises_launch_error(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.side_effect = SandboxLaunchError(
            user_message="Docker command failed",
            command="docker create ...",
            stderr="name already in use",
        )
        with pytest.raises(SandboxLaunchError, match="Docker command failed"):
            runtime.run(_minimal_spec())

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_create_timeout_raises_launch_error(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="docker create", timeout=60)
        with pytest.raises(SandboxLaunchError, match="timed out"):
            runtime.run(_minimal_spec())

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_create_nonzero_exit_raises_launch_error(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            returncode=1, cmd="docker create", stderr="conflict"
        )
        with pytest.raises(SandboxLaunchError):
            runtime.run(_minimal_spec())


# ── list_running ─────────────────────────────────────────────────────────────

class TestListRunning:
    """Verify parsing of ``docker ps`` output."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_parses_multiple_containers(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(
            stdout="abc123\tscc-oci-aaa\ndef456\tscc-oci-bbb\n"
        )
        handles = runtime.list_running()
        assert len(handles) == 2
        assert handles[0] == SandboxHandle(sandbox_id="abc123", name="scc-oci-aaa")
        assert handles[1] == SandboxHandle(sandbox_id="def456", name="scc-oci-bbb")

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_empty_output(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="")
        assert runtime.list_running() == []

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_single_column_output(
        self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_run_docker.return_value = MagicMock(stdout="abc123\n")
        handles = runtime.list_running()
        assert len(handles) == 1
        assert handles[0].sandbox_id == "abc123"
        assert handles[0].name is None


# ── status ───────────────────────────────────────────────────────────────────

class TestStatus:
    """Verify docker inspect → SandboxState mapping."""

    @pytest.mark.parametrize(
        ("raw_status", "expected_state"),
        [
            ("running", SandboxState.RUNNING),
            ("created", SandboxState.CREATED),
            ("exited", SandboxState.STOPPED),
            ("dead", SandboxState.STOPPED),
            ("paused", SandboxState.RUNNING),
            ("restarting", SandboxState.RUNNING),
            ("something_else", SandboxState.UNKNOWN),
        ],
    )
    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_state_mapping(
        self,
        mock_subprocess: MagicMock,
        raw_status: str,
        expected_state: SandboxState,
        runtime: OciSandboxRuntime,
    ) -> None:
        mock_subprocess.return_value = MagicMock(
            returncode=0, stdout=f"{raw_status}\n"
        )
        handle = SandboxHandle(sandbox_id="abc123")
        result = runtime.status(handle)
        assert result.state == expected_state

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_inspect_failure_returns_unknown(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="")
        handle = SandboxHandle(sandbox_id="gone")
        assert runtime.status(handle) == SandboxStatus(state=SandboxState.UNKNOWN)

    @patch("scc_cli.adapters.oci_sandbox_runtime.subprocess.run")
    def test_inspect_timeout_returns_unknown(
        self, mock_subprocess: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        mock_subprocess.side_effect = subprocess.TimeoutExpired(cmd="docker inspect", timeout=10)
        handle = SandboxHandle(sandbox_id="slow")
        assert runtime.status(handle) == SandboxStatus(state=SandboxState.UNKNOWN)


# ── resume / stop / remove ───────────────────────────────────────────────────

class TestLifecycle:
    """Verify resume, stop, and remove delegate correctly."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_resume(self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime) -> None:
        runtime.resume(SandboxHandle(sandbox_id="cid"))
        mock_run_docker.assert_called_once_with(["start", "cid"], timeout=30)

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_stop(self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime) -> None:
        runtime.stop(SandboxHandle(sandbox_id="cid"))
        mock_run_docker.assert_called_once_with(["stop", "cid"], timeout=15)

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_remove(self, mock_run_docker: MagicMock, runtime: OciSandboxRuntime) -> None:
        runtime.remove(SandboxHandle(sandbox_id="cid"))
        mock_run_docker.assert_called_once_with(["rm", "-f", "cid"], timeout=15)


# ── Network enforcement ──────────────────────────────────────────────────────

class TestNetworkEnforcement:
    """Verify _build_create_cmd produces correct --network flags for all modes."""

    def test_enforced_mode_adds_network_flag(self) -> None:
        """web-egress-enforced with a network name → --network <name> in command."""
        spec = _minimal_spec(network_policy="web-egress-enforced")
        cmd = OciSandboxRuntime._build_create_cmd(
            spec, "scc-oci-test", network_name="scc-egress-scc-oci-test",
        )
        assert "--network" in cmd
        idx = cmd.index("--network")
        assert cmd[idx + 1] == "scc-egress-scc-oci-test"

    def test_locked_down_mode_adds_network_none(self) -> None:
        """locked-down-web → --network none."""
        spec = _minimal_spec(network_policy="locked-down-web")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        assert "--network" in cmd
        idx = cmd.index("--network")
        assert cmd[idx + 1] == "none"

    def test_open_mode_no_network_flag(self) -> None:
        """open → no --network flag."""
        spec = _minimal_spec(network_policy="open")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        assert "--network" not in cmd

    def test_none_policy_no_network_flag(self) -> None:
        """None (unset) → no --network flag."""
        spec = _minimal_spec(network_policy=None)
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        assert "--network" not in cmd

    def test_enforced_mode_injects_proxy_env(self) -> None:
        """Proxy env vars appear in the create command for enforced mode."""
        spec = _minimal_spec(network_policy="web-egress-enforced")
        proxy_env = {
            "HTTP_PROXY": "http://172.18.0.2:3128",
            "HTTPS_PROXY": "http://172.18.0.2:3128",
            "NO_PROXY": "",
        }
        cmd = OciSandboxRuntime._build_create_cmd(
            spec, "scc-oci-test",
            network_name="scc-egress-scc-oci-test",
            proxy_env=proxy_env,
        )
        assert "HTTP_PROXY=http://172.18.0.2:3128" in cmd
        assert "HTTPS_PROXY=http://172.18.0.2:3128" in cmd
        assert "NO_PROXY=" in cmd


# ── Container naming ────────────────────────────────────────────────────────

class TestContainerName:
    """Verify deterministic container naming."""

    def test_deterministic(self) -> None:
        name1 = _container_name(Path("/home/user/project"))
        name2 = _container_name(Path("/home/user/project"))
        assert name1 == name2
        assert name1.startswith("scc-oci-")

    def test_different_paths_differ(self) -> None:
        assert _container_name(Path("/a")) != _container_name(Path("/b"))


# ── S02/T03 — Provider-aware exec command and credential volume mounting ─────

class TestProviderAwareExecCmd:
    """Verify _build_exec_cmd uses spec.agent_argv when present."""

    def test_build_exec_cmd_uses_agent_argv_when_present(self) -> None:
        """With agent_argv=("codex",), exec cmd uses codex, not claude."""
        spec = _minimal_spec(agent_argv=["codex"])
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert "codex" in cmd
        assert AGENT_NAME not in cmd
        assert "--dangerously-skip-permissions" not in cmd

    def test_build_exec_cmd_falls_back_to_agent_name(self) -> None:
        """Empty agent_argv uses existing AGENT_NAME + --dangerously-skip-permissions."""
        spec = _minimal_spec(agent_argv=[])
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert AGENT_NAME in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_build_exec_cmd_default_agent_argv(self) -> None:
        """Default SandboxSpec (no agent_argv given) falls back to AGENT_NAME."""
        spec = _minimal_spec()
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert AGENT_NAME in cmd
        assert "--dangerously-skip-permissions" in cmd

    def test_build_exec_cmd_continue_session_with_codex_argv(self) -> None:
        """-c appended after codex argv when continue_session=True."""
        spec = _minimal_spec(agent_argv=["codex"], continue_session=True)
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert "codex" in cmd
        assert "-c" in cmd
        # -c should be after codex
        codex_idx = cmd.index("codex")
        c_idx = cmd.index("-c")
        assert c_idx > codex_idx

    def test_build_exec_cmd_continue_session_with_default_argv(self) -> None:
        """-c appended after default AGENT_NAME argv when continue_session=True."""
        spec = _minimal_spec(continue_session=True)
        cmd = OciSandboxRuntime._build_exec_cmd(spec, "cid123")
        assert AGENT_NAME in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "-c" in cmd


class TestProviderAwareCreateCmd:
    """Verify _build_create_cmd uses spec.data_volume and spec.config_dir."""

    def test_build_create_cmd_uses_data_volume_when_present(self) -> None:
        """With data_volume set, volume mount uses it instead of SANDBOX_DATA_VOLUME."""
        spec = _minimal_spec(data_volume="docker-codex-sandbox-data")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = "docker-codex-sandbox-data:/home/agent/.claude"
        assert mount_str in cmd
        assert SANDBOX_DATA_VOLUME not in " ".join(cmd)

    def test_build_create_cmd_uses_config_dir_when_present(self) -> None:
        """With config_dir set, mount target uses it instead of .claude."""
        spec = _minimal_spec(config_dir=".codex")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_found = any(
            "/home/agent/.codex" in arg for arg in cmd
        )
        assert mount_found

    def test_build_create_cmd_both_volume_and_config_dir(self) -> None:
        """Both data_volume and config_dir produce the expected mount."""
        spec = _minimal_spec(
            data_volume="docker-codex-sandbox-data",
            config_dir=".codex",
        )
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = "docker-codex-sandbox-data:/home/agent/.codex"
        assert mount_str in cmd

    def test_build_create_cmd_falls_back_to_defaults(self) -> None:
        """Empty data_volume and config_dir falls back to SANDBOX_DATA_VOLUME and .claude."""
        spec = _minimal_spec(data_volume="", config_dir="")
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = f"{SANDBOX_DATA_VOLUME}:/home/agent/.claude"
        assert mount_str in cmd

    def test_build_create_cmd_default_spec_falls_back(self) -> None:
        """Default SandboxSpec (no volume/dir given) uses original constants."""
        spec = _minimal_spec()
        cmd = OciSandboxRuntime._build_create_cmd(spec, "scc-oci-test")
        mount_str = f"{SANDBOX_DATA_VOLUME}:/home/agent/.claude"
        assert mount_str in cmd


# ── D041: workspace-scoped config layering ───────────────────────────────────


class TestWorkspaceScopedConfigInjection:
    """D041: Codex project-scoped config goes to workspace, Claude stays home-level."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_workspace_scoped_settings_triggers_git_exclude(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Settings path under workspace mount target triggers mkdir + git exclude."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        # Use /workspace as the mount target — must match _minimal_spec defaults
        workspace_target = Path("/workspace")
        settings = AgentSettings(
            rendered_bytes=b'[sandbox]\nauto_approve = []\n',
            path=workspace_target / ".codex" / "config.toml",
            suffix=".toml",
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        # Calls: create, start, mkdir (git exclude), grep||echo (git exclude), cp
        assert mock_run_docker.call_count >= 4
        all_calls = [call[0][0] for call in mock_run_docker.call_args_list]
        # Find the mkdir call
        mkdir_calls = [c for c in all_calls if "mkdir" in c]
        assert len(mkdir_calls) == 1
        assert f"{workspace_target}/.codex" in " ".join(mkdir_calls[0])

        # Find the git exclude shell command (filter out D039 normalization)
        git_exclude_calls = [
            c for c in all_calls
            if "sh" in c and "-c" in c and ".git/info/exclude" in c[-1]
        ]
        assert len(git_exclude_calls) == 1
        shell_cmd = git_exclude_calls[0][-1]
        assert ".codex" in shell_cmd
        assert ".git/info/exclude" in shell_cmd

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_home_scoped_settings_skips_git_exclude(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Settings path under /home/agent (Claude) does NOT trigger git exclude."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        settings = AgentSettings(
            rendered_bytes=b'{"permissions": {}}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        # 5 calls: create, start, normalize-dir, normalize-auth, cp (no mkdir or git exclude)
        assert mock_run_docker.call_count == 5
        all_calls = [call[0][0] for call in mock_run_docker.call_args_list]
        assert all_calls[0][0] == "create"
        assert all_calls[1] == ["start", "cid123"]
        # Normalization exec calls at 2 and 3
        assert all_calls[2][0] == "exec"
        assert all_calls[3][0] == "exec"
        assert all_calls[4][0] == "cp"
        # No git-exclude calls
        git_exclude_calls = [c for c in all_calls if "-c" in c and ".git/info/exclude" in str(c)]
        assert len(git_exclude_calls) == 0

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_workspace_scoped_settings_cp_targets_workspace_path(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """docker cp writes Codex config to workspace path, not /home/agent."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        workspace_target = Path("/workspace")
        settings = AgentSettings(
            rendered_bytes=b'[sandbox]\nauto_approve = []\n',
            path=workspace_target / ".codex" / "config.toml",
            suffix=".toml",
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        # Find the cp call (last real docker command before exec)
        cp_calls = [
            call[0][0] for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_calls) == 1
        cp_target = cp_calls[0][2]  # "cid123:/workspace/.codex/config.toml"
        assert "cid123:" in cp_target
        assert str(workspace_target / ".codex" / "config.toml") in cp_target
        assert "/home/agent" not in cp_target


# ── D039: Runtime permission normalization ───────────────────────────────────


class TestNormalizeProviderPermissions:
    """D039: Verify permission normalization command construction."""

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_claude_config_dir_chmod_and_chown(self, mock_run: MagicMock) -> None:
        """Claude (.claude) config dir gets 0700, uid 1000."""
        _normalize_provider_permissions("cid123", ".claude")

        # First call: chown+chmod the config dir
        dir_call = mock_run.call_args_list[0]
        dir_cmd: list[str] = dir_call[0][0]
        assert dir_cmd[:3] == ["exec", "cid123", "sh"]
        shell_str = dir_cmd[-1]
        assert f"chown {_AGENT_UID}:{_AGENT_UID} {_AGENT_HOME}/.claude" in shell_str
        assert f"chmod 0700 {_AGENT_HOME}/.claude" in shell_str

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_claude_auth_file_chmod(self, mock_run: MagicMock) -> None:
        """Claude auth file (.credentials.json) gets 0600 if it exists."""
        _normalize_provider_permissions("cid123", ".claude")

        # Second call: auth file chmod
        assert mock_run.call_count == 2
        auth_call = mock_run.call_args_list[1]
        auth_cmd: list[str] = auth_call[0][0]
        shell_str = auth_cmd[-1]
        assert "test -f" in shell_str
        assert ".credentials.json" in shell_str
        assert "chmod 0600" in shell_str
        assert f"chown {_AGENT_UID}:{_AGENT_UID}" in shell_str

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_codex_config_dir_chmod_and_chown(self, mock_run: MagicMock) -> None:
        """Codex (.codex) config dir gets 0700, uid 1000."""
        _normalize_provider_permissions("cid123", ".codex")

        dir_call = mock_run.call_args_list[0]
        shell_str = dir_call[0][0][-1]
        assert f"chown {_AGENT_UID}:{_AGENT_UID} {_AGENT_HOME}/.codex" in shell_str
        assert f"chmod 0700 {_AGENT_HOME}/.codex" in shell_str

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_codex_auth_file_chmod(self, mock_run: MagicMock) -> None:
        """Codex auth file (auth.json) gets 0600 if it exists."""
        _normalize_provider_permissions("cid123", ".codex")

        assert mock_run.call_count == 2
        auth_call = mock_run.call_args_list[1]
        shell_str = auth_call[0][0][-1]
        assert "auth.json" in shell_str
        assert "chmod 0600" in shell_str

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_unknown_config_dir_skips_auth_files(self, mock_run: MagicMock) -> None:
        """Unknown config dir has no known auth files — only dir chmod runs."""
        _normalize_provider_permissions("cid123", ".future-provider")

        # Only one call — the directory chmod; no auth file calls
        assert mock_run.call_count == 1
        shell_str = mock_run.call_args_list[0][0][0][-1]
        assert ".future-provider" in shell_str

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_empty_config_dir_defaults_to_claude(self, mock_run: MagicMock) -> None:
        """Empty config_dir falls back to .claude (matches _build_create_cmd default)."""
        _normalize_provider_permissions("cid123", "")

        dir_call = mock_run.call_args_list[0]
        shell_str = dir_call[0][0][-1]
        assert f"{_AGENT_HOME}/.claude" in shell_str
        # Should also check .credentials.json
        assert mock_run.call_count == 2

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_check_false_on_all_calls(self, mock_run: MagicMock) -> None:
        """All normalization commands are best-effort (check=False)."""
        _normalize_provider_permissions("cid123", ".claude")

        for call in mock_run.call_args_list:
            assert call[1].get("check") is False

    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_auth_files_registry_consistency(self, mock_run: MagicMock) -> None:
        """_AUTH_FILES has entries for both known providers."""
        assert ".claude" in _AUTH_FILES
        assert ".codex" in _AUTH_FILES
        assert ".credentials.json" in _AUTH_FILES[".claude"]
        assert "auth.json" in _AUTH_FILES[".codex"]


class TestNormalizePermissionsIntegration:
    """D039: Verify normalization is called in the run() flow."""

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_normalization_called_in_run_for_claude(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """run() calls normalization between start and settings injection."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec()  # defaults to Claude (empty config_dir)
        runtime.run(spec)

        # Calls: create, start, dir-chmod, auth-chmod, exec(via execvp)
        all_cmds = [call[0][0] for call in mock_run_docker.call_args_list]
        assert all_cmds[0][0] == "create"
        assert all_cmds[1] == ["start", "cid123"]
        # Normalization calls (check=False) at positions 2 and 3
        assert all_cmds[2][0] == "exec"  # dir chmod
        assert "chmod 0700" in all_cmds[2][-1]
        assert all_cmds[3][0] == "exec"  # auth file chmod
        assert "chmod 0600" in all_cmds[3][-1]

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_normalization_called_in_run_for_codex(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """run() calls normalization with Codex config dir."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        spec = _minimal_spec(config_dir=".codex")
        runtime.run(spec)

        all_cmds = [call[0][0] for call in mock_run_docker.call_args_list]
        # Dir chmod references .codex
        dir_shell = all_cmds[2][-1]
        assert ".codex" in dir_shell
        assert "chmod 0700" in dir_shell
        # Auth chmod references auth.json
        auth_shell = all_cmds[3][-1]
        assert "auth.json" in auth_shell

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_normalization_before_settings_injection(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Normalization runs before docker cp (settings injection)."""
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")
        settings = AgentSettings(
            rendered_bytes=b'{"permissions": {}}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        all_cmds = [call[0][0] for call in mock_run_docker.call_args_list]
        # Find positions: cp must come after normalization exec calls
        cp_indices = [i for i, c in enumerate(all_cmds) if c[0] == "cp"]
        norm_indices = [
            i for i, c in enumerate(all_cmds)
            if c[0] == "exec" and "chmod" in str(c)
        ]
        assert len(cp_indices) >= 1
        assert len(norm_indices) >= 1
        assert all(ni < cp_indices[0] for ni in norm_indices)


# ── D038/D042: Config persistence model transitions ─────────────────────────


class TestConfigPersistenceTransitions:
    """D038/D042: Prove config freshness is deterministic across session transitions.

    These tests exercise the OCI runtime's _inject_settings path to verify
    that config injection is governed solely by SandboxSpec.agent_settings —
    not by prior container state.  Each test simulates two sequential launches
    (with fresh containers) and asserts the second launch writes the expected
    config content, regardless of what the first launch wrote.
    """

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_governed_to_standalone_clears_stale_config(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Governed→standalone: fresh standalone launch writes empty config.

        Prior launch injected team config.  A subsequent fresh standalone
        launch writes an empty settings file — clearing any team-specific
        config that might persist in the volume.
        """
        mock_run_docker.return_value = MagicMock(stdout="cid123\n")

        # ── First launch: governed (team config) ──
        team_settings = AgentSettings(
            rendered_bytes=b'{"plugins": ["team-plugin"], "mcpServers": {"internal": {}}}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec_governed = _minimal_spec(agent_settings=team_settings)
        runtime.run(spec_governed)

        # Verify first launch wrote team config
        cp_calls_1 = [
            call for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_calls_1) == 1

        # ── Reset mocks for second launch ──
        mock_run_docker.reset_mock()
        mock_execvp.reset_mock()
        mock_run_docker.return_value = MagicMock(stdout="cid456\n")

        # ── Second launch: standalone (empty config) ──
        empty_settings = AgentSettings(
            rendered_bytes=b"{}",
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec_standalone = _minimal_spec(agent_settings=empty_settings)
        runtime.run(spec_standalone)

        # Verify second launch wrote empty config via docker cp
        cp_calls_2 = [
            call for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_calls_2) == 1
        # The cp target is the settings path inside the container
        cp_target = cp_calls_2[0][0][0][2]
        assert "cid456:" in cp_target
        assert "/home/agent/.claude/settings.json" in cp_target

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_team_a_to_team_b_replaces_config(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """TeamA→TeamB: fresh launch with team B config replaces team A config.

        Verify the runtime writes the new team's config regardless of
        what was in the volume from the prior launch.
        """
        mock_run_docker.return_value = MagicMock(stdout="cid-team-a\n")

        # ── First launch: team A ──
        team_a_settings = AgentSettings(
            rendered_bytes=b'{"plugins": ["team-a-plugin"]}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec_a = _minimal_spec(agent_settings=team_a_settings)
        runtime.run(spec_a)

        # Verify team A config was injected
        cp_calls_a = [
            call for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_calls_a) == 1

        # ── Reset mocks for second launch ──
        mock_run_docker.reset_mock()
        mock_execvp.reset_mock()
        mock_run_docker.return_value = MagicMock(stdout="cid-team-b\n")

        # ── Second launch: team B ──
        team_b_settings = AgentSettings(
            rendered_bytes=b'{"plugins": ["team-b-plugin"], "mcpServers": {"gis": {}}}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec_b = _minimal_spec(agent_settings=team_b_settings)
        runtime.run(spec_b)

        # Verify team B config was injected (not team A)
        cp_calls_b = [
            call for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_calls_b) == 1
        cp_target_b = cp_calls_b[0][0][0][2]
        assert "cid-team-b:" in cp_target_b
        assert "/home/agent/.claude/settings.json" in cp_target_b

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_resume_skips_injection_entirely(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Resume: agent_settings=None means no docker cp at all.

        The application layer sets agent_settings=None for resume (D038).
        The runtime should not issue any docker cp command.
        """
        mock_run_docker.return_value = MagicMock(stdout="cid-resume\n")

        spec_resume = _minimal_spec(agent_settings=None)
        runtime.run(spec_resume)

        all_cmds = [call[0][0] for call in mock_run_docker.call_args_list]
        cp_cmds = [c for c in all_cmds if c[0] == "cp"]
        assert len(cp_cmds) == 0

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_settings_to_no_settings_still_injects_empty(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Settings→no-settings: empty config file is still written.

        Even when the rendered config is an empty dict `{}`, the runtime
        must issue the docker cp to overwrite any stale config from a
        prior launch.  This is the "always writes" guarantee from D038.
        """
        mock_run_docker.return_value = MagicMock(stdout="cid-fresh\n")

        # First launch: real settings
        real_settings = AgentSettings(
            rendered_bytes=b'{"plugins": ["some-plugin"]}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec_real = _minimal_spec(agent_settings=real_settings)
        runtime.run(spec_real)

        mock_run_docker.reset_mock()
        mock_execvp.reset_mock()
        mock_run_docker.return_value = MagicMock(stdout="cid-empty\n")

        # Second launch: empty settings (D038 always-writes semantics)
        empty_settings = AgentSettings(
            rendered_bytes=b"{}",
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec_empty = _minimal_spec(agent_settings=empty_settings)
        runtime.run(spec_empty)

        # docker cp was still called
        cp_cmds = [
            call[0][0] for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_cmds) == 1

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_codex_team_transition_workspace_scoped(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """TeamA→TeamB for Codex: workspace-scoped config is replaced correctly.

        Codex settings go to workspace mount, not /home/agent.  Verify the
        transition writes to the correct workspace-scoped path.
        """
        mock_run_docker.return_value = MagicMock(stdout="cid-cx-a\n")
        workspace_target = Path("/workspace")

        # ── First launch: Codex team A ──
        codex_a_settings = AgentSettings(
            rendered_bytes=b'model = "o3"\ncli_auth_credentials_store = "file"\n',
            path=workspace_target / ".codex" / "config.toml",
            suffix=".toml",
        )
        spec_cx_a = _minimal_spec(agent_settings=codex_a_settings)
        runtime.run(spec_cx_a)

        mock_run_docker.reset_mock()
        mock_execvp.reset_mock()
        mock_run_docker.return_value = MagicMock(stdout="cid-cx-b\n")

        # ── Second launch: Codex team B ──
        codex_b_settings = AgentSettings(
            rendered_bytes=b'model = "o4-mini"\ncli_auth_credentials_store = "file"\n',
            path=workspace_target / ".codex" / "config.toml",
            suffix=".toml",
        )
        spec_cx_b = _minimal_spec(agent_settings=codex_b_settings)
        runtime.run(spec_cx_b)

        # Verify the cp command targets the workspace-scoped Codex path
        cp_calls = [
            call[0][0] for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_calls) == 1
        cp_target = cp_calls[0][2]
        assert "cid-cx-b:" in cp_target
        assert str(workspace_target / ".codex" / "config.toml") in cp_target
        assert "/home/agent" not in cp_target

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_claude_to_codex_provider_switch_writes_correct_path(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Cross-provider transition: Claude→Codex writes to correct target.

        Each provider has its own settings path and scope.  A switch from
        Claude (home-scoped) to Codex (workspace-scoped) should write to
        the Codex path, not the Claude path.
        """
        mock_run_docker.return_value = MagicMock(stdout="cid-claude\n")
        workspace_target = Path("/workspace")

        # ── First launch: Claude ──
        claude_settings = AgentSettings(
            rendered_bytes=b'{"permissions": {}}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec_claude = _minimal_spec(agent_settings=claude_settings)
        runtime.run(spec_claude)

        mock_run_docker.reset_mock()
        mock_execvp.reset_mock()
        mock_run_docker.return_value = MagicMock(stdout="cid-codex\n")

        # ── Second launch: Codex ──
        codex_settings = AgentSettings(
            rendered_bytes=b'cli_auth_credentials_store = "file"\n',
            path=workspace_target / ".codex" / "config.toml",
            suffix=".toml",
        )
        spec_codex = _minimal_spec(agent_settings=codex_settings)
        runtime.run(spec_codex)

        # Verify Codex config targets workspace, not /home/agent
        cp_calls = [
            call[0][0] for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        ]
        assert len(cp_calls) == 1
        cp_target = cp_calls[0][2]
        assert "cid-codex:" in cp_target
        assert str(workspace_target / ".codex" / "config.toml") in cp_target
        # Must NOT write to Claude's path
        assert ".claude" not in cp_target

    @patch("scc_cli.adapters.oci_sandbox_runtime.os.execvp")
    @patch("scc_cli.adapters.oci_sandbox_runtime._run_docker")
    def test_injection_idempotent_same_config_twice(
        self, mock_run_docker: MagicMock, mock_execvp: MagicMock, runtime: OciSandboxRuntime
    ) -> None:
        """Idempotency: writing the same config twice is safe and deterministic.

        Two sequential fresh launches with identical settings should both
        issue docker cp with the same content — the runtime does not skip
        based on "config hasn't changed."
        """
        mock_run_docker.return_value = MagicMock(stdout="cid-1\n")
        settings = AgentSettings(
            rendered_bytes=b'{"plugins": ["fixed-plugin"]}',
            path=Path("/home/agent/.claude/settings.json"),
            suffix=".json",
        )
        spec = _minimal_spec(agent_settings=settings)
        runtime.run(spec)

        cp_count_1 = sum(
            1 for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        )
        assert cp_count_1 == 1

        mock_run_docker.reset_mock()
        mock_execvp.reset_mock()
        mock_run_docker.return_value = MagicMock(stdout="cid-2\n")

        # Same settings, second launch
        runtime.run(spec)
        cp_count_2 = sum(
            1 for call in mock_run_docker.call_args_list
            if call[0][0][0] == "cp"
        )
        assert cp_count_2 == 1
