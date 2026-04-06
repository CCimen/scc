"""CLI entry point for the standalone safety evaluator.

Usage: python3 -m scc_safety_eval <tool> [args...]

Exit codes:
  0 — command allowed
  2 — command blocked (reason printed to stderr)
  2 — unexpected error (fail-closed)
"""

from __future__ import annotations

import sys


def main() -> int:
    """Evaluate a command and exit with the appropriate code."""
    try:
        from .engine import DefaultSafetyEngine
        from .policy import load_policy

        if len(sys.argv) < 2:
            print("Usage: python3 -m scc_safety_eval <tool> [args...]", file=sys.stderr)
            return 2

        policy = load_policy()
        command = " ".join(sys.argv[1:])
        engine = DefaultSafetyEngine()
        verdict = engine.evaluate(command, policy)

        if verdict.allowed:
            return 0

        print(verdict.reason, file=sys.stderr)
        return 2

    except Exception as exc:  # noqa: BLE001 — fail-closed
        print(f"scc_safety_eval: unexpected error: {exc}", file=sys.stderr)
        return 2


sys.exit(main())
