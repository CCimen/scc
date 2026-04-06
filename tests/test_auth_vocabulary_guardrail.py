"""Guardrail: prevent misleading auth/readiness vocabulary in user-facing strings.

After M008-S02 vocabulary cleanup, user-facing strings must use the canonical
three-tier readiness vocabulary:

  Tier 1: "auth cache present" / "auth cache missing"
      — when we only check file existence (not validity or connectivity)

  Tier 2: "image available" / "image not found"
      — when we check whether the provider image exists locally

  Tier 3: "launch-ready"
      — ONLY when BOTH auth cache + image are confirmed present

Banned patterns:
  - "connected" used to describe auth-cache presence (misleading — implies
    live connectivity verification, but we only check file existence)
  - "sign-in required" (should be "sign-in needed" — "required" suggests
    a hard gate, but the user can skip/defer)
  - standalone "ready" meaning only one tier was checked (should not say
    "ready" when only auth OR only image was verified)
  - "not connected" as auth-cache absence wording (misleading — see above)
"""

from __future__ import annotations

import re
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "scc_cli"

# Directories containing user-facing string modules
_UI_DIRS = [
    SRC / "commands",
    SRC / "doctor",
    SRC / "ui",
]

# Also scan setup.py at package root
_EXTRA_FILES = [
    SRC / "setup.py",
]

# Files that legitimately use banned terms in variable names, docstrings,
# or non-user-facing contexts — excluded from the scan.
_EXCLUDED_STEMS = {
    # Internal error class definitions
    "errors",
    # Port/protocol definitions (docstrings describe semantics)
    "agent_provider",
    # Provider resolution internals (variable names like connected_provider_ids)
    "provider_resolution",
}


def _collect_python_files() -> list[Path]:
    """Collect all .py files from UI-facing directories plus extras."""
    files: list[Path] = []
    for d in _UI_DIRS:
        if d.exists():
            files.extend(sorted(d.rglob("*.py")))
    for f in _EXTRA_FILES:
        if f.exists():
            files.append(f)
    return files


