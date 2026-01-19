"""Architecture guardrail tests for application boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[1] / "src" / "scc_cli" / "application"

FORBIDDEN_EXTERNAL_MODULES = {
    "rich",
    "typer",
    "subprocess",
    "zipfile",
    "requests",
    "httpx",
}

FORBIDDEN_INTERNAL_PREFIXES = (
    "scc_cli.ui",
    "scc_cli.commands",
)

DIRECT_IO_METHODS = {
    "read_text",
    "write_text",
}


def _iter_application_files() -> list[Path]:
    return sorted(APPLICATION_ROOT.rglob("*.py"))


def _is_forbidden_module(module: str) -> bool:
    base = module.split(".")[0]
    if base in FORBIDDEN_EXTERNAL_MODULES:
        return True
    return module.startswith(FORBIDDEN_INTERNAL_PREFIXES)


def _attribute_chain(node: ast.Attribute) -> list[str]:
    parts: list[str] = []
    current: ast.AST = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return list(reversed(parts))


def test_application_forbidden_imports() -> None:
    """Application modules do not import forbidden modules."""
    violations: list[str] = []

    for path in _iter_application_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_forbidden_module(alias.name):
                        violations.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level > 0 and module.startswith(("ui", "commands")):
                    violations.append(f"{path}: from {'.' * node.level}{module} import ...")
                    continue
                if module and _is_forbidden_module(module):
                    violations.append(f"{path}: from {module} import ...")

    assert not violations, "\n".join(violations)


def test_application_no_direct_io_calls() -> None:
    """Application modules avoid direct filesystem IO and prints."""
    violations: list[str] = []

    for path in _iter_application_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    violations.append(f"{path}: print call")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                chain = _attribute_chain(node.func)
                if node.func.attr in DIRECT_IO_METHODS and "filesystem" not in chain:
                    violations.append(f"{path}: {'.'.join(chain)}")
                if node.func.attr == "print" and {"console", "err_console"} & set(chain):
                    violations.append(f"{path}: {'.'.join(chain)}")

    assert not violations, "\n".join(violations)
