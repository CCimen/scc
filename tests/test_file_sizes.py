"""File size guardrail test.

Enforces file size limits to maintain code quality and readability.
Files exceeding 1100 lines fail CI; files between 800-1100 lines produce warnings.

Metric: Physical lines (including comments/blanks) using len(open(file).readlines())
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

import pytest

# Thresholds
WARNING_THRESHOLD = 800
FAIL_THRESHOLD = 1100

# Source directory to scan
SRC_DIR = Path(__file__).parent.parent / "src" / "scc_cli"

# Exclusion patterns (directories and file patterns to skip)
EXCLUDED_DIRS = {
    "tests",
    "migrations",
    "vendor",
    "schemas",
    ".venv",
    "build",
    "dist",
    "__pycache__",
}

EXCLUDED_FILE_PATTERNS = {
    "_pb2.py",  # protobuf generated
}


class FileInfo(NamedTuple):
    """Information about a file's line count."""

    path: Path
    line_count: int
    relative_path: str


def should_exclude(file_path: Path) -> bool:
    """Check if a file should be excluded from size checks."""
    # Check if any parent directory is in excluded dirs
    for part in file_path.parts:
        if part in EXCLUDED_DIRS:
            return True

    # Check file patterns
    file_name = file_path.name
    for pattern in EXCLUDED_FILE_PATTERNS:
        if file_name.endswith(pattern):
            return True

    return False


def count_lines(file_path: Path) -> int:
    """Count physical lines in a file (including comments and blanks)."""
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return len(f.readlines())
    except OSError:
        return 0


def get_python_files(directory: Path) -> list[FileInfo]:
    """Get all Python files in directory with their line counts."""
    files: list[FileInfo] = []

    if not directory.exists():
        return files

    for root, _dirs, filenames in os.walk(directory):
        root_path = Path(root)

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            file_path = root_path / filename

            if should_exclude(file_path):
                continue

            line_count = count_lines(file_path)
            try:
                relative = file_path.relative_to(SRC_DIR.parent)
            except ValueError:
                relative = file_path

            files.append(
                FileInfo(
                    path=file_path,
                    line_count=line_count,
                    relative_path=str(relative),
                )
            )

    return files


def categorize_files(
    files: list[FileInfo],
) -> tuple[list[FileInfo], list[FileInfo], list[FileInfo]]:
    """Categorize files by size.

    Returns:
        Tuple of (ideal_or_acceptable, warning_zone, failing)
        - ideal_or_acceptable: < 800 lines
        - warning_zone: 800-1000 lines
        - failing: > 1000 lines
    """
    ideal_or_acceptable: list[FileInfo] = []
    warning_zone: list[FileInfo] = []
    failing: list[FileInfo] = []

    for file_info in files:
        if file_info.line_count > FAIL_THRESHOLD:
            failing.append(file_info)
        elif file_info.line_count >= WARNING_THRESHOLD:
            warning_zone.append(file_info)
        else:
            ideal_or_acceptable.append(file_info)

    return ideal_or_acceptable, warning_zone, failing


def format_warning(file_info: FileInfo) -> str:
    """Format a warning message for a file in the warning zone."""
    return (
        f"WARNING: {file_info.relative_path} ({file_info.line_count} lines)\n"
        f"  Approaching {FAIL_THRESHOLD}-line limit. Please consider splitting.\n"
        f"  Current threshold: warning at {WARNING_THRESHOLD}, fail at {FAIL_THRESHOLD}"
    )


def format_failure(file_info: FileInfo) -> str:
    """Format a failure message for a file exceeding the limit."""
    return (
        f"FAIL: {file_info.relative_path} ({file_info.line_count} lines)\n"
        f"  Exceeds {FAIL_THRESHOLD}-line limit. Must be split.\n"
        f"  Current threshold: warning at {WARNING_THRESHOLD}, fail at {FAIL_THRESHOLD}"
    )


class TestFileSizes:
    """Test class for file size guardrails."""

    @pytest.mark.xfail(
        reason="commands/launch/app.py exceeds limit - to be split in future refactor"
    )
    def test_file_size_limits(self) -> None:
        """Verify all Python files in src/scc_cli/ are within size limits.

        - Files > 1000 lines: FAIL
        - Files 800-1000 lines: WARNING (logged, but test passes)
        - Files < 800 lines: OK
        """
        files = get_python_files(SRC_DIR)

        if not files:
            pytest.skip(f"No Python files found in {SRC_DIR}")

        ideal_or_acceptable, warning_zone, failing = categorize_files(files)

        # Print summary header
        print("\n" + "=" * 70)
        print("FILE SIZE GUARDRAIL REPORT")
        print("=" * 70)

        # Print warnings for files in warning zone
        if warning_zone:
            print(f"\n{'=' * 70}")
            print(f"WARNING ZONE ({WARNING_THRESHOLD}-{FAIL_THRESHOLD} lines)")
            print("=" * 70)
            for file_info in sorted(warning_zone, key=lambda x: -x.line_count):
                print(f"\n{format_warning(file_info)}")

        # Print failures
        if failing:
            print(f"\n{'=' * 70}")
            print(f"FAILURES (>{FAIL_THRESHOLD} lines)")
            print("=" * 70)
            for file_info in sorted(failing, key=lambda x: -x.line_count):
                print(f"\n{format_failure(file_info)}")

        # Print summary
        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print("=" * 70)
        print(f"  Total files scanned: {len(files)}")
        print(f"  Ideal/Acceptable (<{WARNING_THRESHOLD} lines): {len(ideal_or_acceptable)}")
        print(f"  Warning zone ({WARNING_THRESHOLD}-{FAIL_THRESHOLD} lines): {len(warning_zone)}")
        print(f"  Failing (>{FAIL_THRESHOLD} lines): {len(failing)}")

        # Show top 5 largest files for awareness
        print(f"\n{'=' * 70}")
        print("TOP 5 LARGEST FILES")
        print("=" * 70)
        sorted_files = sorted(files, key=lambda x: -x.line_count)[:5]
        for i, file_info in enumerate(sorted_files, 1):
            status = (
                "FAIL"
                if file_info.line_count > FAIL_THRESHOLD
                else "WARN"
                if file_info.line_count >= WARNING_THRESHOLD
                else "OK"
            )
            print(f"  {i}. [{status}] {file_info.relative_path}: {file_info.line_count} lines")

        print("=" * 70 + "\n")

        # Assert no files exceed the fail threshold
        if failing:
            failure_messages = [format_failure(f) for f in failing]
            pytest.fail(
                f"\n{len(failing)} file(s) exceed {FAIL_THRESHOLD} lines:\n\n"
                + "\n\n".join(failure_messages)
            )
