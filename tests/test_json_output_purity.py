"""Tests for JSON output purity - ensuring stdout is clean in JSON mode."""

import json
import sys
from unittest.mock import patch

import pytest

from scc_cli.output_mode import (
    console,
    err_console,
    is_json_mode,
    json_output_mode,
    print_human,
    print_json,
)


class TestJsonOutputPurity:
    """Verify JSON output is not polluted by human-readable messages."""

    def test_print_human_suppressed_in_json_mode(self) -> None:
        """print_human should output nothing to stdout in JSON mode."""
        with json_output_mode():
            with patch.object(console, "print") as mock_stdout:
                print_human("This should not appear")
                mock_stdout.assert_not_called()

    def test_print_human_stderr_suppressed_in_json_mode(self) -> None:
        """print_human with stderr should output nothing in JSON mode."""
        with json_output_mode():
            with (
                patch.object(console, "print") as mock_stdout,
                patch.object(err_console, "print") as mock_stderr,
            ):
                print_human("This should not appear", file=sys.stderr)
                mock_stdout.assert_not_called()
                mock_stderr.assert_not_called()

    def test_json_mode_active_inside_context(self) -> None:
        """is_json_mode should return True inside json_output_mode context."""
        assert not is_json_mode()
        with json_output_mode():
            assert is_json_mode()
        assert not is_json_mode()

    def test_nested_json_mode_preserved(self) -> None:
        """Nested json_output_mode should maintain JSON mode state."""
        assert not is_json_mode()
        with json_output_mode():
            assert is_json_mode()
            with json_output_mode():
                assert is_json_mode()
            assert is_json_mode()
        assert not is_json_mode()


class TestJsonOutputFormat:
    """Verify JSON output format is correct."""

    def test_print_json_outputs_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        """print_json should output valid, parseable JSON."""
        envelope = {"kind": "test", "data": {"foo": "bar"}}
        print_json(envelope)

        captured = capsys.readouterr()
        parsed = json.loads(captured.out.strip())
        assert parsed == envelope

    def test_print_json_compact_by_default(self, capsys: pytest.CaptureFixture[str]) -> None:
        """print_json should output compact JSON without indentation by default."""
        envelope = {"kind": "test", "data": {"foo": "bar"}}
        print_json(envelope)

        captured = capsys.readouterr()
        # Compact JSON has no newlines except the trailing one
        output = captured.out.strip()
        assert "\n" not in output
        # Compact JSON has no spaces after colons or commas
        assert ": " not in output  # No space after colon
        assert ", " not in output  # No space after comma


class TestStdoutStderrSeparation:
    """Verify proper separation of stdout and stderr output."""

    def test_print_human_default_goes_to_stdout(self) -> None:
        """print_human without file parameter should use stdout console."""
        with patch.object(console, "print") as mock_stdout:
            print_human("Regular message")
            mock_stdout.assert_called_once_with("Regular message")

    def test_print_human_with_stderr_uses_err_console(self) -> None:
        """print_human with file=sys.stderr should use stderr console."""
        with (
            patch.object(console, "print") as mock_stdout,
            patch.object(err_console, "print") as mock_stderr,
        ):
            print_human("Error message", file=sys.stderr)
            mock_stdout.assert_not_called()
            mock_stderr.assert_called_once_with("Error message")

    def test_err_console_configured_for_stderr(self) -> None:
        """err_console should be configured to write to stderr."""
        assert err_console.stderr is True

    def test_console_configured_for_stdout(self) -> None:
        """console should be configured for stdout."""
        assert console.stderr is False
