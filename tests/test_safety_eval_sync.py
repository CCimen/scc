"""Sync guardrail: detect drift between core originals and evaluator copies.

The standalone scc_safety_eval package contains copies of three modules
from scc_cli.core/. The only expected differences are import lines
(scc_cli.core.X → relative .X). This test normalizes those import lines
and asserts the files are otherwise identical — if someone edits core
logic without updating the evaluator copy, this test fails.
"""

from __future__ import annotations

from pathlib import Path

# ── File pairs to compare ──────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parent.parent

_SYNC_PAIRS: list[tuple[Path, Path]] = [
    (
        _PROJECT_ROOT / "src" / "scc_cli" / "core" / "shell_tokenizer.py",
        _PROJECT_ROOT
        / "images"
        / "scc-base"
        / "wrappers"
        / "scc_safety_eval"
        / "shell_tokenizer.py",
    ),
    (
        _PROJECT_ROOT / "src" / "scc_cli" / "core" / "git_safety_rules.py",
        _PROJECT_ROOT
        / "images"
        / "scc-base"
        / "wrappers"
        / "scc_safety_eval"
        / "git_safety_rules.py",
    ),
    (
        _PROJECT_ROOT / "src" / "scc_cli" / "core" / "network_tool_rules.py",
        _PROJECT_ROOT
        / "images"
        / "scc-base"
        / "wrappers"
        / "scc_safety_eval"
        / "network_tool_rules.py",
    ),
]

# Known import-line rewrites: core → standalone
_IMPORT_NORMALIZATION = {
    "from scc_cli.core.contracts": "from .contracts",
    "from scc_cli.core.enums": "from .enums",
    "from scc_cli.core.shell_tokenizer": "from .shell_tokenizer",
}


def _normalize_imports(text: str) -> str:
    """Normalize core-style imports to standalone-style so files compare equal."""
    for core_form, relative_form in _IMPORT_NORMALIZATION.items():
        text = text.replace(core_form, relative_form)
    return text


class TestSafetyEvalSync:
    """Ensure evaluator copies stay in sync with core originals."""

    def test_shell_tokenizer_in_sync(self) -> None:
        core, standalone = _SYNC_PAIRS[0]
        core_text = _normalize_imports(core.read_text())
        standalone_text = standalone.read_text()
        assert core_text == standalone_text, (
            f"shell_tokenizer.py has drifted between core and evaluator.\n"
            f"Core: {core}\nEvaluator: {standalone}"
        )

    def test_git_safety_rules_in_sync(self) -> None:
        core, standalone = _SYNC_PAIRS[1]
        core_text = _normalize_imports(core.read_text())
        standalone_text = standalone.read_text()
        assert core_text == standalone_text, (
            f"git_safety_rules.py has drifted between core and evaluator.\n"
            f"Core: {core}\nEvaluator: {standalone}"
        )

    def test_network_tool_rules_in_sync(self) -> None:
        core, standalone = _SYNC_PAIRS[2]
        core_text = _normalize_imports(core.read_text())
        standalone_text = standalone.read_text()
        assert core_text == standalone_text, (
            f"network_tool_rules.py has drifted between core and evaluator.\n"
            f"Core: {core}\nEvaluator: {standalone}"
        )
