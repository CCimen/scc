"""Characterization tests for docker/launch.py.

These tests capture the current behavior of the Docker launch module
before S02 surgery decomposes it. They protect against accidental behavior
changes during the split.

Target: src/scc_cli/docker/launch.py (run_sandbox 216 lines, 54% coverage)
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.core.errors import SandboxLaunchError
from scc_cli.docker import launch

# ═══════════��═══════════════════════════��══════════════════════════���════════════
# Safety Net Policy Extraction & Validation
# ══════════════════════════���═══════════════════════════════════��════════════════


class TestSafetyPolicyExtraction:
    """Characterize safety-net policy extraction from org config."""

    def test_extract_returns_none_when_org_config_is_none(self) -> None:
        """No org config → no safety-net policy."""
        assert launch.extract_safety_net_policy(None) is None

    def test_extract_returns_none_when_no_security_section(self) -> None:
        """Org config without security section → no policy."""
        assert launch.extract_safety_net_policy({"teams": {}}) is None

    def test_extract_returns_none_when_security_not_dict(self) -> None:
        """Non-dict security value → no policy."""
        assert launch.extract_safety_net_policy({"security": "invalid"}) is None

    def test_extract_returns_none_when_no_safety_net_key(self) -> None:
        """Security section without safety_net → no policy."""
        assert launch.extract_safety_net_policy({"security": {"other": True}}) is None

    def test_extract_returns_policy_when_present(self) -> None:
        """Valid org config with safety_net → returns the policy dict."""
        org_config: dict[str, Any] = {
            "security": {"safety_net": {"action": "warn", "rules": ["no-secrets"]}}
        }
        policy = launch.extract_safety_net_policy(org_config)
        assert policy is not None
        assert policy["action"] == "warn"
        assert policy["rules"] == ["no-secrets"]


class TestSafetyPolicyValidation:
    """Characterize safety-net policy validation (fail-closed behavior)."""

    def test_valid_action_preserved(self) -> None:
        """Valid 'warn' action is kept as-is."""
        result = launch.validate_safety_net_policy({"action": "warn"})
        assert result["action"] == "warn"

    def test_valid_allow_action_preserved(self) -> None:
        """Valid 'allow' action is kept as-is."""
        result = launch.validate_safety_net_policy({"action": "allow"})
        assert result["action"] == "allow"

    def test_missing_action_defaults_to_block(self) -> None:
        """Missing action → fail-closed to 'block'."""
        result = launch.validate_safety_net_policy({"rules": ["some-rule"]})
        assert result["action"] == "block"

    def test_invalid_action_defaults_to_block(self) -> None:
        """Invalid action value → fail-closed to 'block'."""
        result = launch.validate_safety_net_policy({"action": "yolo"})
        assert result["action"] == "block"

    def test_extra_keys_preserved(self) -> None:
        """Extra keys in policy are preserved through validation."""
        result = launch.validate_safety_net_policy({"action": "warn", "custom": True})
        assert result["custom"] is True


class TestEffectivePolicy:
    """Characterize get_effective_safety_net_policy fallback behavior."""

    def test_returns_default_when_org_config_none(self) -> None:
        """No org config → DEFAULT_SAFETY_NET_POLICY (block)."""
        result = launch.get_effective_safety_net_policy(None)
        assert result["action"] == "block"

    def test_returns_validated_custom_policy_when_present(self) -> None:
        """Valid org config → validated custom policy."""
        org: dict[str, Any] = {"security": {"safety_net": {"action": "allow"}}}
        result = launch.get_effective_safety_net_policy(org)
        assert result["action"] == "allow"

    def test_returns_default_when_safety_net_missing(self) -> None:
        """Org config without safety_net → default block policy."""
        result = launch.get_effective_safety_net_policy({"security": {}})
        assert result["action"] == "block"


# ════════════════════════════════��═══════════════════════════════════��══════════
# Policy Host File Writing
# ══════════════��══════════════��═════════════════════════════════════════════════


class TestWritePolicyToDir:
    """Characterize atomic policy writing to host."""

    def test_writes_policy_file_to_dir(self, tmp_path: Path) -> None:
        """Policy is written as JSON to the target directory."""
        result = launch._write_policy_to_dir({"action": "warn"}, tmp_path)
        assert result is not None
        content = json.loads(result.read_text())
        assert content["action"] == "warn"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        """Creates parent directories if they don't exist."""
        target = tmp_path / "deep" / "nested" / "dir"
        result = launch._write_policy_to_dir({"action": "block"}, target)
        assert result is not None
        assert result.exists()

    def test_returns_none_on_unwritable_dir(self) -> None:
        """Returns None if the directory cannot be created."""
        # /proc/fake is never writable
        result = launch._write_policy_to_dir({"action": "block"}, Path("/proc/fake/deep"))
        assert result is None


# ════════════════════════════════���═══════════════════════════════════════���══════
# run_sandbox Failure Branches
# ════════════════════════════���════════════════════════════════���═════════════════


