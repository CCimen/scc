"""Function size guardrail test.

Enforces function size limits to maintain readability and modularity.
Functions exceeding 300 lines fail; functions between 200-300 lines produce warnings.

Metric: Physical lines per function using AST line numbers.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import NamedTuple

import pytest

# Thresholds
WARNING_THRESHOLD = 200
FAIL_THRESHOLD = 300

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


class FunctionInfo(NamedTuple):
    """Information about a function's size."""

    path: Path
    function_name: str
    line_count: int
    relative_path: str
    lineno: int


def should_exclude(file_path: Path) -> bool:
    """Check if a file should be excluded from size checks."""
    for part in file_path.parts:
        if part in EXCLUDED_DIRS:
            return True

    file_name = file_path.name
    for pattern in EXCLUDED_FILE_PATTERNS:
        if file_name.endswith(pattern):
            return True

    return False


def iter_functions(tree: ast.AST) -> list[tuple[str, int, int]]:
    """Yield function name, start line, and end line."""
    functions: list[tuple[str, int, int]] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not hasattr(node, "end_lineno") or node.end_lineno is None:
                continue
            functions.append((node.name, node.lineno, node.end_lineno))

    return functions


def get_function_sizes(directory: Path) -> list[FunctionInfo]:
    """Get all functions in directory with their line counts."""
    functions: list[FunctionInfo] = []

    if not directory.exists():
        return functions

    for root, _dirs, filenames in os.walk(directory):
        root_path = Path(root)

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            file_path = root_path / filename

            if should_exclude(file_path):
                continue

            try:
                source = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for name, start, end in iter_functions(tree):
                line_count = end - start + 1
                try:
                    relative = file_path.relative_to(SRC_DIR.parent)
                except ValueError:
                    relative = file_path

                functions.append(
                    FunctionInfo(
                        path=file_path,
                        function_name=name,
                        line_count=line_count,
                        relative_path=str(relative),
                        lineno=start,
                    )
                )

    return functions


def categorize_functions(
    functions: list[FunctionInfo],
) -> tuple[list[FunctionInfo], list[FunctionInfo], list[FunctionInfo]]:
    """Categorize functions by size."""
    ideal_or_acceptable: list[FunctionInfo] = []
    warning_zone: list[FunctionInfo] = []
    failing: list[FunctionInfo] = []

    for function_info in functions:
        if function_info.line_count > FAIL_THRESHOLD:
            failing.append(function_info)
        elif function_info.line_count >= WARNING_THRESHOLD:
            warning_zone.append(function_info)
        else:
            ideal_or_acceptable.append(function_info)

    return ideal_or_acceptable, warning_zone, failing


def format_warning(function_info: FunctionInfo) -> str:
    """Format a warning message for a function in the warning zone."""
    return (
        f"WARNING: {function_info.relative_path}:{function_info.lineno} "
        f"{function_info.function_name} ({function_info.line_count} lines)\n"
        f"  Approaching {FAIL_THRESHOLD}-line limit. Please consider splitting.\n"
        f"  Current threshold: warning at {WARNING_THRESHOLD}, fail at {FAIL_THRESHOLD}"
    )


def format_failure(function_info: FunctionInfo) -> str:
    """Format a failure message for a function exceeding the limit."""
    return (
        f"FAIL: {function_info.relative_path}:{function_info.lineno} "
        f"{function_info.function_name} ({function_info.line_count} lines)\n"
        f"  Exceeds {FAIL_THRESHOLD}-line limit. Must be split.\n"
        f"  Current threshold: warning at {WARNING_THRESHOLD}, fail at {FAIL_THRESHOLD}"
    )


class TestFunctionSizes:
    """Test class for function size guardrails."""

    @pytest.mark.xfail(
        reason=(
            "Known large functions exceed guardrail (launch flow and org/reset commands). "
            "Tracked in maintainability refactor."
        )
    )
    def test_function_size_limits(self) -> None:
        """Verify all functions in src/scc_cli/ are within size limits."""
        functions = get_function_sizes(SRC_DIR)

        if not functions:
            pytest.skip(f"No functions found in {SRC_DIR}")

        ideal_or_acceptable, warning_zone, failing = categorize_functions(functions)

        print("\n" + "=" * 70)
        print("FUNCTION SIZE GUARDRAIL REPORT")
        print("=" * 70)

        if warning_zone:
            print(f"\n{'=' * 70}")
            print(f"WARNING ZONE ({WARNING_THRESHOLD}-{FAIL_THRESHOLD} lines)")
            print("=" * 70)
            for function_info in sorted(warning_zone, key=lambda x: -x.line_count):
                print(f"\n{format_warning(function_info)}")

        if failing:
            print(f"\n{'=' * 70}")
            print(f"FAILURES (>{FAIL_THRESHOLD} lines)")
            print("=" * 70)
            for function_info in sorted(failing, key=lambda x: -x.line_count):
                print(f"\n{format_failure(function_info)}")

        print(f"\n{'=' * 70}")
        print("SUMMARY")
        print("=" * 70)
        print(f"  Total functions scanned: {len(functions)}")
        print(f"  Ideal/Acceptable (<{WARNING_THRESHOLD} lines): {len(ideal_or_acceptable)}")
        print(f"  Warning zone ({WARNING_THRESHOLD}-{FAIL_THRESHOLD} lines): {len(warning_zone)}")
        print(f"  Failing (>{FAIL_THRESHOLD} lines): {len(failing)}")

        print(f"\n{'=' * 70}")
        print("TOP 5 LARGEST FUNCTIONS")
        print("=" * 70)
        sorted_functions = sorted(functions, key=lambda x: -x.line_count)[:5]
        for i, function_info in enumerate(sorted_functions, 1):
            status = (
                "FAIL"
                if function_info.line_count > FAIL_THRESHOLD
                else "WARN"
                if function_info.line_count >= WARNING_THRESHOLD
                else "OK"
            )
            print(
                "  "
                f"{i}. [{status}] {function_info.relative_path}:"
                f"{function_info.lineno} {function_info.function_name}: "
                f"{function_info.line_count} lines"
            )

        print("=" * 70 + "\n")

        if failing:
            failure_messages = [format_failure(f) for f in failing]
            pytest.fail(
                f"\n{len(failing)} function(s) exceed {FAIL_THRESHOLD} lines:\n\n"
                + "\n\n".join(failure_messages)
            )
