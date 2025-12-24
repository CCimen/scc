"""Define data types for the doctor health check module.

Provide dataclasses for representing check results, validation results,
and overall doctor diagnostic results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    passed: bool
    message: str
    version: str | None = None
    fix_hint: str | None = None
    fix_url: str | None = None
    severity: str = "error"  # "error", "warning", "info"
    code_frame: str | None = None  # Optional code frame for syntax errors
    fix_commands: list[str] | None = None  # Copy-pasteable fix commands


@dataclass
class JsonValidationResult:
    """Result of JSON file validation with error details."""

    valid: bool
    error_message: str | None = None
    line: int | None = None
    column: int | None = None
    file_path: Path | None = None
    code_frame: str | None = None


@dataclass
class DoctorResult:
    """Complete health check results."""

    git_ok: bool = False
    git_version: str | None = None
    docker_ok: bool = False
    docker_version: str | None = None
    sandbox_ok: bool = False
    wsl2_detected: bool = False
    windows_path_warning: bool = False
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        """Check if all critical prerequisites pass."""
        return self.git_ok and self.docker_ok and self.sandbox_ok

    @property
    def error_count(self) -> int:
        """Return the count of failed critical checks."""
        return sum(1 for c in self.checks if not c.passed and c.severity == "error")

    @property
    def warning_count(self) -> int:
        """Return the count of warnings."""
        return sum(1 for c in self.checks if not c.passed and c.severity == "warning")