class TestRunSandboxFailures:
    """Characterize run_sandbox error handling for Docker-unavailable scenarios."""

    @patch("scc_cli.docker.launch.write_safety_net_policy_to_host")
    @patch("scc_cli.docker.launch.get_effective_safety_net_policy")
    @patch("scc_cli.docker.launch.reset_global_settings", return_value=True)
    @patch("scc_cli.docker.launch._sync_credentials_from_existing_containers")
    @patch("scc_cli.docker.launch._preinit_credential_volume")
    @patch("subprocess.run")
    @patch("os.name", "posix")
    def test_raises_on_detached_failure(
        self,
        mock_run: MagicMock,
        mock_preinit: MagicMock,
        mock_sync: MagicMock,
        mock_reset: MagicMock,
        mock_policy: MagicMock,
        mock_write: MagicMock,
        tmp_path: Path,
    ) -> None:
        """run_sandbox raises SandboxLaunchError when detached container creation fails."""
        mock_policy.return_value = {"action": "block"}
        mock_write.return_value = tmp_path / "policy.json"
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Docker daemon not running",
        )

        with pytest.raises(SandboxLaunchError, match="Failed to create Docker sandbox"):
            launch.run_sandbox(workspace=tmp_path, ensure_credentials=True)

    @patch("scc_cli.docker.launch.write_safety_net_policy_to_host")
    @patch("scc_cli.docker.launch.get_effective_safety_net_policy")
    @patch("scc_cli.docker.launch.reset_global_settings", return_value=True)
    @patch("scc_cli.docker.launch._sync_credentials_from_existing_containers")
    @patch("scc_cli.docker.launch._preinit_credential_volume")
    @patch("subprocess.run")
    @patch("os.name", "posix")
    def test_raises_on_empty_container_id(
        self,
        mock_run: MagicMock,
        mock_preinit: MagicMock,
        mock_sync: MagicMock,
        mock_reset: MagicMock,
        mock_policy: MagicMock,
        mock_write: MagicMock,
        tmp_path: Path,
    ) -> None:
        """run_sandbox raises when detached start returns empty container ID."""
        mock_policy.return_value = {"action": "block"}
        mock_write.return_value = tmp_path / "policy.json"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="",  # Empty container ID
            stderr="",
        )

        with pytest.raises(SandboxLaunchError, match="empty container ID"):
            launch.run_sandbox(workspace=tmp_path, ensure_credentials=True)

    @patch("scc_cli.docker.launch.write_safety_net_policy_to_host")
    @patch("scc_cli.docker.launch.get_effective_safety_net_policy")
    @patch("scc_cli.docker.launch.reset_global_settings", return_value=False)
    @patch("scc_cli.docker.launch._sync_credentials_from_existing_containers")
    @patch("scc_cli.docker.launch._preinit_credential_volume")
    @patch("scc_cli.docker.launch._create_symlinks_in_container")
    @patch("scc_cli.docker.launch._start_migration_loop")
    @patch("subprocess.run")
    @patch("os.execvp")
    @patch("os.name", "posix")
    def test_reset_failure_continues_with_warning(
        self,
        mock_execvp: MagicMock,
        mock_run: MagicMock,
        mock_migration: MagicMock,
        mock_symlinks: MagicMock,
        mock_preinit: MagicMock,
        mock_sync: MagicMock,
        mock_reset: MagicMock,
        mock_policy: MagicMock,
        mock_write: MagicMock,
        tmp_path: Path,
    ) -> None:
        """run_sandbox continues (doesn't crash) when reset_global_settings returns False."""
        mock_policy.return_value = {"action": "block"}
        mock_write.return_value = tmp_path / "policy.json"
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="container123",
            stderr="",
        )
        # execvp should not return; raise to exit the flow
        mock_execvp.side_effect = SystemExit(0)

        with pytest.raises(SystemExit):
            launch.run_sandbox(workspace=tmp_path, ensure_credentials=True)

        # Verify it got past reset failure to the run phase
        assert mock_run.called


# ══════════════��═══════════════════════���═════════════════════════════════���══════
# Mount Race Detection
# ═══════════════════════════════���═════════════════════════���═════════════════════


class TestMountRaceDetection:
    """Characterize _is_mount_race_error detection patterns."""

    def test_detects_bind_source_error(self) -> None:
        """'bind source path does not exist' is a retryable mount race."""
        assert launch._is_mount_race_error("Error: bind source path does not exist") is True

    def test_detects_no_such_file(self) -> None:
        """'no such file or directory' is a retryable mount race."""
        assert launch._is_mount_race_error("Error: no such file or directory") is True

    def test_rejects_unrelated_error(self) -> None:
        """Unrelated Docker errors are not mount race conditions."""
        assert launch._is_mount_race_error("permission denied") is False

    def test_case_insensitive(self) -> None:
        """Detection is case-insensitive."""
        assert launch._is_mount_race_error("BIND SOURCE PATH DOES NOT EXIST") is True


# ═════════════════════════════════════���═════════════════════════════════════════
# inject_file_to_sandbox_volume
# ═══════════════════════════════════════════════════════════════════════════════


class TestInjectFile:
    """Characterize inject_file_to_sandbox_volume."""

    @patch("subprocess.run")
    def test_inject_success(self, mock_run: MagicMock) -> None:
        """Returns True when docker run succeeds."""
        mock_run.return_value = MagicMock(returncode=0)
        result = launch.inject_file_to_sandbox_volume("test.json", '{"key": "val"}')
        assert result is True
        assert mock_run.called

    @patch("subprocess.run")
    def test_inject_failure(self, mock_run: MagicMock) -> None:
        """Returns False when docker run fails."""
        mock_run.return_value = MagicMock(returncode=1)
        result = launch.inject_file_to_sandbox_volume("test.json", "content")
        assert result is False

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=30))
    def test_inject_timeout(self, mock_run: MagicMock) -> None:
        """Returns False on timeout (no exception propagated)."""
        result = launch.inject_file_to_sandbox_volume("test.json", "content")
        assert result is False

    @patch("subprocess.run", side_effect=FileNotFoundError("docker not found"))
    def test_inject_docker_not_found(self, mock_run: MagicMock) -> None:
        """Returns False when docker binary is not found."""
        result = launch.inject_file_to_sandbox_volume("test.json", "content")
        assert result is False
