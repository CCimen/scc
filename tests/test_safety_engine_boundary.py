"""Boundary guardrail: core safety modules must not import plugin or provider code."""

from __future__ import annotations

import ast
from pathlib import Path

CORE_SAFETY_ROOT = Path(__file__).resolve().parents[1] / "src" / "scc_cli" / "core"

# Core safety modules that must remain provider-neutral
CORE_SAFETY_FILES = [
    CORE_SAFETY_ROOT / "safety_engine.py",
    CORE_SAFETY_ROOT / "shell_tokenizer.py",
    CORE_SAFETY_ROOT / "git_safety_rules.py",
    CORE_SAFETY_ROOT / "network_tool_rules.py",
]

# Forbidden import sources — plugin code and provider-specific adapters
FORBIDDEN_MODULE_PREFIXES = (
    "scc_safety_impl",
    "sandboxed_code_plugins",
    "scc_cli.adapters.claude",
    "scc_cli.adapters.codex",
)


def _collect_import_modules(path: Path) -> list[tuple[str, str]]:
    """Return (module, context_string) pairs for all imports in a file."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    imports: list[tuple[str, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, f"import {alias.name}"))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imports.append((module, f"from {module} import ..."))
    return imports


def test_core_safety_modules_have_no_forbidden_imports() -> None:
    """Core safety modules do not import from plugin or provider adapter code."""
    violations: list[str] = []

    for path in CORE_SAFETY_FILES:
        if not path.exists():
            continue
        for module, context in _collect_import_modules(path):
            if any(module.startswith(prefix) for prefix in FORBIDDEN_MODULE_PREFIXES):
                violations.append(f"{path.name}: {context}")

    assert not violations, "Core safety modules contain forbidden imports:\n" + "\n".join(
        violations
    )
