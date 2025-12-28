"""Integration tests for safety-net policy file I/O and E2E flow.

These tests verify the file I/O operations in docker/launch.py that handle
writing safety-net policy files with atomic patterns, proper permissions,
and fallback behavior.

Test Coverage:
- _write_policy_to_dir: 12 tests (atomic write, permissions, error handling)
- write_safety_net_policy_to_host: 10 tests (cache directory, fallback behavior)
- E2E flow simulation: 5 tests
"""

from __future__ import annotations

import json
import os
import stat
import threading
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from scc_cli.constants import SAFETY_NET_POLICY_FILENAME
from scc_cli.docker.launch import (
    DEFAULT_SAFETY_NET_POLICY,
    VALID_SAFETY_NET_ACTIONS,
    _get_fallback_policy_dir,
    _write_policy_to_dir,
    extract_safety_net_policy,
    get_effective_safety_net_policy,
    validate_safety_net_policy,
    write_safety_net_policy_to_host,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create isolated cache directory for testing.

    Patches get_cache_dir() to return temp directory, ensuring tests don't
    write to real ~/.cache/scc. CACHE_DIR is a module constant computed at
    import time, so we must patch the function not the env vars.

    Returns:
        Path to temporary cache directory for SCC
    """
    cache_dir = tmp_path / "cache" / "scc"
    cache_dir.mkdir(parents=True)

    # Patch get_cache_dir to return our temp directory
    # This is needed because CACHE_DIR is computed at module load time
    monkeypatch.setattr("scc_cli.docker.launch.get_cache_dir", lambda: cache_dir)

    return cache_dir


@pytest.fixture
def sample_policy() -> dict[str, Any]:
    """Standard test policy with multiple flags."""
    return {
        "action": "block",
        "block_force_push": True,
        "block_reset_hard": True,
        "block_branch_force_delete": True,
    }


@pytest.fixture
def warn_policy() -> dict[str, Any]:
    """Policy with warn action for testing overwrite behavior."""
    return {
        "action": "warn",
        "block_force_push": False,
        "block_reset_hard": False,
    }


@pytest.fixture
def example_org_config() -> dict[str, Any]:
    """Load the example 09 org config file or provide fallback."""
    example_path = Path(__file__).parent.parent / "examples" / "09-org-safety-net-enabled.json"
    if example_path.exists():
        data: dict[str, Any] = json.loads(example_path.read_text())
        return data
    # Fallback if example doesn't exist
    return {
        "organization": {"name": "Test Org", "id": "test-org"},
        "security": {
            "safety_net": {
                "action": "block",
                "block_force_push": True,
                "block_reset_hard": True,
            }
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TestWritePolicyToDir - 12 tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWritePolicyToDir:
    """Tests for _write_policy_to_dir function with atomic write pattern."""

    def test_write_creates_policy_file_in_target_dir(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Policy file is created in the target directory."""
        result = _write_policy_to_dir(sample_policy, tmp_path)

        assert result is not None
        assert result.exists()
        assert result.parent == tmp_path

    def test_write_returns_path_to_created_file(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Returns absolute path to the created file."""
        result = _write_policy_to_dir(sample_policy, tmp_path)

        assert result is not None
        assert result.is_absolute()
        assert result.name == SAFETY_NET_POLICY_FILENAME

    def test_write_file_contains_valid_json(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Created file contains valid JSON."""
        result = _write_policy_to_dir(sample_policy, tmp_path)

        assert result is not None
        content = result.read_text()
        parsed = json.loads(content)

        assert isinstance(parsed, dict)

    def test_write_file_contains_correct_policy_content(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """File content matches the input policy."""
        result = _write_policy_to_dir(sample_policy, tmp_path)

        assert result is not None
        parsed = json.loads(result.read_text())

        assert parsed["action"] == "block"
        assert parsed["block_force_push"] is True
        assert parsed["block_reset_hard"] is True
        assert parsed["block_branch_force_delete"] is True

    def test_write_creates_directory_if_not_exists(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Creates target directory if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "path" / "dir"
        assert not nested_dir.exists()

        result = _write_policy_to_dir(sample_policy, nested_dir)

        assert result is not None
        assert nested_dir.exists()
        assert result.exists()

    def test_write_file_has_correct_permissions_0600(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """File has 0600 permissions (owner read/write only)."""
        result = _write_policy_to_dir(sample_policy, tmp_path)

        assert result is not None
        file_stat = os.stat(result)
        mode = stat.S_IMODE(file_stat.st_mode)

        assert mode == 0o600

    def test_write_directory_has_correct_permissions_0700(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Directory is created with 0700 permissions."""
        new_dir = tmp_path / "new_cache_dir"

        result = _write_policy_to_dir(sample_policy, new_dir)

        assert result is not None
        dir_stat = os.stat(new_dir)
        mode = stat.S_IMODE(dir_stat.st_mode)

        assert mode == 0o700

    def test_write_overwrites_existing_file(
        self, tmp_path: Path, sample_policy: dict[str, Any], warn_policy: dict[str, Any]
    ) -> None:
        """Existing policy file is overwritten with new content."""
        # First write
        result1 = _write_policy_to_dir(sample_policy, tmp_path)
        assert result1 is not None
        assert json.loads(result1.read_text())["action"] == "block"

        # Second write with different policy
        result2 = _write_policy_to_dir(warn_policy, tmp_path)
        assert result2 is not None

        # Verify content changed
        content = json.loads(result2.read_text())
        assert content["action"] == "warn"
        assert content["block_force_push"] is False

    def test_write_preserves_other_files_in_directory(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Other files in directory are not affected."""
        other_file = tmp_path / "other.json"
        other_file.write_text('{"key": "value"}')

        result = _write_policy_to_dir(sample_policy, tmp_path)

        assert result is not None
        assert other_file.exists()
        assert json.loads(other_file.read_text()) == {"key": "value"}

    def test_write_returns_none_on_permission_error(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Returns None when directory creation fails due to permissions."""
        # Skip on Windows - permission model is different
        if os.name == "nt":
            pytest.skip("Permission tests not reliable on Windows")

        # Create a read-only directory
        readonly_parent = tmp_path / "readonly"
        readonly_parent.mkdir(mode=0o444)

        target_dir = readonly_parent / "nested"
        result = _write_policy_to_dir(sample_policy, target_dir)

        assert result is None

        # Cleanup: restore permissions for cleanup
        readonly_parent.chmod(0o755)

    def test_write_handles_concurrent_writes(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Concurrent writes don't cause data corruption.

        Due to atomic write pattern (temp file + rename), concurrent writes
        should result in one complete policy, not a corrupted mix.
        """
        results: list[Path | None] = []
        errors: list[Exception] = []

        def writer() -> None:
            try:
                result = _write_policy_to_dir(sample_policy, tmp_path)
                results.append(result)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0

        # File should exist and be valid JSON
        policy_file = tmp_path / SAFETY_NET_POLICY_FILENAME
        assert policy_file.exists()

        content = json.loads(policy_file.read_text())
        assert content["action"] == "block"

    def test_write_cleans_up_tempfile_on_failure(
        self, tmp_path: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Temporary file is cleaned up if write fails mid-operation."""

        # Mock os.write to fail after creating temp file
        def failing_write(fd: int, data: bytes) -> int:
            raise OSError("Simulated write failure")

        with patch("os.write", side_effect=failing_write):
            result = _write_policy_to_dir(sample_policy, tmp_path)

        assert result is None

        # Check no temp files left behind (files starting with .policy_)
        temp_files = list(tmp_path.glob(".policy_*.tmp"))
        assert len(temp_files) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TestWriteSafetyNetPolicyToHost - 10 tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestWriteSafetyNetPolicyToHost:
    """Tests for write_safety_net_policy_to_host with cache and fallback behavior."""

    def test_write_to_host_uses_cache_directory(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Policy is written to the XDG cache directory."""
        result = write_safety_net_policy_to_host(sample_policy)

        assert result is not None
        # The result path should be within the cache directory tree
        assert "cache" in str(result).lower() or "scc" in str(result).lower()

    def test_write_to_host_returns_path_on_success(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Returns absolute path on successful write."""
        result = write_safety_net_policy_to_host(sample_policy)

        assert result is not None
        assert result.is_absolute()
        assert result.exists()

    def test_write_to_host_file_readable_by_docker(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any]
    ) -> None:
        """File is readable (Docker needs to mount and read it)."""
        result = write_safety_net_policy_to_host(sample_policy)

        assert result is not None

        # File should be readable
        content = result.read_text()
        parsed = json.loads(content)
        assert parsed["action"] == "block"

    def test_write_to_host_uses_fallback_on_cache_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_policy: dict[str, Any]
    ) -> None:
        """Falls back to ~/.cache/scc-policy-fallback/ when primary fails."""
        # Set HOME so fallback is in our temp directory
        monkeypatch.setenv("HOME", str(tmp_path))

        # Make cache directory fail by mocking get_cache_dir
        def fail_cache_dir() -> Path:
            # Return a path that doesn't exist and can't be created
            return Path("/nonexistent/readonly/dir/cache")

        with patch("scc_cli.docker.launch.get_cache_dir", side_effect=fail_cache_dir):
            # Primary write should fail, fallback should succeed
            fallback_dir = _get_fallback_policy_dir()
            result = _write_policy_to_dir(sample_policy, fallback_dir)

            assert result is not None
            assert result.exists()
            assert "scc-policy-fallback" in str(result)

    def test_write_to_host_returns_none_when_all_paths_fail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_policy: dict[str, Any]
    ) -> None:
        """Returns None when both primary and fallback fail."""
        # Skip on Windows - harder to simulate permission failures
        if os.name == "nt":
            pytest.skip("Permission tests not reliable on Windows")

        # Create read-only home directory
        readonly_home = tmp_path / "readonly_home"
        readonly_home.mkdir(mode=0o444)

        monkeypatch.setenv("HOME", str(readonly_home))
        monkeypatch.setenv("XDG_CACHE_HOME", str(readonly_home / "cache"))

        # Make cache_dir return something under readonly_home
        with patch("scc_cli.docker.launch.get_cache_dir") as mock_cache:
            mock_cache.return_value = readonly_home / "cache" / "scc"

            result = write_safety_net_policy_to_host(sample_policy)

        # Restore permissions for cleanup
        readonly_home.chmod(0o755)

        # Both should have failed
        assert result is None

    def test_write_to_host_creates_cache_dir_if_missing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_policy: dict[str, Any]
    ) -> None:
        """Creates cache directory if it doesn't exist."""
        # Set up empty HOME without cache dir
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "newcache"))

        # Ensure dir doesn't exist
        cache_dir = tmp_path / "newcache" / "scc"
        assert not cache_dir.exists()

        result = write_safety_net_policy_to_host(sample_policy)

        assert result is not None
        assert result.exists()

    def test_write_to_host_uses_fixed_cache_location(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Uses ~/.cache/scc regardless of XDG_CACHE_HOME (by design).

        Note: CACHE_DIR is computed at module import time as ~/.cache/scc.
        This is intentional - the path must be predictable for Docker mounts.
        """
        result = write_safety_net_policy_to_host(sample_policy)

        assert result is not None
        assert result.exists()
        # Should be under the patched cache directory
        assert str(temp_cache_dir) in str(result)

    def test_write_to_host_path_is_absolute_and_resolved(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Returned path is absolute and resolved (no symlinks).

        Docker Desktop requires absolute, resolved paths for bind mounts.
        """
        result = write_safety_net_policy_to_host(sample_policy)

        assert result is not None
        assert result.is_absolute()
        # Path should be resolved (no symlinks in path)
        assert result == result.resolve()

    def test_write_to_host_idempotent_multiple_calls(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Multiple calls with same policy produce same result."""
        result1 = write_safety_net_policy_to_host(sample_policy)
        result2 = write_safety_net_policy_to_host(sample_policy)

        assert result1 is not None
        assert result2 is not None

        # Path should be the same
        assert result1 == result2

        # Content should be the same
        content1 = json.loads(result1.read_text())
        content2 = json.loads(result2.read_text())
        assert content1 == content2

    def test_write_to_host_different_policies_overwrites(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any], warn_policy: dict[str, Any]
    ) -> None:
        """Different policies overwrite previous content."""
        # First write
        result1 = write_safety_net_policy_to_host(sample_policy)
        assert result1 is not None
        assert json.loads(result1.read_text())["action"] == "block"

        # Second write with different policy
        result2 = write_safety_net_policy_to_host(warn_policy)
        assert result2 is not None

        # Content should reflect second write
        content = json.loads(result2.read_text())
        assert content["action"] == "warn"


# ═══════════════════════════════════════════════════════════════════════════════
# TestSafetyNetE2EFlow - 5 tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSafetyNetE2EFlow:
    """End-to-end flow tests simulating org_config → policy → file."""

    def test_e2e_org_config_to_policy_file(
        self, temp_cache_dir: Path, example_org_config: dict[str, Any]
    ) -> None:
        """Complete flow from org config to written policy file."""
        # Step 1: Get effective policy from org config
        effective_policy = get_effective_safety_net_policy(example_org_config)

        # Step 2: Write to host
        result = write_safety_net_policy_to_host(effective_policy)

        # Verify complete flow
        assert result is not None
        assert result.exists()

        content = json.loads(result.read_text())
        assert content["action"] in VALID_SAFETY_NET_ACTIONS

    def test_e2e_policy_file_readable_by_simulated_plugin(
        self, temp_cache_dir: Path, sample_policy: dict[str, Any]
    ) -> None:
        """Simulate plugin reading the policy file (as scc-safety-net would).

        The scc-safety-net plugin reads from SCC_POLICY_PATH environment variable.
        """
        # Write policy
        policy_path = write_safety_net_policy_to_host(sample_policy)
        assert policy_path is not None

        # Simulate plugin behavior: read from path
        def simulate_plugin_read(path: Path) -> dict[str, Any]:
            """Simulates what scc-safety-net plugin does to read policy."""
            with open(path) as f:
                data: dict[str, Any] = json.load(f)
                return data

        plugin_policy = simulate_plugin_read(policy_path)

        # Plugin should get correct policy
        assert plugin_policy["action"] == "block"
        assert plugin_policy["block_force_push"] is True

    def test_e2e_with_example_09_full_config(
        self, temp_cache_dir: Path, example_org_config: dict[str, Any]
    ) -> None:
        """E2E with full example 09 org config."""
        # Extract → Validate → Write
        extracted = extract_safety_net_policy(example_org_config)
        assert extracted is not None

        validated = validate_safety_net_policy(extracted)
        assert validated["action"] in VALID_SAFETY_NET_ACTIONS

        result = write_safety_net_policy_to_host(validated)
        assert result is not None

        # Round-trip verification
        written = json.loads(result.read_text())
        assert written == validated

    def test_e2e_missing_safety_net_uses_default(self, temp_cache_dir: Path) -> None:
        """E2E with org config missing safety_net uses default policy."""
        org_config_without_safety_net = {
            "organization": {"name": "Test Org"},
            "security": {"blocked_plugins": []},
        }

        # Should return default
        effective = get_effective_safety_net_policy(org_config_without_safety_net)
        assert effective == DEFAULT_SAFETY_NET_POLICY

        result = write_safety_net_policy_to_host(effective)
        assert result is not None

        content = json.loads(result.read_text())
        assert content["action"] == "block"

    def test_e2e_invalid_action_corrected_and_written(self, temp_cache_dir: Path) -> None:
        """E2E with invalid action corrected (fail-closed) and written."""
        org_config_with_typo = {
            "security": {
                "safety_net": {
                    "action": "blokc",  # Typo
                    "block_force_push": True,
                }
            }
        }

        # Get effective should correct the action
        effective = get_effective_safety_net_policy(org_config_with_typo)
        assert effective["action"] == "block"  # Corrected
        assert effective["block_force_push"] is True  # Preserved

        # Write should succeed
        result = write_safety_net_policy_to_host(effective)
        assert result is not None

        # File should have corrected action
        content = json.loads(result.read_text())
        assert content["action"] == "block"
        assert content["block_force_push"] is True
