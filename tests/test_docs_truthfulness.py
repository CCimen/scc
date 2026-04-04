"""Guardrail: prevent stale network-mode vocabulary and documentation truthfulness regressions.

After M003-S05 vocabulary cleanup, all user-facing strings, README claims, and
example configs must use the current NetworkPolicy vocabulary:
  - open
  - web-egress-enforced
  - locked-down-web

Old names (unrestricted, corp-proxy-only, corp-proxy, isolated) must not appear
as network_policy values in source, docs, or examples.  Additionally, the README
must not claim Docker Desktop is a hard requirement — it should list Docker
generically (Engine, Desktop, OrbStack, Colima) per Constitution §3.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scc_cli.core.enums import NetworkPolicy

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "scc_cli"
COMMANDS_DIR = SRC / "commands"
EXAMPLES_DIR = ROOT / "examples"
README = ROOT / "README.md"

# Stale network-mode names that must not appear as policy values
STALE_NAMES = {"unrestricted", "corp-proxy-only", "corp-proxy", "isolated"}

# Valid network policy values drawn from the canonical enum
VALID_POLICIES = {member.value for member in NetworkPolicy}


# ---------------------------------------------------------------------------
# Test a: blocked_by strings in source must not contain stale network modes
# ---------------------------------------------------------------------------


def test_no_stale_network_modes_in_blocked_by_strings() -> None:
    """No blocked_by= string literal in src/scc_cli/ should reference old network mode names.

    We scan for string literals that appear as blocked_by arguments containing
    stale names.  The pattern matches ``blocked_by="...stale..."`` and
    ``blocked_by='...stale...'`` in Python source.
    """
    # Regex: blocked_by= followed by a string literal containing a stale name
    pattern = re.compile(
        r"""blocked_by\s*=\s*(?:f?["'])([^"']+)(?:["'])""",
    )
    violations: list[str] = []

    for py_file in sorted(SRC.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        for match in pattern.finditer(source):
            value = match.group(1)
            for stale in STALE_NAMES:
                # Match stale name as a network_policy value, not incidental English
                # e.g. "network_policy=isolated" is stale, but "isolated feature" is not
                if re.search(rf"(?:network_policy|policy)\s*[=:]\s*{re.escape(stale)}\b", value):
                    lineno = source[: match.start()].count("\n") + 1
                    rel = py_file.relative_to(SRC)
                    violations.append(f"  {rel}:{lineno}: blocked_by contains stale '{stale}' → {value!r}")

    if violations:
        raise AssertionError(
            "Stale network mode names found in blocked_by= strings.\n"
            "Use 'open', 'web-egress-enforced', or 'locked-down-web' instead.\n\n"
            "Violations:\n" + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Test b: warning/error strings in commands/ must not contain stale names
# ---------------------------------------------------------------------------


def test_no_stale_network_modes_in_user_warnings() -> None:
    """Warning and error strings in src/scc_cli/commands/ must not reference old network mode names.

    Targets string literals that mention network_policy/proxy context alongside
    a stale mode name — avoids false positives on unrelated uses of 'isolated'.
    """
    # Match string literals that contain both a context keyword and a stale name
    context_kw = r"(?:network_policy|proxy|network.mode|egress)"
    violations: list[str] = []

    for py_file in sorted(COMMANDS_DIR.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        lines = source.splitlines()
        for i, line in enumerate(lines, start=1):
            # Only inspect lines that look like they contain warning/error strings
            if not re.search(r"(?:warn|error|message|msg|print|log|click\.echo)", line, re.IGNORECASE):
                continue
            # Check if the line has a stale name in network context
            for stale in STALE_NAMES:
                if re.search(rf"{context_kw}.*\b{re.escape(stale)}\b", line, re.IGNORECASE):
                    rel = py_file.relative_to(COMMANDS_DIR)
                    violations.append(f"  commands/{rel}:{i}: stale '{stale}' → {line.strip()!r}")
                elif re.search(rf"\b{re.escape(stale)}\b.*{context_kw}", line, re.IGNORECASE):
                    rel = py_file.relative_to(COMMANDS_DIR)
                    violations.append(f"  commands/{rel}:{i}: stale '{stale}' → {line.strip()!r}")

    if violations:
        raise AssertionError(
            "Stale network mode names found in user-facing warnings/errors.\n"
            "Use 'open', 'web-egress-enforced', or 'locked-down-web' instead.\n\n"
            "Violations:\n" + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Test c: README must not claim Docker Desktop is a hard requirement
# ---------------------------------------------------------------------------


def test_readme_no_docker_desktop_hard_requirement() -> None:
    """README must not say 'Requires Docker Desktop' without mentioning alternatives.

    Per Constitution §3, Docker is listed generically. If Docker Desktop appears
    in a 'Requires' context, alternatives (Engine, OrbStack, Colima) must also
    be mentioned on the same line or within the next two lines.
    """
    readme_text = README.read_text(encoding="utf-8")
    lines = readme_text.splitlines()

    for i, line in enumerate(lines):
        if re.search(r"Requires.*Docker\s+Desktop", line, re.IGNORECASE):
            # Check current line and next two for alternatives
            context = " ".join(lines[i : i + 3])
            has_alternatives = all(
                alt.lower() in context.lower()
                for alt in ("Engine", "OrbStack", "Colima")
            )
            if not has_alternatives:
                raise AssertionError(
                    f"README.md:{i + 1}: 'Requires Docker Desktop' without mentioning "
                    "Engine/OrbStack/Colima alternatives.\n"
                    f"Line: {line!r}"
                )


# ---------------------------------------------------------------------------
# Test d: README must not contain stale network mode names as values
# ---------------------------------------------------------------------------


def test_readme_no_stale_network_mode_names() -> None:
    """README must not reference old network mode names as network_policy values.

    The word 'isolated' in prose (e.g. 'isolated environment') is acceptable.
    Only matches in JSON-like context, backticks, or adjacent to network_policy
    are flagged.
    """
    readme_text = README.read_text(encoding="utf-8")
    violations: list[str] = []

    for i, line in enumerate(readme_text.splitlines(), start=1):
        for stale in STALE_NAMES:
            # Match in backtick context: `isolated`, `unrestricted`
            if re.search(rf"`{re.escape(stale)}`", line):
                violations.append(f"  README.md:{i}: stale '{stale}' in backticks → {line.strip()!r}")
                continue
            # Match in JSON-like context: "isolated", "unrestricted"
            if re.search(rf'"{re.escape(stale)}"', line):
                violations.append(f"  README.md:{i}: stale '{stale}' in quotes → {line.strip()!r}")
                continue
            # Match adjacent to network_policy keyword
            if re.search(
                rf"network_policy.*\b{re.escape(stale)}\b", line, re.IGNORECASE
            ):
                violations.append(f"  README.md:{i}: stale '{stale}' near network_policy → {line.strip()!r}")

    if violations:
        raise AssertionError(
            "Stale network mode names found in README.md as policy values.\n"
            "Use 'open', 'web-egress-enforced', or 'locked-down-web' instead.\n\n"
            "Violations:\n" + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# Test e: example JSON files must use valid NetworkPolicy values
# ---------------------------------------------------------------------------


def test_example_json_uses_valid_network_policy_values() -> None:
    """All network_policy values in examples/*.json must be valid NetworkPolicy members."""
    if not EXAMPLES_DIR.is_dir():
        return  # No examples directory — nothing to check

    violations: list[str] = []
    json_files = sorted(EXAMPLES_DIR.glob("*.json"))

    if not json_files:
        return  # No JSON files — nothing to check

    for json_file in json_files:
        text = json_file.read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            violations.append(f"  {json_file.name}: invalid JSON")
            continue

        # Recursively find all "network_policy" values in the JSON tree
        found = _extract_network_policy_values(data)
        for path_str, value in found:
            if value not in VALID_POLICIES:
                violations.append(
                    f"  {json_file.name}: {path_str} = {value!r} "
                    f"(expected one of {sorted(VALID_POLICIES)})"
                )

    if violations:
        raise AssertionError(
            "Invalid network_policy values found in example JSON files.\n\n"
            "Violations:\n" + "\n".join(violations)
        )


def _extract_network_policy_values(
    obj: object,
    path: str = "$",
) -> list[tuple[str, str]]:
    """Recursively extract (json-path, value) pairs for 'network_policy' keys."""
    results: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            current_path = f"{path}.{key}"
            if key == "network_policy" and isinstance(value, str):
                results.append((current_path, value))
            else:
                results.extend(_extract_network_policy_values(value, current_path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(_extract_network_policy_values(item, f"{path}[{i}]"))
    return results
