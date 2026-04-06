"""Guardrail: prevent Claude-specific runtime constants in core/constants.py.

After the S04 legacy Claude path isolation, all Claude-specific runtime
constants (image names, volume names, credential paths, etc.) live in the
adapter modules that consume them. core/constants.py holds only product-level
constants (CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX).

This test prevents re-introduction of provider-specific values into core.
"""

from __future__ import annotations

import tokenize
from io import BytesIO
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "scc_cli"

# Claude-specific constant names that must NOT appear in core/constants.py.
# These were localized to consumer modules in S04/T01-T02.
_CLAUDE_CONSTANTS = frozenset(
    {
        "AGENT_NAME",
        "SANDBOX_IMAGE",
        "AGENT_CONFIG_DIR",
        "SANDBOX_DATA_VOLUME",
        "SANDBOX_DATA_MOUNT",
        "CREDENTIAL_PATHS",
        "OAUTH_CREDENTIAL_KEY",
        "DEFAULT_MARKETPLACE_REPO",
    }
)


def _find_name_tokens(source: str, names: frozenset[str]) -> list[tuple[int, str]]:
    """Return (lineno, line_text) for NAME tokens matching any name in the set.

    Uses Python's tokenize module (per KNOWLEDGE.md) to avoid false positives
    from comments, docstrings, or string literals.
    """
    hits: list[tuple[int, str]] = []
    lines = source.splitlines()

    try:
        tokens = list(tokenize.tokenize(BytesIO(source.encode()).readline))
    except tokenize.TokenError:
        return hits

    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string in names:
            lineno = tok.start[0]
            hits.append((lineno, lines[lineno - 1].strip()))

    return hits


class TestNoClaudeSpecificConstantsInCore:
    """core/constants.py must not define any Claude-specific runtime constants."""

    def test_no_claude_constants_defined_in_core(self) -> None:
        constants_file = SRC / "core" / "constants.py"
        source = constants_file.read_text(encoding="utf-8")

        hits = _find_name_tokens(source, _CLAUDE_CONSTANTS)

        if hits:
            details = "\n".join(f"  line {ln}: {text}" for ln, text in hits)
            raise AssertionError(
                f"Claude-specific constants found in core/constants.py:\n{details}\n\n"
                "These belong in the adapter/consumer modules, not in core. "
                "See S04 slice plan for rationale."
            )

    def test_no_claude_constant_imports_from_core(self) -> None:
        """No module should import Claude-specific constants from core.constants."""
        violations: list[str] = []

        for py_file in sorted(SRC.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
            except OSError:
                continue

            for lineno, line in enumerate(source.splitlines(), start=1):
                # Only check import lines referencing core.constants
                if "core.constants" not in line or "import" not in line:
                    continue

                # Check if any Claude-specific constant name appears on this line
                for name in _CLAUDE_CONSTANTS:
                    if name in line:
                        rel = py_file.relative_to(SRC)
                        violations.append(f"  {rel}:{lineno}: {line.strip()}")
                        break  # one violation per line is enough

        if violations:
            raise AssertionError(
                "Found imports of Claude-specific constants from core.constants:\n"
                + "\n".join(violations)
                + "\n\nImport from the consumer module instead."
            )
