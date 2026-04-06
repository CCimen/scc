"""Shared Codex launch helpers for SCC container sessions."""

from __future__ import annotations

CODEX_DANGER_FLAG = "--dangerously-bypass-approvals-and-sandbox"


def build_codex_container_argv() -> tuple[str, ...]:
    """Return the canonical Codex argv for containerized SCC sessions."""
    return ("codex", CODEX_DANGER_FLAG)
