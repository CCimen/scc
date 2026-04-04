"""Integration tests for the standalone safety evaluator CLI and shell wrappers.

Tests the full wrapper → evaluator → verdict chain via subprocess calls
to ``python3 -m scc_safety_eval``. Shell wrappers themselves need Docker,
so we test them for structural correctness (existence, permissions, content)
rather than live execution.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WRAPPERS_DIR = _PROJECT_ROOT / "images" / "scc-base" / "wrappers"
_BIN_DIR = _WRAPPERS_DIR / "bin"

_TOOLS = ["git", "curl", "wget", "ssh", "scp", "sftp", "rsync"]


def _run_evaluator(
    args: list[str],
    *,
    policy_path: str | None = None,
    env_override: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the standalone evaluator CLI via subprocess."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_WRAPPERS_DIR)
    if policy_path is not None:
        env["SCC_POLICY_PATH"] = policy_path
    elif "SCC_POLICY_PATH" in env:
        del env["SCC_POLICY_PATH"]
    if env_override:
        env.update(env_override)
    return subprocess.run(
        ["python3", "-m", "scc_safety_eval", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def _write_policy(tmp_dir: str, policy: dict) -> str:
    """Write a policy JSON file and return its path."""
    path = os.path.join(tmp_dir, "policy.json")
    with open(path, "w") as f:
        json.dump(policy, f)
    return path


# ── Shell wrapper structural tests ────────────────────────────────────────


class TestWrapperScripts:
    """Verify shell wrapper scripts exist and are well-formed."""

    @pytest.mark.parametrize("tool", _TOOLS)
    def test_wrapper_exists(self, tool: str) -> None:
        wrapper = _BIN_DIR / tool
        assert wrapper.exists(), f"Wrapper script missing: {wrapper}"

    @pytest.mark.parametrize("tool", _TOOLS)
    def test_wrapper_is_executable(self, tool: str) -> None:
        wrapper = _BIN_DIR / tool
        mode = wrapper.stat().st_mode
        assert mode & stat.S_IXUSR, f"Wrapper not executable: {wrapper}"

    @pytest.mark.parametrize("tool", _TOOLS)
    def test_wrapper_uses_absolute_real_bin(self, tool: str) -> None:
        content = (_BIN_DIR / tool).read_text()
        assert f"REAL_BIN=/usr/bin/{tool}" in content, (
            f"Wrapper for {tool} does not set REAL_BIN to absolute path"
        )

    @pytest.mark.parametrize("tool", _TOOLS)
    def test_wrapper_calls_evaluator(self, tool: str) -> None:
        content = (_BIN_DIR / tool).read_text()
        assert "python3 -m scc_safety_eval" in content, (
            f"Wrapper for {tool} does not invoke the evaluator"
        )

    @pytest.mark.parametrize("tool", _TOOLS)
    def test_wrapper_uses_basename(self, tool: str) -> None:
        """Wrapper passes basename of $0 as tool name — prevents path prefix issues."""
        content = (_BIN_DIR / tool).read_text()
        assert 'basename "$0"' in content, (
            f"Wrapper for {tool} does not use basename for tool name"
        )

    @pytest.mark.parametrize("tool", _TOOLS)
    def test_wrapper_has_bash_shebang(self, tool: str) -> None:
        content = (_BIN_DIR / tool).read_text()
        assert content.startswith("#!/bin/bash"), (
            f"Wrapper for {tool} missing bash shebang"
        )


# ── Evaluator CLI tests (blocked/allowed/fail-closed) ─────────────────────


class TestEvaluatorBlocked:
    """Commands that should be blocked (exit code 2)."""

    def test_git_force_push_blocked(self) -> None:
        result = _run_evaluator(["git", "push", "--force", "origin", "main"])
        assert result.returncode == 2
        assert result.stderr.strip()  # reason on stderr

    def test_curl_blocked(self) -> None:
        result = _run_evaluator(["curl", "https://example.com"])
        assert result.returncode == 2

    def test_wget_blocked(self) -> None:
        result = _run_evaluator(["wget", "https://example.com/file.tar.gz"])
        assert result.returncode == 2

    def test_ssh_blocked(self) -> None:
        result = _run_evaluator(["ssh", "user@host"])
        assert result.returncode == 2

    def test_scp_blocked(self) -> None:
        result = _run_evaluator(["scp", "file.txt", "user@host:/tmp/"])
        assert result.returncode == 2

    def test_sftp_blocked(self) -> None:
        result = _run_evaluator(["sftp", "user@host"])
        assert result.returncode == 2

    def test_rsync_blocked(self) -> None:
        result = _run_evaluator(["rsync", "-avz", "src/", "host:/dst/"])
        assert result.returncode == 2


class TestEvaluatorAllowed:
    """Commands that should be allowed (exit code 0)."""

    def test_git_status_allowed(self) -> None:
        result = _run_evaluator(["git", "status"])
        assert result.returncode == 0

    def test_git_log_allowed(self) -> None:
        result = _run_evaluator(["git", "log", "--oneline"])
        assert result.returncode == 0

    def test_safe_command_ls(self) -> None:
        result = _run_evaluator(["ls", "-la"])
        assert result.returncode == 0

    def test_safe_git_push(self) -> None:
        result = _run_evaluator(["git", "push", "origin", "main"])
        assert result.returncode == 0


class TestEvaluatorFailClosed:
    """Fail-closed behavior when policy is missing or broken."""

    def test_no_policy_path_blocks_dangerous_commands(self) -> None:
        """Without SCC_POLICY_PATH, dangerous commands should still be blocked."""
        result = _run_evaluator(["git", "push", "--force"])
        assert result.returncode == 2

    def test_no_policy_path_allows_safe_commands(self) -> None:
        """Without SCC_POLICY_PATH, safe commands should still be allowed."""
        result = _run_evaluator(["git", "status"])
        assert result.returncode == 0

    def test_nonexistent_policy_file_blocks_dangerous(self) -> None:
        result = _run_evaluator(
            ["git", "push", "--force"],
            policy_path="/nonexistent/policy.json",
        )
        assert result.returncode == 2

    def test_malformed_json_blocks_dangerous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            with open(path, "w") as f:
                f.write("{not valid json")
            result = _run_evaluator(["git", "push", "--force"], policy_path=path)
            assert result.returncode == 2

    def test_wrong_schema_blocks_dangerous(self) -> None:
        """Policy file with valid JSON but wrong schema (missing 'action')."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad_schema.json")
            with open(path, "w") as f:
                json.dump({"not_action": "allow"}, f)
            result = _run_evaluator(["git", "push", "--force"], policy_path=path)
            assert result.returncode == 2


