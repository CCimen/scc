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
    pass


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
    """Verify human mode sends all output to stderr, nothing to stdout.

    NOTE: These tests are currently marked xfail because the doctor command
    outputs to stdout. This documents the contract violation that needs to be
    fixed when doctor is migrated to use the gated console infrastructure.
    """

    @pytest.mark.xfail(
        reason="doctor command outputs to stdout instead of stderr - needs migration to gated console",
        strict=True,  # Fail if this unexpectedly passes (contract was fixed)
    )
    def test_doctor_human_stdout_is_empty(self) -> None:
        """Human mode must not emit anything to stdout."""
        # TERM=dumb disables Rich animations but keeps text output
        result = run_scc("doctor", env_override={"TERM": "dumb"})

        assert result.stdout == "", (
            f"Human mode leaked to stdout:\nstdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    @pytest.mark.xfail(
        reason="doctor command outputs to stdout instead of stderr - needs migration to gated console",
        strict=True,
    )
    def test_doctor_human_stderr_has_content(self) -> None:
        """Human mode must emit diagnostic content to stderr."""
        result = run_scc("doctor", env_override={"TERM": "dumb"})

        # stderr should contain diagnostic output
        # Accept both Unicode and ASCII indicators
        has_content = bool(result.stderr.strip())
        has_diagnostic_indicator = any(
            indicator in result.stderr for indicator in ["OK", "FAIL", "WARN"]
        )

        assert has_content, "Human mode stderr is empty"
        assert has_diagnostic_indicator, (
            f"Human mode stderr missing expected indicators:\nstderr: {result.stderr!r}"
        )


class TestNoColorStreamContract:
    """Verify NO_COLOR environment variable is respected."""

    @pytest.mark.xfail(
        reason="doctor command outputs to stdout instead of stderr - needs migration to gated console",
        strict=True,
    )
    def test_no_color_still_outputs_to_stderr(self) -> None:
        """NO_COLOR should not break the stderr contract."""
        result = run_scc("doctor", env_override={"NO_COLOR": "1", "TERM": "dumb"})

        # stdout still empty
        assert result.stdout == "", f"NO_COLOR mode leaked to stdout: {result.stdout!r}"

        # stderr has content
        assert result.stderr.strip(), "NO_COLOR mode stderr is empty"


class TestPipedOutputContract:
    """Test behavior when stdout is piped (non-TTY)."""

    @pytest.mark.xfail(
        reason="doctor command outputs to stdout instead of stderr - needs migration to gated console",
        strict=True,
    )
    def test_human_mode_with_piped_stdout(self) -> None:
        """When stdout is piped, human output should still go to stderr.

        This simulates: scc doctor | cat
        The pipe makes stdout non-TTY, but stderr may still be TTY.
        """
        # We're already capturing stdout via subprocess, which makes it non-TTY
        result = run_scc("doctor", env_override={"TERM": "dumb"})

        # stdout should be empty (human mode never writes to stdout)
        assert result.stdout == "", f"Piped mode leaked to stdout: {result.stdout!r}"

        # stderr should have doctor output
        assert result.stderr.strip(), "Piped mode stderr is empty"


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
