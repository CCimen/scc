"""Claude renderer: project ArtifactRenderPlan into Claude-native surfaces.

Adapter-owned renderer that consumes a provider-neutral ArtifactRenderPlan
and projects it into Claude Code's native file structures and settings.

Claude-native surfaces (per spec-06):
- Skills: writes ``skill.json`` metadata under ``.claude/.scc-managed/skills/{name}/``
- MCP servers: produces ``mcpServers`` entries in the settings fragment
- Native integrations (metadata-only — the renderer writes SCC-managed
  JSON metadata files, not the actual native content):
  - ``.claude/.scc-managed/hooks/{name}.json``: hook metadata
  - ``settings_fragment.extraKnownMarketplaces``: marketplace source entries
  - ``settings_fragment.enabledPlugins``: plugin enablement entries
  - ``.claude/.scc-managed/instructions/{name}.json``: instruction metadata

The renderer is deterministic and idempotent — the same plan + workspace
always produce the same output.  Actual content fetching (git clone, URL
download) is NOT the renderer's job; it writes metadata and references that
the launch pipeline or runtime can later resolve.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scc_cli.core.errors import MaterializationError
from scc_cli.core.governed_artifacts import (
    ArtifactKind,
    ArtifactRenderPlan,
    PortableArtifact,
    ProviderArtifactBinding,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Renderer result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RendererResult:
    """Result of rendering an ArtifactRenderPlan to Claude-native surfaces.

    Attributes:
        rendered_paths: Files/directories written to workspace.
        skipped_artifacts: Artifact names that were in the plan but could not
            be rendered (carried from the plan or added by the renderer).
        warnings: Non-fatal issues encountered during rendering.
        settings_fragment: Dict fragment to merge into settings.local.json.
            Caller (launch pipeline) owns the actual merge.
    """

    rendered_paths: tuple[Path, ...] = ()
    skipped_artifacts: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    settings_fragment: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# SCC-managed output directory within the Claude workspace.
# Keeps bundle-rendered content separate from user-authored Claude files.
SCC_MANAGED_DIR = ".claude/.scc-managed"
SKILLS_SUBDIR = "skills"
HOOKS_SUBDIR = "hooks"
INSTRUCTIONS_SUBDIR = "instructions"

# Known native_config keys for Claude native integrations.
_INTEGRATION_KEYS = frozenset(
    {"hooks", "marketplace_bundle", "plugin_bundle", "instructions"}
)


# ---------------------------------------------------------------------------
# Binding dispatch helpers
# ---------------------------------------------------------------------------


def _render_skill_binding(
    binding: ProviderArtifactBinding,
    workspace: Path,
    bundle_id: str,
) -> tuple[list[Path], list[str]]:
    """Render a skill binding into the Claude skill installation surface.

    Writes a skill metadata file under
    ``<workspace>/.claude/.scc-managed/skills/<safe_name>/skill.json``.

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

    skill_dir = workspace / SCC_MANAGED_DIR / SKILLS_SUBDIR / safe_name

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
    """Render an MCP server binding into a settings fragment.

    Produces a ``{server_name: server_config}`` dict suitable for merging
    into the ``mcpServers`` key of settings.local.json.

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
) -> tuple[list[Path], dict[str, Any], list[str]]:
    """Render a native integration binding into Claude-specific surfaces.

    Processes known native_config keys:
    - ``hooks``: writes hook metadata under ``.scc-managed/hooks/``
    - ``marketplace_bundle``: adds extraKnownMarketplaces entry to fragment
    - ``plugin_bundle``: adds enabledPlugins entry to fragment
    - ``instructions``: writes instruction metadata under ``.scc-managed/instructions/``

    Returns:
        (rendered_paths, settings_fragment, warnings)

    Raises:
        MaterializationError: If any file write operation fails.
    """
    rendered: list[Path] = []
    warnings: list[str] = []
    settings: dict[str, Any] = {}
    config = binding.native_config

    # ── hooks ──────────────────────────────────────────────────────────────
    if "hooks" in config:
        hooks_ref = config["hooks"]
        hooks_dir = workspace / SCC_MANAGED_DIR / HOOKS_SUBDIR

        safe_name = Path(hooks_ref).stem
        hooks_metadata: dict[str, Any] = {
            "source": hooks_ref,
            "provider": "claude",
            "bundle_id": bundle_id,
            "managed_by": "scc",
        }
        hooks_path = hooks_dir / f"{safe_name}.json"
        try:
            hooks_dir.mkdir(parents=True, exist_ok=True)
            hooks_path.write_text(json.dumps(hooks_metadata, indent=2) + "\n")
        except OSError as exc:
            raise MaterializationError(
                bundle_id=bundle_id,
                artifact_name=f"hooks:{hooks_ref}",
                target_path=str(hooks_path),
                reason=str(exc),
            ) from exc
        rendered.append(hooks_path)

    # ── marketplace_bundle ─────────────────────────────────────────────────
    if "marketplace_bundle" in config:
        marketplace_ref = config["marketplace_bundle"]
        marketplace_name = Path(marketplace_ref).name
        settings.setdefault("extraKnownMarketplaces", {})[marketplace_name] = {
            "source": {
                "source": "directory",
                "path": marketplace_ref,
            },
        }

    # ── plugin_bundle ──────────────────────────────────────────────────────
    if "plugin_bundle" in config:
        plugin_ref = config["plugin_bundle"]
        plugin_name = Path(plugin_ref).name
        settings.setdefault("enabledPlugins", {})[plugin_name] = True

    # ── instructions ───────────────────────────────────────────────────────
    if "instructions" in config:
        instructions_ref = config["instructions"]
        instructions_dir = workspace / SCC_MANAGED_DIR / INSTRUCTIONS_SUBDIR

        safe_name = Path(instructions_ref).stem
        instructions_metadata: dict[str, Any] = {
            "source": instructions_ref,
            "provider": "claude",
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

    return rendered, settings, warnings


# ---------------------------------------------------------------------------
# Settings fragment merge helper
# ---------------------------------------------------------------------------


def _merge_settings_fragment(
    target: dict[str, Any],
    source: dict[str, Any],
) -> None:
    """Merge *source* settings fragment into *target*, combining nested dicts."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            target[key].update(value)
        else:
            target[key] = value


