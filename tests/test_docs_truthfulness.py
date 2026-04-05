"""Guardrail: prevent stale vocabulary and documentation truthfulness regressions.

After M003-S05 vocabulary cleanup, all user-facing strings, README claims, and
example configs must use the current NetworkPolicy vocabulary:
  - open
  - web-egress-enforced
  - locked-down-web

Old names (unrestricted, corp-proxy-only, corp-proxy, isolated) must not appear
as network_policy values in source, docs, or examples.  Additionally, the README
must not claim Docker Desktop is a hard requirement — it should list Docker
generically (Engine, Desktop, OrbStack, Colima) per Constitution §3.

After M004 safety engine delivery, the README must truthfully document:
  - The ``scc support safety-audit`` command
  - SCC's built-in safety engine as a core capability (not plugin-only)
  - Runtime wrappers as defense-in-depth for destructive git + explicit network tools
  - All expected core safety modules and provider adapter files must exist
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


# ===========================================================================
# M004 safety truthfulness guardrails
# ===========================================================================

CORE_SAFETY_DIR = SRC / "core"
ADAPTERS_DIR = SRC / "adapters"


# ---------------------------------------------------------------------------
# Test f: README must mention the scc support safety-audit command
# ---------------------------------------------------------------------------


def test_readme_mentions_safety_audit_command() -> None:
    """README must document the ``scc support safety-audit`` command.

    S04 added this CLI surface for inspecting safety-check audit events.
    The README command table or troubleshooting section must reference it.
    """
    readme_text = README.read_text(encoding="utf-8")
    assert "safety-audit" in readme_text, (
        "README.md does not mention 'safety-audit'. "
        "The `scc support safety-audit` command (added in M004/S04) must be documented."
    )


# ---------------------------------------------------------------------------
# Test g: README must describe core safety engine (not plugin-only)
# ---------------------------------------------------------------------------


def test_readme_describes_core_safety_engine() -> None:
    """README must mention the SCC-owned safety engine as a core capability.

    Per Constitution §9 (runtime-level safety beats provider luck) and M004,
    the README should describe SCC's built-in safety engine — not attribute
    command guardrails solely to the scc-safety-net plugin.
    """
    readme_text = README.read_text(encoding="utf-8").lower()
    has_safety_engine = "safety engine" in readme_text
    has_runtime_safety = "runtime safety" in readme_text
    assert has_safety_engine or has_runtime_safety, (
        "README.md does not mention 'safety engine' or 'runtime safety'. "
        "M004 delivered an SCC-owned safety engine; the README must describe "
        "it as a core capability per Constitution §9."
    )


# ---------------------------------------------------------------------------
# Test h: README enforcement scope mentions runtime wrappers
# ---------------------------------------------------------------------------


def test_readme_enforcement_scope_mentions_runtime_wrappers() -> None:
    """README enforcement scope must mention runtime wrappers and their tool coverage.

    M004/S02 delivered runtime wrappers for 7 tools (git, curl, wget, ssh, scp,
    sftp, rsync). The enforcement scope section must mention these wrappers and
    note that they are defense-in-depth (topology + proxy remain the hard control).
    """
    readme_text = README.read_text(encoding="utf-8")
    # Must mention wrappers
    assert re.search(r"[Ww]rappers?\b.*intercept|[Ww]rappers?\b.*defense", readme_text), (
        "README.md enforcement scope does not describe runtime wrappers as "
        "defense-in-depth. M004/S02 wrappers must be documented."
    )
    # Must mention at least the core network tools covered
    for tool in ("curl", "wget", "ssh"):
        assert tool in readme_text, (
            f"README.md does not mention '{tool}' in enforcement scope. "
            f"M004 runtime wrappers cover this tool."
        )


# ---------------------------------------------------------------------------
# Test i: core safety module files must exist
# ---------------------------------------------------------------------------


def test_safety_engine_core_files_exist() -> None:
    """All expected core safety modules from M004/S01 must exist on disk.

    These modules form the shared safety engine:
    - safety_engine.py (orchestrator)
    - shell_tokenizer.py (command parsing)
    - git_safety_rules.py (destructive git detection)
    - network_tool_rules.py (explicit network tool detection)
    - safety_policy_loader.py (fail-closed policy loading from S04)
    """
    expected = [
        CORE_SAFETY_DIR / "safety_engine.py",
        CORE_SAFETY_DIR / "shell_tokenizer.py",
        CORE_SAFETY_DIR / "git_safety_rules.py",
        CORE_SAFETY_DIR / "network_tool_rules.py",
        CORE_SAFETY_DIR / "safety_policy_loader.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in expected if not p.exists()]
    assert not missing, (
        f"Core safety module files missing: {missing}. "
        "These are required M004 deliverables."
    )


# ---------------------------------------------------------------------------
# Test j: provider safety adapter files must exist
# ---------------------------------------------------------------------------


def test_safety_adapter_files_exist() -> None:
    """Both provider safety adapters from M004/S03 must exist on disk.

    ClaudeSafetyAdapter and CodexSafetyAdapter are the provider-specific
    UX/audit wrappers over the shared engine.
    """
    expected = [
        ADAPTERS_DIR / "claude_safety_adapter.py",
        ADAPTERS_DIR / "codex_safety_adapter.py",
    ]
    missing = [str(p.relative_to(ROOT)) for p in expected if not p.exists()]
    assert not missing, (
        f"Safety adapter files missing: {missing}. "
        "These are required M004/S03 deliverables."
    )


# ===========================================================================
# M005 team-pack model truthfulness guardrails
# ===========================================================================


# ---------------------------------------------------------------------------
# Test k: Codex capability_profile must report supports_skills=True
# ---------------------------------------------------------------------------


def test_codex_capability_profile_supports_skills() -> None:
    """Codex capability profile must report supports_skills=True.

    The Codex renderer writes skill metadata under .agents/skills/{name}/,
    so the capability profile must not claim skills are unsupported.
    """
    from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

    profile = CodexAgentProvider().capability_profile()
    assert profile.supports_skills is True, (
        f"Codex capability_profile.supports_skills is {profile.supports_skills}. "
        "The Codex renderer handles skills; this must be True."
    )


def test_codex_capability_profile_supports_native_integrations() -> None:
    """Codex capability profile must report supports_native_integrations=True.

    The Codex renderer writes native integration metadata (rules, hooks,
    instructions, plugins) so the capability profile must not deny this.
    """
    from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

    profile = CodexAgentProvider().capability_profile()
    assert profile.supports_native_integrations is True, (
        f"Codex capability_profile.supports_native_integrations is "
        f"{profile.supports_native_integrations}. "
        "The Codex renderer handles native integrations; this must be True."
    )


# ---------------------------------------------------------------------------
# Test l: Provider capability profiles must be asymmetric-truthful
# ---------------------------------------------------------------------------


def test_provider_profiles_asymmetric_and_truthful() -> None:
    """Provider capability profiles must reflect actual renderer capabilities.

    Both providers support skills and native integrations (rendered via
    their respective renderers). Surfaces are intentionally asymmetric
    (D019/spec-06), but both must report True for supported features.
    """
    from scc_cli.adapters.claude_agent_provider import ClaudeAgentProvider
    from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

    claude = ClaudeAgentProvider().capability_profile()
    codex = CodexAgentProvider().capability_profile()

    # Both have renderers that handle skills and native integrations
    assert claude.supports_skills is True
    assert codex.supports_skills is True
    assert claude.supports_native_integrations is True
    assert codex.supports_native_integrations is True

    # Asymmetric: Codex does not support resume, Claude does
    assert claude.supports_resume is True
    assert codex.supports_resume is False

    # Provider IDs are distinct
    assert claude.provider_id != codex.provider_id


# ---------------------------------------------------------------------------
# Test m: org-v1 schema must include governed_artifacts and enabled_bundles
# ---------------------------------------------------------------------------


def test_schema_includes_governed_artifacts_section() -> None:
    """org-v1.schema.json must define a governed_artifacts property.

    M005 introduced governed artifacts as the canonical policy surface for
    skills, MCP servers, and native integrations. The schema must reflect this.
    """
    schema_path = SRC / "schemas" / "org-v1.schema.json"
    assert schema_path.exists(), "org-v1.schema.json not found"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    props = schema.get("properties", {})
    assert "governed_artifacts" in props, (
        "org-v1.schema.json does not define a 'governed_artifacts' property. "
        "M005 requires this section for artifact/bundle/binding definitions."
    )

    ga = props["governed_artifacts"]
    ga_props = ga.get("properties", {})
    for required_key in ("artifacts", "bindings", "bundles"):
        assert required_key in ga_props, (
            f"governed_artifacts schema missing '{required_key}' sub-property."
        )


def test_schema_profiles_include_enabled_bundles() -> None:
    """Profile schema must include enabled_bundles for team-pack selection.

    Teams enable bundles (not raw artifacts). The schema must allow
    enabled_bundles in profile definitions.
    """
    schema_path = SRC / "schemas" / "org-v1.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    profile_props = (
        schema.get("properties", {})
        .get("profiles", {})
        .get("additionalProperties", {})
        .get("properties", {})
    )
    assert "enabled_bundles" in profile_props, (
        "Profile schema does not include 'enabled_bundles'. "
        "Teams select bundles from governed_artifacts.bundles via this field."
    )


# ---------------------------------------------------------------------------
# Test n: Renderers must not overclaim — docstrings must say metadata-only
# ---------------------------------------------------------------------------


def test_renderer_docstrings_say_metadata_not_content() -> None:
    """Renderer module docstrings must honestly describe output as metadata.

    Both renderers write SCC-managed JSON metadata files that reference
    artifact sources. They do NOT fetch or install actual content. The
    module docstrings must reflect this to prevent overclaiming.
    """
    for renderer_name in ("claude_renderer.py", "codex_renderer.py"):
        renderer_path = ADAPTERS_DIR / renderer_name
        assert renderer_path.exists(), f"{renderer_name} not found"
        source = renderer_path.read_text(encoding="utf-8")
        assert "metadata" in source.lower()[:2000], (
            f"{renderer_name} module docstring does not mention 'metadata'. "
            "The renderer writes metadata/references, not actual native content."
        )


# ---------------------------------------------------------------------------
# Test o: sync_marketplace_settings_for_start must be marked transitional
# ---------------------------------------------------------------------------


def test_sync_marketplace_settings_for_start_is_transitional() -> None:
    """sync_marketplace_settings_for_start docstring must note it is transitional.

    This function predates the governed-artifact bundle pipeline. Its
    docstring must explicitly note it is transitional so operators
    understand the bundle pipeline is the canonical path.
    """
    start_session_path = SRC / "application" / "start_session.py"
    assert start_session_path.exists()
    source = start_session_path.read_text(encoding="utf-8")

    # Find the function and its docstring
    func_start = source.find("def sync_marketplace_settings_for_start")
    assert func_start != -1, "sync_marketplace_settings_for_start not found"

    # Check the next ~500 chars for the transitional marker
    context = source[func_start : func_start + 800]
    assert "transitional" in context.lower(), (
        "sync_marketplace_settings_for_start docstring does not mention "
        "'transitional'. It must be marked as predating the bundle pipeline."
    )


# ---------------------------------------------------------------------------
# Test p: bundle_resolver comment must not overclaim renderable for portables
# ---------------------------------------------------------------------------


def test_bundle_resolver_portable_comment_is_truthful() -> None:
    """Bundle resolver must document that portable artifacts are renderable (D023).

    Skills and MCP servers without provider bindings are portable — they
    can be rendered from source metadata alone. The resolver populates
    portable_artifacts so renderers project them into provider-native surfaces.
    The comment must reflect this D023 implementation.
    """
    resolver_path = SRC / "core" / "bundle_resolver.py"
    source = resolver_path.read_text(encoding="utf-8")

    # The comment should mention D023 and portable_artifacts
    assert "D023" in source or "portable_artifacts" in source, (
        "bundle_resolver.py portable-artifact comment does not mention "
        "D023 or portable_artifacts. The comment must document that "
        "portable skills/MCP servers are renderable without bindings."
    )


# ===========================================================================
# M007 multi-provider runtime truthfulness guardrails
# ===========================================================================


# ---------------------------------------------------------------------------
# Test q: README title must say 'Sandboxed Code CLI' (D030)
# ---------------------------------------------------------------------------


def test_readme_title_says_sandboxed_code_cli() -> None:
    """README title must say 'Sandboxed Code CLI', not 'Sandboxed Claude CLI'.

    Per D030, the product name is provider-neutral. The title line must
    contain 'Sandboxed Code CLI' — not 'Sandboxed Claude CLI' or
    'Sandboxed Coding CLI'.
    """
    first_line = README.read_text(encoding="utf-8").splitlines()[0]
    assert "Sandboxed Code CLI" in first_line, (
        f"README.md title does not contain 'Sandboxed Code CLI'. Got: {first_line!r}"
    )
    assert "Sandboxed Claude CLI" not in first_line, (
        f"README.md title still contains stale 'Sandboxed Claude CLI'. Got: {first_line!r}"
    )
    assert "Sandboxed Coding CLI" not in first_line, (
        f"README.md title contains incorrect 'Sandboxed Coding CLI'. Got: {first_line!r}"
    )


# ---------------------------------------------------------------------------
# Test r: ProviderRuntimeSpec exists in core contracts, registry in core
# ---------------------------------------------------------------------------


def test_provider_runtime_spec_exists_in_core() -> None:
    """core/provider_registry.py must exist with PROVIDER_REGISTRY, and
    core/contracts.py must define ProviderRuntimeSpec.

    These are M007/S01 deliverables — the multi-provider dispatch foundation.
    """
    registry_path = SRC / "core" / "provider_registry.py"
    contracts_path = SRC / "core" / "contracts.py"

    assert registry_path.exists(), "core/provider_registry.py missing (M007/S01 deliverable)"
    assert contracts_path.exists(), "core/contracts.py missing"

    registry_src = registry_path.read_text(encoding="utf-8")
    assert "PROVIDER_REGISTRY" in registry_src, (
        "core/provider_registry.py does not define PROVIDER_REGISTRY"
    )

    contracts_src = contracts_path.read_text(encoding="utf-8")
    assert "ProviderRuntimeSpec" in contracts_src, (
        "core/contracts.py does not define ProviderRuntimeSpec"
    )


# ---------------------------------------------------------------------------
# Test s: fail-closed dispatch error exists in core/errors.py
# ---------------------------------------------------------------------------


def test_fail_closed_dispatch_error_exists() -> None:
    """core/errors.py must define InvalidProviderError for fail-closed dispatch.

    When an unknown provider_id is requested, the dispatch must fail closed
    with a typed error rather than silently falling back. M007/S01 delivers
    this error class.
    """
    errors_path = SRC / "core" / "errors.py"
    assert errors_path.exists(), "core/errors.py missing"

    source = errors_path.read_text(encoding="utf-8")
    assert "class InvalidProviderError" in source, (
        "core/errors.py does not define InvalidProviderError. "
        "M007/S01 fail-closed dispatch requires this error class."
    )


# ---------------------------------------------------------------------------
# Test t: doctor check_provider_auth exists
# ---------------------------------------------------------------------------


def test_doctor_check_provider_auth_exists() -> None:
    """doctor/checks/environment.py must define check_provider_auth.

    M007/S03 delivers provider-aware doctor checks. The check_provider_auth
    function validates provider-specific authentication prerequisites.
    """
    env_checks_path = SRC / "doctor" / "checks" / "environment.py"
    assert env_checks_path.exists(), "doctor/checks/environment.py missing"

    source = env_checks_path.read_text(encoding="utf-8")
    assert "def check_provider_auth" in source, (
        "doctor/checks/environment.py does not define check_provider_auth. "
        "M007/S03 requires provider-aware doctor checks."
    )


# ---------------------------------------------------------------------------
# Test u: core/constants.py must NOT contain Claude-specific runtime constants
# ---------------------------------------------------------------------------


def test_core_constants_no_claude_specifics() -> None:
    """core/constants.py must not contain Claude-specific runtime constants.

    Provider-specific values (SANDBOX_IMAGE, AGENT_NAME, DATA_VOLUME,
    CLAUDE_IMAGE, CLAUDE_CONTAINER) belong in adapter modules, not in
    core constants. This complements test_no_claude_constants_in_core.py
    but lives here for documentation-truthfulness continuity.
    """
    constants_path = SRC / "core" / "constants.py"
    assert constants_path.exists(), "core/constants.py missing"

    source = constants_path.read_text(encoding="utf-8")
    banned = [
        "SANDBOX_IMAGE",
        "AGENT_NAME",
        "DATA_VOLUME",
        "CLAUDE_IMAGE",
        "CLAUDE_CONTAINER",
        "CODEX_IMAGE",
        "CODEX_CONTAINER",
    ]
    found = [name for name in banned if name in source]
    assert not found, (
        f"core/constants.py contains provider-specific constants: {found}. "
        "These belong in adapter modules, not in the product-level constants file."
    )
