"""JSON validation helpers for doctor module.

Provides enhanced JSON validation with code frames and helpful hints.
"""

from __future__ import annotations

import json
from pathlib import Path

from ...theme import Indicators
from ..types import JsonValidationResult


def validate_json_file(file_path: Path) -> JsonValidationResult:
    """
    Validate a JSON file and extract detailed error information.

    Args:
        file_path: Path to the JSON file to validate

    Returns:
        JsonValidationResult with validation status and error details
    """
    if not file_path.exists():
        return JsonValidationResult(valid=True, file_path=file_path)

    try:
        content = file_path.read_text(encoding="utf-8")
        json.loads(content)
        return JsonValidationResult(valid=True, file_path=file_path)
    except json.JSONDecodeError as e:
        code_frame = format_code_frame(content, e.lineno, e.colno, file_path)
        return JsonValidationResult(
            valid=False,
            error_message=e.msg,
            line=e.lineno,
            column=e.colno,
            file_path=file_path,
            code_frame=code_frame,
        )
    except OSError as e:
        return JsonValidationResult(
            valid=False,
            error_message=f"Cannot read file: {e}",
            file_path=file_path,
        )


def format_code_frame(
    content: str,
    error_line: int,
    error_col: int,
    file_path: Path,
    context_lines: int = 2,
) -> str:
    """
    Format a code frame showing the error location with context.

    Creates a visual representation like:
        10 │   "selected_profile": "dev-team",
        11 │   "preferences": {
      → 12 │     "auto_update": true
           │     ^
        13 │     "show_tips": false
        14 │   }

    Args:
        content: The file content
        error_line: Line number where error occurred (1-indexed)
        error_col: Column number where error occurred (1-indexed)
        file_path: Path to the file (for display)
        context_lines: Number of lines to show before/after error

    Returns:
        Formatted code frame string with Rich markup
    """
    lines = content.splitlines()
    total_lines = len(lines)

    # Calculate line range to display
    start_line = max(1, error_line - context_lines)
    end_line = min(total_lines, error_line + context_lines)

    # Calculate padding for line numbers
    max_line_num = end_line
    line_num_width = len(str(max_line_num))

    frame_lines = []

    # Add file path header
    frame_lines.append(f"[dim]File: {file_path}[/dim]")
    frame_lines.append("")

    for line_num in range(start_line, end_line + 1):
        line_content = lines[line_num - 1] if line_num <= total_lines else ""

        # Truncate long lines to prevent secret leakage (keep first 80 chars)
        if len(line_content) > 80:
            line_content = line_content[:77] + "..."

        if line_num == error_line:
            # Error line with arrow indicator
            frame_lines.append(
                f"[bold red]{Indicators.get('ARROW')} {line_num:>{line_num_width}} │[/bold red] "
                f"[white]{_escape_rich(line_content)}[/white]"
            )
            # Caret line pointing to error column
            caret_padding = " " * (line_num_width + 4 + max(0, error_col - 1))
            frame_lines.append(f"[bold red]{caret_padding}^[/bold red]")
        else:
            # Context line
            frame_lines.append(
                f"[dim]  {line_num:>{line_num_width}} │[/dim] "
                f"[dim]{_escape_rich(line_content)}[/dim]"
            )

    return "\n".join(frame_lines)


def _escape_rich(text: str) -> str:
    """Escape Rich markup characters in text."""
    return text.replace("[", "\\[").replace("]", "\\]")


def get_json_error_hints(error_message: str) -> list[str]:
    """
    Get helpful hints based on common JSON error messages.

    Args:
        error_message: The JSON decode error message

    Returns:
        List of helpful hints for fixing the error
    """
    hints = []
    error_lower = error_message.lower()

    if "expecting" in error_lower and "," in error_lower:
        hints.append("Missing comma between values")
    elif "expecting property name" in error_lower:
        hints.append("Trailing comma after last item (not allowed in JSON)")
        hints.append("Missing closing brace or bracket")
    elif "expecting value" in error_lower:
        hints.append("Missing value after colon or comma")
        hints.append("Empty array or object element")
    elif "expecting ':'" in error_lower:
        hints.append("Missing colon after property name")
    elif "unterminated string" in error_lower or "invalid \\escape" in error_lower:
        hints.append("Unclosed string quote or invalid escape sequence")
    elif "extra data" in error_lower:
        hints.append("Multiple root objects (JSON must have single root)")

    if not hints:
        hints.append("Check JSON syntax near the indicated line")

    return hints