# ---------------------------------------------------------------------------
# Binding classifier
# ---------------------------------------------------------------------------


def _classify_binding(
    binding: ProviderArtifactBinding,
) -> str:
    """Classify a binding as 'skill', 'mcp', 'native', or 'unknown'.

    Classification order:
    1. native_config contains integration keys → native
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
# Portable artifact rendering (D023)
# ---------------------------------------------------------------------------


def _render_portable_skill(
    artifact: PortableArtifact,
    workspace: Path,
    bundle_id: str,
) -> tuple[list[Path], list[str]]:
    """Render a portable skill that has no provider-specific binding.

    Uses the artifact's source metadata to write skill placement metadata
    under ``.claude/.scc-managed/skills/<safe_name>/skill.json``.

    Returns:
        (rendered_paths, warnings)

    Raises:
        MaterializationError: If the skill metadata file cannot be written.
    """
    rendered: list[Path] = []
    warnings: list[str] = []

    safe_name = artifact.name.replace("/", "_").replace("\\", "_").replace("..", "_")
    skill_dir = workspace / SCC_MANAGED_DIR / SKILLS_SUBDIR / safe_name

    metadata: dict[str, Any] = {
        "name": artifact.name,
        "provider": "claude",
        "bundle_id": bundle_id,
        "managed_by": "scc",
        "portable": True,
    }
    if artifact.source_type:
        metadata["source_type"] = artifact.source_type
    if artifact.source_url:
        metadata["source_url"] = artifact.source_url
    if artifact.source_path:
        metadata["source_path"] = artifact.source_path
    if artifact.source_ref:
        metadata["source_ref"] = artifact.source_ref
    if artifact.version:
        metadata["version"] = artifact.version

    metadata_path = skill_dir / "skill.json"
    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    except OSError as exc:
        raise MaterializationError(
            bundle_id=bundle_id,
            artifact_name=artifact.name,
            target_path=str(metadata_path),
            reason=str(exc),
        ) from exc
    rendered.append(metadata_path)

    return rendered, warnings


def _render_portable_mcp(
    artifact: PortableArtifact,
    bundle_id: str,
) -> tuple[dict[str, Any], list[str]]:
    """Render a portable MCP server that has no provider-specific binding.

    Uses the artifact's source metadata to produce a settings fragment entry.
    For MCP servers with source_url, renders as SSE transport by default.

    Returns:
        (mcp_config_dict, warnings)
    """
    warnings: list[str] = []

    server_name = artifact.name
    server_config: dict[str, Any] = {
        "managed_by": "scc",
        "bundle_id": bundle_id,
        "portable": True,
    }

    if artifact.source_url:
        server_config["type"] = "sse"
        server_config["url"] = artifact.source_url
    else:
        warnings.append(
            f"Portable MCP server '{artifact.name}' in bundle '{bundle_id}' "
            "has no source_url; cannot determine connection endpoint"
        )
        server_config["type"] = "sse"

    if artifact.source_ref:
        server_config["source_ref"] = artifact.source_ref
    if artifact.version:
        server_config["version"] = artifact.version

    return {server_name: server_config}, warnings


# ---------------------------------------------------------------------------
# Main renderer
# ---------------------------------------------------------------------------


def render_claude_artifacts(
    plan: ArtifactRenderPlan,
    workspace: Path,
) -> RendererResult:
    """Project an ArtifactRenderPlan into Claude-native surfaces.

    Consumes a provider-neutral ArtifactRenderPlan produced by the core
    bundle resolver and renders it into Claude Code's native file structures.

    Rendering is deterministic and idempotent — the same plan and workspace
    always produce the same output.

    The renderer dispatches each binding based on its characteristics:
    - Bindings with integration-specific native_config keys → native integration
    - Bindings with transport_type → MCP server definition
    - Bindings with only native_ref → skill placement

    The ``settings_fragment`` in the result is NOT written to
    settings.local.json by the renderer.  The calling launch pipeline
    (T05) owns the merge into the active settings file.

    Args:
        plan: ArtifactRenderPlan to render (must target provider 'claude').
        workspace: Root directory for the workspace (project root).

    Returns:
        RendererResult with rendered paths, skipped items, warnings,
        and a settings fragment for the caller to merge.
    """
    if plan.provider != "claude":
        return RendererResult(
            warnings=(
                f"Plan targets provider '{plan.provider}', not 'claude'; "
                "nothing rendered",
            ),
            skipped_artifacts=plan.effective_artifacts,
        )

    all_rendered: list[Path] = []
    all_warnings: list[str] = []
    merged_settings: dict[str, Any] = {}

    for binding in plan.bindings:
        if binding.provider != "claude":
            all_warnings.append(
                f"Binding for provider '{binding.provider}' found in "
                f"Claude plan for bundle '{plan.bundle_id}'; skipping"
            )
            continue

        kind = _classify_binding(binding)

        if kind == "native":
            paths, fragment, warnings = _render_native_integration_binding(
                binding, workspace, plan.bundle_id
            )
            all_rendered.extend(paths)
            all_warnings.extend(warnings)
            _merge_settings_fragment(merged_settings, fragment)

        elif kind == "mcp":
            mcp_config, warnings = _render_mcp_binding(binding, plan.bundle_id)
            all_warnings.extend(warnings)
            merged_settings.setdefault("mcpServers", {}).update(mcp_config)

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

    # Render portable artifacts that have no provider-specific binding (D023)
    for portable in plan.portable_artifacts:
        if portable.kind == ArtifactKind.SKILL:
            paths, warnings = _render_portable_skill(
                portable, workspace, plan.bundle_id
            )
            all_rendered.extend(paths)
            all_warnings.extend(warnings)

        elif portable.kind == ArtifactKind.MCP_SERVER:
            mcp_config, warnings = _render_portable_mcp(
                portable, plan.bundle_id
            )
            all_warnings.extend(warnings)
            merged_settings.setdefault("mcpServers", {}).update(mcp_config)

    # Write the settings fragment to a per-bundle file for audit/debug
    if merged_settings:
        settings_dir = workspace / ".claude"

        safe_bundle = plan.bundle_id.replace("/", "_").replace("\\", "_")
        fragment_path = settings_dir / f".scc-settings-{safe_bundle}.json"
        try:
            settings_dir.mkdir(parents=True, exist_ok=True)
            fragment_path.write_text(json.dumps(merged_settings, indent=2) + "\n")
        except OSError as exc:
            raise MaterializationError(
                bundle_id=plan.bundle_id,
                artifact_name="settings_fragment",
                target_path=str(fragment_path),
                reason=str(exc),
            ) from exc
        all_rendered.append(fragment_path)

    return RendererResult(
        rendered_paths=tuple(all_rendered),
        skipped_artifacts=plan.skipped,
        warnings=tuple(all_warnings),
        settings_fragment=merged_settings,
    )
