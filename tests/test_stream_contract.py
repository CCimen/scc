"""Subprocess-level stream contract validation (A.9).

These tests validate the fundamental stdout/stderr contract at the system boundary
by running the actual CLI binary and capturing real streams.

Contract:
- JSON mode (--json): stdout = valid JSON, stderr = empty (or debug only)
- Human mode: stdout = empty, stderr = all Rich UI output

This catches bugs that unit tests miss because they mock consoles.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


def run_scc(
    *args: str, env_override: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the SCC CLI and capture output.

    Args:
        *args: CLI arguments (e.g., "doctor", "--json")
        env_override: Environment variables to override (merged with os.environ)

    Returns:
        CompletedProcess with stdout, stderr, and returncode
    """
    env = {**os.environ}
    if env_override:
        env.update(env_override)

    return subprocess.run(
        ["scc", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,  # Prevent hanging tests
    )


class TestJsonModeStreamContract:
    """Verify JSON mode outputs valid JSON to stdout with clean stderr."""

    def test_doctor_json_stdout_is_valid_json(self) -> None:
        """JSON mode must produce parseable JSON to stdout."""
        result = run_scc("doctor", "--json")

        # stdout must be valid JSON
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"JSON mode stdout is not valid JSON: {e}\nstdout: {result.stdout!r}")

        # Should have expected JSON envelope structure
        assert "kind" in data, f"Missing 'kind' in JSON: {data}"

    def test_doctor_json_stderr_is_clean(self) -> None:
        """JSON mode stderr should be empty or only contain debug output."""
        result = run_scc("doctor", "--json")

        # stderr should be empty or only DEBUG lines
        # (Some environments may emit debug output, which is acceptable)
        stderr_lines = result.stderr.strip().splitlines() if result.stderr else []

        for line in stderr_lines:
            # Allow empty lines and DEBUG-prefixed lines
            if line.strip() and not line.strip().startswith("DEBUG"):
                pytest.fail(
                    f"JSON mode stderr contains non-debug output:\n"
                    f"Line: {line!r}\n"
                    f"Full stderr: {result.stderr!r}"
                )

    def test_doctor_json_parseable_by_jq(self) -> None:
        """Verify stdout can be piped through jq (simulated via JSON parse)."""
        result = run_scc("doctor", "--json")

        # This simulates: scc doctor --json 2>/dev/null | jq .
        # The key test is that stdout parses as valid JSON
        parsed = json.loads(result.stdout)

        # Verify basic structure expected by scripts
        assert isinstance(parsed, dict), "JSON output must be an object"


class TestHumanModeStreamContract:
    """Verify human mode stream contract for doctor command.

    Doctor uses a RELAXED contract (different from other commands):
    - Normal report output → stdout (allows `scc doctor > report.txt`)
    - Errors about doctor failing to run → stderr
    - --json mode → pure JSON to stdout only

    This is intentional - doctor is a "reporting" command where users may
    want to capture the output to a file.
    """

    def test_doctor_human_stdout_has_report(self) -> None:
        """Doctor human mode outputs report to stdout (relaxed contract)."""
        # TERM=dumb disables Rich animations but keeps text output
        result = run_scc("doctor", env_override={"TERM": "dumb"})

        # stdout should contain the health check report
        has_content = bool(result.stdout.strip())
        # Accept various indicators in the health check output
        has_diagnostic_indicator = any(
            indicator in result.stdout
            for indicator in ["Health Check", "✓", "✗", "Git", "Docker", "OK", "FAIL"]
        )

        assert has_content, (
            f"Doctor stdout should contain report:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert has_diagnostic_indicator, (
            f"Doctor stdout missing expected health check content:\nstdout: {result.stdout!r}"
        )

    def test_doctor_human_stderr_for_errors_only(self) -> None:
        """Doctor human mode should only use stderr for actual errors."""
        result = run_scc("doctor", env_override={"TERM": "dumb"})

        # stderr should be empty or only contain debug output / error messages
        # (not the main health check report)
        if result.stderr.strip():
            # If there's stderr content, it should be error/debug related
            # not the main report (which should be in stdout)
            has_report_in_stderr = any(
                indicator in result.stderr for indicator in ["Health Check", "Git", "Docker"]
            )
            assert not has_report_in_stderr, (
                f"Doctor report should go to stdout, not stderr:\nstderr: {result.stderr!r}"
            )


class TestNoColorStreamContract:
    """Verify NO_COLOR environment variable is respected."""

    def test_no_color_doctor_still_outputs_to_stdout(self) -> None:
        """NO_COLOR should not change doctor's relaxed contract (stdout for report)."""
        result = run_scc("doctor", env_override={"NO_COLOR": "1", "TERM": "dumb"})

        # Doctor uses relaxed contract: report goes to stdout
        assert result.stdout.strip(), (
            f"NO_COLOR mode doctor stdout should have report: {result.stdout!r}"
        )


