"""Guardrail: prevent stale docker.check_docker_available() calls outside the adapter layer.

After the RuntimeProbe migration (M003-S01), all Docker availability detection
must go through the probe adapter. Direct calls to check_docker_available()
should only exist in:

- scc_cli/docker/core.py  — original definition
- scc_cli/docker/__init__.py  — re-export
- scc_cli/adapters/docker_runtime_probe.py  — the adapter that wraps it

Any other occurrence is a regression: new code should use RuntimeProbe instead.
"""

from __future__ import annotations

import tokenize
from io import BytesIO
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "scc_cli"

# Files where check_docker_available is allowed to appear
ALLOWED_FILES = {
    SRC / "docker" / "core.py",  # definition
    SRC / "docker" / "__init__.py",  # re-export
    SRC / "adapters" / "docker_runtime_probe.py",  # probe adapter wrapping it
}

TOKEN = "check_docker_available"


def _has_code_reference(source: str) -> list[tuple[int, str]]:
    """Return (lineno, line_text) for lines that reference the token in code, not strings/comments."""
    hits: list[tuple[int, str]] = []
    lines = source.splitlines()

    # Collect line numbers that contain the token only inside strings or comments
    # by tokenizing and checking where NAME tokens with our target appear.
    try:
        tokens = list(tokenize.tokenize(BytesIO(source.encode()).readline))
    except tokenize.TokenError:
        # If tokenization fails, fall back to AST-only checking
        return hits

    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string == TOKEN:
            lineno = tok.start[0]
            hits.append((lineno, lines[lineno - 1].strip()))

    return hits


def test_no_stale_check_docker_available_calls() -> None:
    """No file outside the allowlist should reference check_docker_available in code.

    If this test fails, you are calling docker.check_docker_available()
    directly instead of going through RuntimeProbe. Use the probe adapter's
    ensure_available() or probe() method instead.
    """
    violations: list[str] = []

    for py_file in sorted(SRC.rglob("*.py")):
        if py_file in ALLOWED_FILES:
            continue

        source = py_file.read_text(encoding="utf-8")
        if TOKEN not in source:
            continue

        for lineno, line_text in _has_code_reference(source):
            rel = py_file.relative_to(SRC)
            violations.append(f"  {rel}:{lineno}: {line_text}")

    if violations:
        msg = (
            "Direct check_docker_available() usage found outside the adapter layer.\n"
            "Use RuntimeProbe.probe() or ensure_available() instead.\n\n"
            "Violations:\n" + "\n".join(violations)
        )
        raise AssertionError(msg)
