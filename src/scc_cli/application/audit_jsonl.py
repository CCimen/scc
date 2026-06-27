"""Shared JSONL primitives for bounded audit readers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

DEFAULT_SCAN_LINE_FLOOR = 50
BINARY_CHUNK_SIZE = 8192


def scan_line_limit(limit: int) -> int:
    """Return the bounded scan window for a requested event limit."""
    if limit <= 0:
        return 0
    return max(limit * 4, DEFAULT_SCAN_LINE_FLOOR)


def tail_lines(path: Path, *, max_lines: int) -> list[str]:
    """Return the last ``max_lines`` UTF-8 lines from ``path``."""
    if max_lines <= 0:
        return []

    with path.open("rb") as handle:
        handle.seek(0, 2)
        file_size = handle.tell()
        position = file_size
        if file_size == 0:
            return []

        lines: list[bytes] = []
        remainder = b""
        skip_trailing_newline = True

        while position > 0 and len(lines) < max_lines:
            read_size = min(BINARY_CHUNK_SIZE, position)
            position -= read_size
            handle.seek(position)
            chunk = handle.read(read_size)
            parts = (chunk + remainder).split(b"\n")
            remainder = parts[0]

            for part in reversed(parts[1:]):
                if skip_trailing_newline and part == b"":
                    skip_trailing_newline = False
                    continue
                skip_trailing_newline = False
                lines.append(part)
                if len(lines) >= max_lines:
                    break

        if len(lines) < max_lines and remainder:
            lines.append(remainder)

    return [line.decode("utf-8", errors="replace") for line in reversed(lines)]


def redact_value(value: Any, *, redact_paths: bool) -> Any:
    """Redact local paths in nested JSON-compatible values."""
    if isinstance(value, str):
        return redact_string(value, redact_paths=redact_paths)
    if isinstance(value, dict):
        return {key: redact_value(item, redact_paths=redact_paths) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_value(item, redact_paths=redact_paths) for item in value]
    return value


def redact_string(value: str, *, redact_paths: bool) -> str:
    """Replace the current home directory with ``~`` when redaction is enabled."""
    if not redact_paths:
        return value
    home = str(Path.home())
    return value.replace(home, "~") if home in value else value