class TestPipedOutputContract:
    """Test behavior when stdout is piped (non-TTY)."""

    def test_doctor_piped_stdout_has_report(self) -> None:
        """When stdout is piped, doctor report should still go to stdout.

        This simulates: scc doctor | cat or scc doctor > report.txt
        The pipe makes stdout non-TTY, but doctor's relaxed contract
        still outputs the report to stdout for capture.
        """
        # We're already capturing stdout via subprocess, which makes it non-TTY
        result = run_scc("doctor", env_override={"TERM": "dumb"})

        # stdout should have doctor report (relaxed contract allows capture)
        assert result.stdout.strip(), (
            f"Piped mode doctor stdout should have report:\nstdout: {result.stdout!r}"
        )


class TestVersionCommandContract:
    """Test --version output follows expected patterns."""

    def test_version_human_stdout_contains_version(self) -> None:
        """Version command may output to stdout (common CLI convention)."""
        result = run_scc("--version")

        # Version typically goes to stdout per CLI conventions
        # This is an exception to our stderr rule for human output
        combined_output = result.stdout + result.stderr
        assert "scc" in combined_output.lower() or "1." in combined_output, (
            f"Version output missing expected content:\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )


class TestWorktreeStdoutPurity:
    """Verify worktree commands keep stdout pure for shell integration.

    The wt() shell wrapper relies on stdout containing ONLY the worktree path.
    Any error messages leaking to stdout break the wrapper.

    Shell wrapper pattern:
        wt() {
            local p
            p="$(scc worktree switch "$@")" || return $?
            cd "$p" || return 1
        }
    """

    def test_switch_in_non_git_dir_stdout_empty(self, tmp_path: Path) -> None:
        """worktree switch in non-git dir: stdout must be empty.

        This is the most common failure mode that breaks the wt() wrapper.
        Error output must go to stderr only.
        """
        # CLI syntax: scc worktree [group-workspace] switch <target> -w <workspace>
        result = run_scc("worktree", ".", "switch", "main", "-w", str(tmp_path))

        assert result.stdout == "", (
            f"stdout leak breaks wt() wrapper:\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )

    def test_switch_in_non_git_dir_exit_code(self, tmp_path: Path) -> None:
        """worktree switch in non-git dir: exit code must be 4 (ToolError)."""
        # CLI syntax: scc worktree [group-workspace] switch <target> -w <workspace>
        result = run_scc("worktree", ".", "switch", "main", "-w", str(tmp_path))

        # ToolError exit code is 4
        assert result.returncode == 4, (
            f"Expected exit code 4 (ToolError), got {result.returncode}\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )

    def test_switch_in_non_git_dir_stderr_has_error(self, tmp_path: Path) -> None:
        """worktree switch in non-git dir: stderr must contain error message."""
        # CLI syntax: scc worktree [group-workspace] switch <target> -w <workspace>
        result = run_scc("worktree", ".", "switch", "main", "-w", str(tmp_path))

        assert "Not a git repository" in result.stderr, (
            f"stderr missing error message:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_switch_invalid_target_stdout_empty(self, tmp_path: Path) -> None:
        """worktree switch with invalid target: stdout must be empty.

        Even when the repo exists but target is invalid, errors go to stderr.
        """
        import subprocess

        # Create a git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            env={
                **os.environ,
                "GIT_AUTHOR_NAME": "test",
                "GIT_AUTHOR_EMAIL": "test@test.com",
                "GIT_COMMITTER_NAME": "test",
                "GIT_COMMITTER_EMAIL": "test@test.com",
            },
        )

        # Switch to nonexistent target
        result = run_scc("worktree", "switch", "nonexistent-worktree-xyz", "-w", str(tmp_path))

        assert result.stdout == "", (
            f"stdout leak breaks wt() wrapper:\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )


class TestNonWorktreeStdoutPurity:
    """Verify non-worktree commands also route errors to stderr.

    This validates the handle_errors fix applies broadly, not just to worktree.
    """

    def test_workspace_not_found_stdout_empty(self) -> None:
        """Commands with invalid CLI argument: stdout must be empty.

        Verifies CLI parsing errors route to stderr, not stdout.
        """
        # This triggers a CLI parsing error (nonexistent path treated as arg to list)
        result = run_scc("worktree", "list", "/nonexistent/path/that/does/not/exist")

        # CLI parsing error: exit code 2, error to stderr, stdout empty
        assert result.stdout == "", (
            f"CLI error leaked to stdout:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert result.returncode == 2, (
            f"Expected CLI error (exit 2):\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert result.stderr != "", "Expected error message in stderr"

    def test_workspace_not_found_stderr_has_error(self) -> None:
        """Commands with group-level workspace fallback: verifies new behavior.

        After UX changes, invalid group-level workspace falls back to current directory.
        """
        # CLI syntax: scc worktree [WORKSPACE] list
        # This uses the optional group workspace, which falls back to current directory
        result = run_scc("worktree", "/nonexistent/path/that/does/not/exist", "list")

        # New behavior: falls back to current directory, so command succeeds
        assert result.returncode == 0, (
            f"Expected success with fallback behavior:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
