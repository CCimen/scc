"""Configuration health checks for doctor module.

Checks for user config validity and config directory accessibility.
"""

from __future__ import annotations

from ..types import CheckResult
from .json_helpers import get_json_error_hints, validate_json_file


def check_user_config_valid() -> CheckResult:
    """Check if user configuration file is valid JSON.

    Validates ~/.config/scc/config.json for JSON syntax errors
    and provides helpful error messages with code frames.

    Returns:
        CheckResult with user config validation status.
    """
    from ... import config

    config_file = config.CONFIG_FILE

    if not config_file.exists():
        return CheckResult(
            name="User Config",
            passed=True,
            message="No user config file (using defaults)",
            severity="info",
        )

    result = validate_json_file(config_file)

    if result.valid:
        return CheckResult(
            name="User Config",
            passed=True,
            message=f"User config is valid JSON: {config_file}",
        )

    # Build error message with hints
    error_msg = f"Invalid JSON in {config_file.name}"
    if result.line is not None:
        error_msg += f" at line {result.line}"
        if result.column is not None:
            error_msg += f", column {result.column}"

    # Get helpful hints
    hints = get_json_error_hints(result.error_message or "")
    fix_hint = f"Error: {result.error_message}\n"
    fix_hint += "Hints:\n"
    for hint in hints:
        fix_hint += f"  • {hint}\n"
    fix_hint += f"Edit with: $EDITOR {config_file}"

    return CheckResult(
        name="User Config",
        passed=False,
        message=error_msg,
        fix_hint=fix_hint,
        severity="error",
        code_frame=result.code_frame,
    )


def check_config_directory() -> CheckResult:
    """Check if configuration directory exists and is writable."""
    from ... import config

    config_dir = config.CONFIG_DIR

    if not config_dir.exists():
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            return CheckResult(
                name="Config Directory",
                passed=True,
                message=f"Created config directory: {config_dir}",
            )
        except PermissionError:
            return CheckResult(
                name="Config Directory",
                passed=False,
                message=f"Cannot create config directory: {config_dir}",
                fix_hint="Check permissions on parent directory",
                severity="error",
            )

    # Check if writable
    test_file = config_dir / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()
        return CheckResult(
            name="Config Directory",
            passed=True,
            message=f"Config directory is writable: {config_dir}",
        )
    except (PermissionError, OSError):
        return CheckResult(
            name="Config Directory",
            passed=False,
            message=f"Config directory is not writable: {config_dir}",
            fix_hint=f"Check permissions: chmod 755 {config_dir}",
            severity="error",
        )