class TestEvaluatorPolicyOverrides:
    """Tests for policy-based overrides (allow action, disabled rules)."""

    def test_allow_policy_permits_dangerous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_policy(tmp, {"action": "allow", "rules": {}})
            result = _run_evaluator(["git", "push", "--force"], policy_path=path)
            assert result.returncode == 0

    def test_disabled_rule_permits_specific_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_policy(
                tmp, {"action": "block", "rules": {"block_force_push": False}}
            )
            result = _run_evaluator(
                ["git", "push", "--force", "origin", "main"], policy_path=path
            )
            assert result.returncode == 0

    def test_disabled_git_rule_does_not_affect_network(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_policy(
                tmp, {"action": "block", "rules": {"block_force_push": False}}
            )
            result = _run_evaluator(["curl", "https://example.com"], policy_path=path)
            assert result.returncode == 2


# ── Negative / boundary tests ─────────────────────────────────────────────


class TestEvaluatorNegative:
    """Malformed inputs, edge cases, and boundary conditions."""

    def test_empty_tool_name(self) -> None:
        """Empty tool name should not crash the evaluator."""
        result = _run_evaluator([""])
        assert result.returncode == 0  # empty string → no rules match → allowed

    def test_whitespace_only_args(self) -> None:
        result = _run_evaluator(["git", "   "])
        assert result.returncode == 0  # safe git command with whitespace arg

    def test_tool_with_path_prefix(self) -> None:
        """Tool name with path prefix — evaluator uses the full first arg as tool."""
        result = _run_evaluator(["/usr/bin/git", "push", "--force"])
        # The evaluator joins args: "/usr/bin/git push --force"
        # shell_tokenizer will strip the path, so it should still detect force push
        assert result.returncode == 2

    def test_no_arguments_shows_usage(self) -> None:
        """Running evaluator with no args should show usage and exit 2."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(_WRAPPERS_DIR)
        if "SCC_POLICY_PATH" in env:
            del env["SCC_POLICY_PATH"]
        result = subprocess.run(
            ["python3", "-m", "scc_safety_eval"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 2
        assert "Usage" in result.stdout or "Usage" in result.stderr
