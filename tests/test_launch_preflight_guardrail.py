"""Structural guardrails for launch preflight consistency (M008-S01).

Anti-drift tests that prevent inline provider resolution from creeping back
into launch entry-point files that were migrated to the shared preflight module.

Also verifies single-source-of-truth for provider metadata (image refs,
display names) — catching the exact consistency bug M008 cleaned up.

Pattern: same AST/tokenize structural scanning approach used by
test_no_claude_constants_in_core.py and test_import_boundaries.py.
"""

from __future__ import annotations

import ast
import tokenize
from io import BytesIO
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "scc_cli"


# ─────────────────────────────────────────────────────────────────────────────
# Part 1: Provider resolution anti-drift
#
# flow.py and flow_interactive.py were migrated in T03 to use
# preflight.resolve_launch_provider() instead of inline choose_start_provider /
# resolve_active_provider / _resolve_provider calls.
#
# ensure_provider_image / ensure_provider_auth remain inline per T03 decision:
# ensure_launch_ready lacks StartSessionPlan context for post-plan auth bootstrap.
# ─────────────────────────────────────────────────────────────────────────────

# Functions that must NOT appear as direct calls in migrated files.
# These must go through preflight.resolve_launch_provider().
_RESOLUTION_FUNCTIONS = frozenset({
    "choose_start_provider",
    "resolve_active_provider",
})

# Files that have been migrated to use preflight for provider resolution.
# When orchestrator_handlers.py and worktree_commands.py are migrated,
# add them here.
_MIGRATED_FILES = (
    SRC / "commands" / "launch" / "flow.py",
    SRC / "commands" / "launch" / "flow_interactive.py",
)

# preflight.py itself is the one legitimate consumer of choose_start_provider.
_PREFLIGHT_MODULE = SRC / "commands" / "launch" / "preflight.py"


def _extract_name_tokens(source_bytes: bytes) -> list[str]:
    """Extract all NAME tokens from Python source, ignoring comments/strings."""
    tokens = tokenize.tokenize(BytesIO(source_bytes).readline)
    return [tok.string for tok in tokens if tok.type == tokenize.NAME]