def _extract_string_tokens(path: Path) -> list[tuple[int, str]]:
    """Extract (line_number, string_value) for all string tokens in a file.

    Uses the tokenize module to correctly isolate string literals from
    variable names, comments, and other token types.
    """
    results: list[tuple[int, str]] = []
    try:
        with open(path, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                if tok.type == tokenize.STRING:
                    # Evaluate the string literal to get the raw value
                    try:
                        val = eval(tok.string)  # noqa: S307
                        if isinstance(val, str):
                            results.append((tok.start[0], val))
                    except Exception:
                        # f-strings or complex expressions — fall back to raw
                        results.append((tok.start[0], tok.string))
    except tokenize.TokenError:
        pass
    return results


# ---------------------------------------------------------------------------
# Banned vocabulary patterns — compiled regexes
# ---------------------------------------------------------------------------

# Pattern 1: "connected" used as a status label for auth-cache presence.
# Matches strings that are exactly "connected" or "not connected" as status
# display values. Does NOT match variable names or longer phrases.
_CONNECTED_STATUS = re.compile(
    r'^"?(not )?connected"?$'
    r'|'
    r'(?:status|label|value)\s*[:=]\s*["\'](?:not )?connected["\']',
    re.IGNORECASE,
)

# Pattern 2: "sign-in required" — should be "sign-in needed"
_SIGN_IN_REQUIRED = re.compile(r"sign-in required", re.IGNORECASE)

# Pattern 3: standalone "ready" as sole auth readiness descriptor.
# This catches strings like '"ready"' used to describe auth-only status,
# but not compound terms like "launch-ready" or "not ready".
# We look for the word "ready" used as a display value in auth contexts.
_STANDALONE_READY_AUTH = re.compile(
    r"""(?:["']ready["'])"""
    r"|"
    r"""(?:else\s+["'](?:not )?ready["'])""",
)


def test_no_connected_as_auth_status() -> None:
    """User-facing strings must not use 'connected'/'not connected' for auth cache status."""
    violations: list[str] = []
    for path in _collect_python_files():
        if path.stem in _EXCLUDED_STEMS:
            continue
        for lineno, value in _extract_string_tokens(path):
            # Check for exact "connected" or "not connected" as a status value
            stripped = value.strip()
            if stripped in ("connected", "not connected"):
                violations.append(
                    f"  {path.relative_to(ROOT)}:{lineno} — "
                    f"banned auth status string: {stripped!r}"
                )
    assert not violations, (
        "Found 'connected'/'not connected' used as auth-cache status labels.\n"
        "Use 'auth cache present' / 'sign-in needed' instead.\n"
        + "\n".join(violations)
    )


def test_no_sign_in_required() -> None:
    """User-facing strings must use 'sign-in needed', not 'sign-in required'."""
    violations: list[str] = []
    for path in _collect_python_files():
        if path.stem in _EXCLUDED_STEMS:
            continue
        for lineno, value in _extract_string_tokens(path):
            if _SIGN_IN_REQUIRED.search(value):
                violations.append(
                    f"  {path.relative_to(ROOT)}:{lineno} — "
                    f"contains 'sign-in required': {value!r}"
                )
    assert not violations, (
        "Found 'sign-in required' in user-facing strings.\n"
        "Use 'sign-in needed' instead.\n"
        + "\n".join(violations)
    )


def test_no_standalone_ready_for_auth_only() -> None:
    """User-facing strings must not use bare 'ready' when only auth cache was checked.

    The word 'ready' alone implies full launch readiness (auth + image).
    When only auth cache was verified, use 'auth cache present'.
    When only the image was checked, use 'image available'.
    Use 'launch-ready' only when both are confirmed.
    """
    violations: list[str] = []

    # Scan setup.py and provider_choice.py specifically — these are the
    # known sites where auth readiness is displayed.
    target_files = [
        SRC / "setup.py",
        SRC / "commands" / "launch" / "provider_choice.py",
    ]

    for path in target_files:
        if not path.exists():
            continue
        # Read raw lines for context-aware matching
        lines = path.read_text().splitlines()
        for i, line in enumerate(lines, start=1):
            # Look for "ready" used as a display value in auth-check context
            # Pattern: string literal "ready" near auth/provider readiness logic
            if _STANDALONE_READY_AUTH.search(line):
                # Allow "launch-ready" and "not ready" in error contexts
                if "launch-ready" in line or "launch_ready" in line:
                    continue
                # Allow the pattern in comments/docstrings
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    continue
                violations.append(
                    f"  {path.relative_to(ROOT)}:{i} — "
                    f"standalone 'ready' as auth status: {stripped!r}"
                )

    assert not violations, (
        "Found standalone 'ready' used as auth-only readiness status.\n"
        "Use 'auth cache present' for auth-only, 'image available' for image-only, "
        "'launch-ready' for both.\n"
        + "\n".join(violations)
    )


def test_doctor_auth_check_uses_truthful_vocabulary() -> None:
    """Doctor auth check must use 'auth cache present' / 'auth cache missing' vocabulary."""
    env_path = SRC / "doctor" / "checks" / "environment.py"
    assert env_path.exists(), f"Expected {env_path} to exist"

    content = env_path.read_text()

    # The positive case should say "auth cache present"
    assert "auth cache present" in content, (
        "Doctor environment.py should contain 'auth cache present' for successful auth checks"
    )

    # The negative case should say "auth cache missing", not "not ready" or "not connected"
    assert "auth cache missing" in content, (
        "Doctor environment.py should contain 'auth cache missing' for failed auth checks"
    )

    # Should NOT contain misleading terms for auth status
    assert "not connected" not in content, (
        "Doctor environment.py should not use 'not connected' for auth cache absence"
    )


def test_auth_bootstrap_uses_truthful_vocabulary() -> None:
    """Auth bootstrap messages must use 'auth cache' vocabulary.

    Canonical auth messaging lives in preflight.py._ensure_auth.
    auth_bootstrap.py is a deprecated redirect with no user-facing text.
    """
    preflight_path = SRC / "commands" / "launch" / "preflight.py"
    assert preflight_path.exists(), f"Expected {preflight_path} to exist"

    content = preflight_path.read_text()

    # Should reference "auth cache" in user-facing messages
    assert "auth cache" in content, (
        "preflight.py should reference 'auth cache' in user-facing messages"
    )

    # Should NOT use "connected" as auth status
    assert '"connected"' not in content and "'connected'" not in content, (
        "preflight.py should not use 'connected' as auth status wording"
    )

    # auth_bootstrap.py still exists as a deprecated redirect
    bootstrap_path = SRC / "commands" / "launch" / "auth_bootstrap.py"
    assert bootstrap_path.exists(), (
        "auth_bootstrap.py should exist as a deprecated redirect"
    )
    bootstrap_content = bootstrap_path.read_text()
    assert "deprecated" in bootstrap_content.lower(), (
        "auth_bootstrap.py should be marked as deprecated"
    )
