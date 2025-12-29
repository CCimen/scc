"""Tests for output_mode stderr routing."""

import sys
from unittest.mock import patch

from scc_cli.output_mode import (
    console,
    err_console,
    json_output_mode,
    print_human,
)


class TestPrintHumanStderrRouting:
    """Tests for print_human file parameter handling."""

    def test_print_human_uses_stdout_console_by_default(self) -> None:
        """Default print_human should use stdout console."""
        with patch.object(console, "print") as mock_print:
            print_human("test message")
            mock_print.assert_called_once_with("test message")

    def test_print_human_uses_stderr_console_when_file_is_stderr(self) -> None:
        """print_human with file=sys.stderr should use stderr console."""
        with patch.object(err_console, "print") as mock_stderr_print:
            print_human("error message", file=sys.stderr)
            mock_stderr_print.assert_called_once_with("error message")

    def test_print_human_does_not_use_stdout_when_file_is_stderr(self) -> None:
        """Ensure stdout console is not used when stderr is specified."""
        with (
            patch.object(console, "print") as mock_stdout,
            patch.object(err_console, "print") as mock_stderr,
        ):
            print_human("error message", file=sys.stderr)
            mock_stdout.assert_not_called()
            mock_stderr.assert_called_once()

    def test_print_human_suppressed_in_json_mode(self) -> None:
        """print_human should be no-op in JSON mode regardless of file."""
        with json_output_mode():
            with (
                patch.object(console, "print") as mock_stdout,
                patch.object(err_console, "print") as mock_stderr,
            ):
                print_human("should not print")
                print_human("should not print either", file=sys.stderr)
                mock_stdout.assert_not_called()
                mock_stderr.assert_not_called()

    def test_print_human_with_kwargs_passed_to_console(self) -> None:
        """Additional kwargs should be passed to console.print."""
        with patch.object(console, "print") as mock_print:
            print_human("styled message", style="bold")
            mock_print.assert_called_once_with("styled message", style="bold")

    def test_print_human_with_kwargs_passed_to_err_console(self) -> None:
        """Additional kwargs should be passed to err_console.print."""
        with patch.object(err_console, "print") as mock_print:
            print_human("styled error", file=sys.stderr, style="red")
            mock_print.assert_called_once_with("styled error", style="red")


class TestErrConsoleConfiguration:
    """Tests for err_console setup."""

    def test_err_console_is_configured_for_stderr(self) -> None:
        """err_console should be configured to write to stderr."""
        assert err_console.stderr is True

    def test_console_is_configured_for_stdout(self) -> None:
        """console should be configured for stdout (not stderr)."""
        assert console.stderr is False