class TestProviderResolutionAntiDrift:
    """Migrated launch files must not call resolution functions directly."""

    def test_migrated_files_do_not_call_resolution_functions(self) -> None:
        """flow.py and flow_interactive.py should not contain direct calls
        to choose_start_provider or resolve_active_provider."""
        violations: list[str] = []
        for path in _MIGRATED_FILES:
            assert path.exists(), f"Missing migrated file: {path}"
            source = path.read_bytes()
            names = _extract_name_tokens(source)
            for name in names:
                if name in _RESOLUTION_FUNCTIONS:
                    violations.append(f"{path.name}: contains '{name}'")
        assert not violations, (
            "Migrated files contain direct resolution calls. "
            "Use preflight.resolve_launch_provider() instead:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_migrated_files_import_from_preflight(self) -> None:
        """Each migrated file must import from commands.launch.preflight."""
        for path in _MIGRATED_FILES:
            assert path.exists(), f"Missing migrated file: {path}"
            source = path.read_text()
            assert "preflight" in source, (
                f"{path.name} does not import from preflight module. "
                "Launch entry points should use preflight.resolve_launch_provider()."
            )

    def test_preflight_is_sole_wrapper_of_choose_start_provider(self) -> None:
        """Only preflight.py may import and call choose_start_provider in
        the commands/launch directory (excluding tests).

        Other callers in commands/launch/ should use resolve_launch_provider().
        orchestrator_handlers.py is excluded — it has its own migration timeline.
        """
        launch_dir = SRC / "commands" / "launch"
        violations: list[str] = []
        for py_file in sorted(launch_dir.glob("*.py")):
            if py_file.name.startswith("_") and py_file.name != "__init__.py":
                continue
            if py_file == _PREFLIGHT_MODULE:
                continue  # preflight.py is the legitimate wrapper
            if py_file.name == "provider_choice.py":
                continue  # definition site
            source = py_file.read_bytes()
            names = _extract_name_tokens(source)
            if "choose_start_provider" in names:
                violations.append(py_file.name)
        assert not violations, (
            "Only preflight.py should call choose_start_provider in commands/launch/. "
            f"Violations: {violations}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Part 2: Single source of truth for provider metadata
#
# Image refs must come from core/image_contracts.py constants.
# Display names must come from core/provider_registry.py or
# core/provider_resolution.py.
# Adapter modules may duplicate display names (they implement the contract).
# ─────────────────────────────────────────────────────────────────────────────

# Hardcoded image ref strings that should only appear in canonical locations.
_IMAGE_REF_LITERALS = frozenset({
    "scc-agent-claude:latest",
    "scc-agent-codex:latest",
    "scc-agent-claude",
    "scc-agent-codex",
})

# Canonical locations where image ref constants may be defined.
_IMAGE_REF_CANONICAL = frozenset({
    "image_contracts.py",  # defines the constants
    "provider_registry.py",  # imports and uses them in the registry
})

# Canonical locations where display names may be hardcoded.
_DISPLAY_NAME_CANONICAL = frozenset({
    "provider_resolution.py",  # _DISPLAY_NAMES dict
    "provider_registry.py",  # ProviderRuntimeSpec entries
})

# Adapter modules legitimately duplicate display names (they return them
# from capability_profile and display_name properties).
_DISPLAY_NAME_ADAPTER_ALLOWLIST = frozenset({
    "claude_agent_provider.py",
    "codex_agent_provider.py",
    "claude_agent_runner.py",
    "codex_agent_runner.py",
})

# Modules that have known, documented provider-specific strings that
# predate the registry centralization. These are tracked for future cleanup.
_DISPLAY_NAME_LEGACY_ALLOWLIST = frozenset({
    "render.py",  # has display_name defaults in function signatures
    "sandbox.py",  # has display_name defaults in function signatures
})


def _collect_string_literals(source: str) -> list[str]:
    """Extract all string literals from Python source using AST."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.append(node.value)
    return literals


class TestProviderMetadataSingleSource:
    """Provider image refs and display names must come from canonical sources."""

    def test_image_refs_not_hardcoded_outside_canonical(self) -> None:
        """Image ref strings like 'scc-agent-claude:latest' must only appear
        in image_contracts.py and provider_registry.py."""
        violations: list[str] = []
        for py_file in sorted(SRC.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            if py_file.name in _IMAGE_REF_CANONICAL:
                continue
            source = py_file.read_text()
            literals = _collect_string_literals(source)
            for lit in literals:
                if lit in _IMAGE_REF_LITERALS:
                    rel = py_file.relative_to(SRC)
                    violations.append(f"{rel}: hardcoded '{lit}'")
        assert not violations, (
            "Image ref strings must only be defined in image_contracts.py "
            "and consumed via the provider registry. Violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_display_names_not_hardcoded_outside_canonical(self) -> None:
        """Display name strings ('Claude Code', 'Codex') should only appear
        as hardcoded values in the registry, resolution module, and adapters."""
        display_names = {"Claude Code", "Codex"}
        allowed_files = (
            _DISPLAY_NAME_CANONICAL
            | _DISPLAY_NAME_ADAPTER_ALLOWLIST
            | _DISPLAY_NAME_LEGACY_ALLOWLIST
        )
        violations: list[str] = []
        for py_file in sorted(SRC.rglob("*.py")):
            if "__pycache__" in str(py_file):
                continue
            if py_file.name in allowed_files:
                continue
            # Skip __init__.py re-exports and test files
            if py_file.name == "__init__.py":
                continue
            source = py_file.read_text()
            literals = _collect_string_literals(source)
            for lit in literals:
                if lit in display_names:
                    rel = py_file.relative_to(SRC)
                    violations.append(f"{rel}: hardcoded '{lit}'")
        assert not violations, (
            "Display name strings must come from the provider registry or "
            "resolution module. Adapter modules may duplicate them. Violations:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_provider_registry_keys_match_dispatch(self) -> None:
        """PROVIDER_REGISTRY and _PROVIDER_DISPATCH must cover the same providers."""
        from scc_cli.commands.launch.dependencies import _PROVIDER_DISPATCH
        from scc_cli.core.provider_registry import PROVIDER_REGISTRY

        registry_keys = set(PROVIDER_REGISTRY.keys())
        dispatch_keys = set(_PROVIDER_DISPATCH.keys())
        assert registry_keys == dispatch_keys, (
            f"Provider registry keys {registry_keys} differ from "
            f"dispatch table keys {dispatch_keys}. "
            "Both must cover the same set of known providers."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Part 3: preflight.py architecture guard (D046)
# ─────────────────────────────────────────────────────────────────────────────

# Allowed core/ imports at the top-level of preflight.py (types and errors only).
_ALLOWED_CORE_TOP_LEVEL = frozenset({
    "scc_cli.core.contracts",
    "scc_cli.core.errors",
})


class TestPreflightArchitectureGuard:
    """preflight.py must not import core/ modules at top-level except types/errors."""

    def test_preflight_top_level_core_imports(self) -> None:
        """D046: preflight.py command-layer module must not depend on core/
        logic at the top level. Only types (contracts) and errors are allowed.
        Deferred (function-level) imports are fine for runtime dispatch."""
        source = _PREFLIGHT_MODULE.read_text()
        tree = ast.parse(source)

        violations: list[str] = []
        for node in ast.iter_child_nodes(tree):
            # Only check top-level imports
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("scc_cli.core."):
                    if node.module not in _ALLOWED_CORE_TOP_LEVEL:
                        names = [a.name for a in node.names]
                        violations.append(
                            f"line {node.lineno}: from {node.module} import {', '.join(names)}"
                        )

        assert not violations, (
            "preflight.py has top-level imports from core/ that are not types/errors. "
            "Move logic imports to function-level (deferred) if needed:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )
