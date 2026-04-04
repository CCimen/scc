"""Codex renderer: project ArtifactRenderPlan into Codex-native surfaces.

Adapter-owned renderer that consumes a provider-neutral ArtifactRenderPlan
and projects it into Codex's native file structures and config surfaces.

Codex-native surfaces (per spec-06):
- Skills: placed under .agents/skills/{name}/
- MCP servers: entries in .mcp.json (workspace-scoped)
- Native integrations:
  - .codex-plugin/plugin.json for plugin bundles
  - .codex/rules/*.rules for rule files
  - .codex/hooks.json for hook definitions
  - AGENTS.md content via .codex/.scc-managed/instructions/

Codex surfaces are intentionally asymmetric from Claude (D019/spec-06).
Rules and hooks are separate native config surfaces, not plugin components.
The renderer does NOT force Codex surfaces into Claude plugin shapes.

The renderer is deterministic and idempotent — the same plan + workspace
always produce the same output.  Actual content fetching (git clone, URL
download) is NOT the renderer's job; it writes metadata and references.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scc_cli.core.errors import MaterializationError
from scc_cli.core.governed_artifacts import ArtifactRenderPlan, ProviderArtifactBinding

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Renderer result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RendererResult:
    """Result of rendering an ArtifactRenderPlan to Codex-native surfaces.

    Attributes:
        rendered_paths: Files/directories written to workspace.
        skipped_artifacts: Artifact names that were in the plan but could not
            be rendered (carried from the plan or added by the renderer).
        warnings: Non-fatal issues encountered during rendering.
        mcp_fragment: Dict fragment to merge into .mcp.json.
            Caller (launch pipeline) owns the actual merge.
    """

    rendered_paths: tuple[Path, ...] = ()
    skipped_artifacts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    mcp_fragment: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Codex skill installation surface.
SKILLS_DIR = ".agents/skills"

# Codex config directories.
CODEX_CONFIG_DIR = ".codex"
CODEX_RULES_DIR = ".codex/rules"
CODEX_PLUGIN_DIR = ".codex-plugin"

# SCC-managed output directory within the Codex workspace for instructions.
SCC_MANAGED_DIR = ".codex/.scc-managed"
INSTRUCTIONS_SUBDIR = "instructions"

# SCC section markers for merge-safe single-file surfaces.
SCC_SECTION_START = "# --- SCC-MANAGED START (do not edit) ---"
SCC_SECTION_END = "# --- SCC-MANAGED END ---"

# Known native_config keys for Codex native integrations.
_INTEGRATION_KEYS = frozenset(
    {"plugin_bundle", "rules", "hooks", "instructions"}
)


# ---------------------------------------------------------------------------
# Binding dispatch helpers
# ---------------------------------------------------------------------------


def _render_skill_binding(
    binding: ProviderArtifactBinding,
    workspace: Path,
    bundle_id: str,
) -> tuple[list[Path], list[str]]:
    """Render a skill binding into the Codex skill installation surface.

    Writes a skill metadata file under
    ``<workspace>/.agents/skills/<safe_name>/skill.json``.

    Returns:
        (rendered_paths, warnings)

    Raises:
        MaterializationError: If the skill metadata file cannot be written.
    """
    rendered: list[Path] = []
    warnings: list[str] = []

    skill_ref = binding.native_ref
    if not skill_ref:
        warnings.append(
            f"Skill binding in bundle '{bundle_id}' has no native_ref; "
            "cannot determine skill placement"
        )
        return rendered, warnings

    # Sanitise the ref for filesystem usage
    safe_name = skill_ref.replace("/", "_").replace("\\", "_").replace("..", "_")

    skill_dir = workspace / SKILLS_DIR / safe_name

    metadata: dict[str, Any] = {
        "native_ref": binding.native_ref,
        "provider": binding.provider,
        "bundle_id": bundle_id,
        "managed_by": "scc",
    }
    if binding.native_config:
        metadata["native_config"] = dict(binding.native_config)

    metadata_path = skill_dir / "skill.json"
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    except OSError as exc:
        raise MaterializationError(
            bundle_id=bundle_id,
            artifact_name=skill_ref,
            target_path=str(metadata_path),
            reason=str(exc),
        ) from exc
    rendered.append(metadata_path)

    return rendered, warnings


def _render_mcp_binding(
    binding: ProviderArtifactBinding,
    bundle_id: str,
) -> tuple[dict[str, Any], list[str]]:
    """Render an MCP server binding into an .mcp.json fragment.

    Produces a ``{server_name: server_config}`` dict suitable for merging
    into the workspace ``.mcp.json`` file.

    Returns:
        (mcp_config_dict, warnings)
    """
    warnings: list[str] = []

    server_name = binding.native_ref or f"scc-{bundle_id}-mcp"
    transport = binding.transport_type or "sse"
    config = dict(binding.native_config)

    server_config: dict[str, Any] = {"type": transport}

    if transport in ("sse", "http"):
        url = config.pop("url", None)
        if url:
            server_config["url"] = url
        else:
            warnings.append(
                f"MCP server '{server_name}' has transport '{transport}' "
                "but no 'url' in binding native_config"
            )
        # Collect header_* keys → headers dict
        headers: dict[str, str] = {}
        for key in list(config):
            if key.startswith("header_"):
                headers[key[7:]] = config.pop(key)
        if headers:
            server_config["headers"] = headers

    elif transport == "stdio":
        command = config.pop("command", None)
        if command:
            server_config["command"] = command
        else:
            warnings.append(
                f"MCP server '{server_name}' has transport 'stdio' "
                "but no 'command' in binding native_config"
            )
        args_raw = config.pop("args", None)
        if args_raw:
            server_config["args"] = (
                args_raw.split() if isinstance(args_raw, str) else [str(args_raw)]
            )
        # Collect env_* keys → env dict
        env: dict[str, str] = {}
        for key in list(config):
            if key.startswith("env_"):
                env[key[4:]] = config.pop(key)
        if env:
            server_config["env"] = env

    return {server_name: server_config}, warnings


def _render_native_integration_binding(
    binding: ProviderArtifactBinding,
    workspace: Path,
    bundle_id: str,
) -> tuple[list[Path], list[str]]:
    """Render a native integration binding into Codex-specific surfaces.

    Processes known native_config keys:
    - ``plugin_bundle``: writes plugin manifest under ``.codex-plugin/``
    - ``rules``: writes rule metadata under ``.codex/rules/``
    - ``hooks``: writes hook metadata into ``.codex/hooks.json`` (merge-safe)
    - ``instructions``: writes instruction metadata under
      ``.codex/.scc-managed/instructions/``

    Returns:
        (rendered_paths, warnings)

    Raises:
        MaterializationError: If any file write operation fails.
        MergeConflictError: If hooks.json has conflicting SCC-managed keys
            from a different bundle that cannot be safely merged.
    """
    rendered: list[Path] = []
    warnings: list[str] = []
    config = binding.native_config

    # ── plugin_bundle ──────────────────────────────────────────────────────
    if "plugin_bundle" in config:
        plugin_ref = config["plugin_bundle"]
        plugin_dir = workspace / CODEX_PLUGIN_DIR

        plugin_manifest: dict[str, Any] = {
            "source": plugin_ref,
            "provider": "codex",
            "bundle_id": bundle_id,
            "managed_by": "scc",
        }
        plugin_path = plugin_dir / "plugin.json"
        try:
            plugin_dir.mkdir(parents=True, exist_ok=True)
            plugin_path.write_text(json.dumps(plugin_manifest, indent=2) + "\n")
        except OSError as exc:
            raise MaterializationError(
                bundle_id=bundle_id,
                artifact_name=f"plugin:{plugin_ref}",
                target_path=str(plugin_path),
                reason=str(exc),
            ) from exc
        rendered.append(plugin_path)

    # ── rules ──────────────────────────────────────────────────────────────
    if "rules" in config:
        rules_ref = config["rules"]
        rules_dir = workspace / CODEX_RULES_DIR

        safe_name = Path(rules_ref).stem
        rules_metadata: dict[str, Any] = {
            "source": rules_ref,
            "provider": "codex",
            "bundle_id": bundle_id,
            "managed_by": "scc",
        }
        rules_path = rules_dir / f"{safe_name}.rules.json"
        try:
            rules_dir.mkdir(parents=True, exist_ok=True)
            rules_path.write_text(json.dumps(rules_metadata, indent=2) + "\n")
        except OSError as exc:
            raise MaterializationError(
                bundle_id=bundle_id,
                artifact_name=f"rules:{rules_ref}",
                target_path=str(rules_path),
                reason=str(exc),
            ) from exc
        rendered.append(rules_path)

    # ── hooks ──────────────────────────────────────────────────────────────
    if "hooks" in config:
        hooks_ref = config["hooks"]
        codex_dir = workspace / CODEX_CONFIG_DIR

        hooks_metadata: dict[str, Any] = {
            "source": hooks_ref,
            "provider": "codex",
            "bundle_id": bundle_id,
            "managed_by": "scc",
        }
        hooks_path = codex_dir / "hooks.json"

        # Merge strategy: read existing file, update SCC-managed entries.
        # The entire read-merge-write sequence is wrapped because even
        # hooks_path.exists() can raise PermissionError on a locked dir.
        try:
            existing_hooks: dict[str, Any] = {}
            if hooks_path.exists():
                try:
                    existing_hooks = json.loads(hooks_path.read_text())
                except json.JSONDecodeError:
                    warnings.append(
                        f"Could not parse existing {hooks_path}; overwriting"
                    )

            existing_hooks.setdefault("scc_managed", {})[bundle_id] = hooks_metadata
            codex_dir.mkdir(parents=True, exist_ok=True)
            hooks_path.write_text(json.dumps(existing_hooks, indent=2) + "\n")
        except OSError as exc:
            raise MaterializationError(
                bundle_id=bundle_id,
                artifact_name=f"hooks:{hooks_ref}",
                target_path=str(hooks_path),
                reason=str(exc),
            ) from exc
        rendered.append(hooks_path)

    # ── instructions ───────────────────────────────────────────────────────
    if "instructions" in config:
        instructions_ref = config["instructions"]
        instructions_dir = workspace / SCC_MANAGED_DIR / INSTRUCTIONS_SUBDIR

        safe_name = Path(instructions_ref).stem
        instructions_metadata: dict[str, Any] = {
            "source": instructions_ref,
            "provider": "codex",
            "bundle_id": bundle_id,
            "managed_by": "scc",
        }
        instr_path = instructions_dir / f"{safe_name}.json"
        try:
            instructions_dir.mkdir(parents=True, exist_ok=True)
            instr_path.write_text(json.dumps(instructions_metadata, indent=2) + "\n")
        except OSError as exc:
            raise MaterializationError(
                bundle_id=bundle_id,
                artifact_name=f"instructions:{instructions_ref}",
                target_path=str(instr_path),
                reason=str(exc),
            ) from exc
        rendered.append(instr_path)

    return rendered, warnings


# ---------------------------------------------------------------------------
# Binding classifier
# ---------------------------------------------------------------------------


def _classify_binding(
    binding: ProviderArtifactBinding,
) -> str:
    """Classify a binding as 'skill', 'mcp', 'native', or 'unknown'.

    Classification order:
    1. native_config contains Codex integration keys → native
    2. transport_type is set → mcp
    3. native_ref is set (no integration keys) → skill
    4. otherwise → unknown
    """
    native_keys = set(binding.native_config.keys())
    if native_keys & _INTEGRATION_KEYS:
        return "native"
    if binding.transport_type:
        return "mcp"
    if binding.native_ref:
        return "skill"
    return "unknown"


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------


def render_codex_artifacts(
    plan: ArtifactRenderPlan,
    workspace: Path,
) -> RendererResult:
    """Project an ArtifactRenderPlan into Codex-native surfaces.

    Consumes a provider-neutral ArtifactRenderPlan produced by the core
    bundle resolver and renders it into Codex's native file structures.

    Rendering is deterministic and idempotent — the same plan and workspace
    always produce the same output.

    The renderer dispatches each binding based on its characteristics:
    - Bindings with integration-specific native_config keys → native integration
    - Bindings with transport_type → MCP server definition
    - Bindings with only native_ref → skill placement

    The ``mcp_fragment`` in the result is NOT written to ``.mcp.json``
    by the renderer.  The calling launch pipeline (T05) owns the merge
    into the active MCP config file.

    Args:
        plan: ArtifactRenderPlan to render (must target provider 'codex').
        workspace: Root directory for the workspace (project root).

    Returns:
        RendererResult with rendered paths, skipped items, warnings,
        and an MCP fragment for the caller to merge.
    """
    if plan.provider != "codex":
        return RendererResult(
            warnings=(
                f"Plan targets provider '{plan.provider}', not 'codex'; "
                "nothing rendered",
            ),
            skipped_artifacts=plan.effective_artifacts,
        )

    all_rendered: list[Path] = []
    all_warnings: list[str] = []
    merged_mcp: dict[str, Any] = {}

    for binding in plan.bindings:
        if binding.provider != "codex":
            all_warnings.append(
                f"Binding for provider '{binding.provider}' found in "
                f"Codex plan for bundle '{plan.bundle_id}'; skipping"
            )
            continue

        kind = _classify_binding(binding)

        if kind == "native":
            paths, warnings = _render_native_integration_binding(
                binding, workspace, plan.bundle_id
            )
            all_rendered.extend(paths)
            all_warnings.extend(warnings)

        elif kind == "mcp":
            mcp_config, warnings = _render_mcp_binding(binding, plan.bundle_id)
            all_warnings.extend(warnings)
            merged_mcp.setdefault("mcpServers", {}).update(mcp_config)

        elif kind == "skill":
            paths, warnings = _render_skill_binding(
                binding, workspace, plan.bundle_id
            )
            all_rendered.extend(paths)
            all_warnings.extend(warnings)

        else:
            all_warnings.append(
                f"Binding in bundle '{plan.bundle_id}' has no native_ref, "
                "transport_type, or recognised native_config keys; skipping"
            )

    # Write the MCP fragment to a per-bundle audit file for debug/diagnostics
    if merged_mcp:
        codex_dir = workspace / CODEX_CONFIG_DIR

        safe_bundle = plan.bundle_id.replace("/", "_").replace("\\", "_")
        fragment_path = codex_dir / f".scc-mcp-{safe_bundle}.json"
        try:
            codex_dir.mkdir(parents=True, exist_ok=True)
            fragment_path.write_text(json.dumps(merged_mcp, indent=2) + "\n")
        except OSError as exc:
            raise MaterializationError(
                bundle_id=plan.bundle_id,
                artifact_name="mcp_fragment",
                target_path=str(fragment_path),
                reason=str(exc),
            ) from exc
        all_rendered.append(fragment_path)

    return RendererResult(
        rendered_paths=tuple(all_rendered),
        skipped_artifacts=plan.skipped,
        warnings=tuple(all_warnings),
        mcp_fragment=merged_mcp,
    )
