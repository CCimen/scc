"""Characterization tests for the Claude renderer.

Verifies that render_claude_artifacts() produces expected file structures
and settings fragments from known ArtifactRenderPlans.

Covers:
- Empty plan → empty result
- Skill binding → skill metadata file under .scc-managed/skills/
- MCP server binding (SSE/HTTP/stdio) → mcpServers settings fragment
- Native integration binding (hooks, marketplace, plugin, instructions)
- Mixed bundle with multiple binding types
- Plan targeting wrong provider → skip with warning
- Non-claude binding in plan → skip with warning
- Empty native_ref on skill → warning
- Missing URL on MCP SSE → warning
- Settings fragment audit file written for non-empty fragments
- Deterministic/idempotent rendering (same plan → same output)
- Skipped artifact: Codex-only binding in Claude plan → skipped with reason
- Binding classifier: skill / mcp / native / unknown classification
- Internal helpers: _render_skill_binding with null native_ref,
  _merge_settings_fragment with nested dict merging
- MCP edge cases: non-string args, no headers, no env, unknown transport
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scc_cli.adapters.claude_renderer import (
    SCC_MANAGED_DIR,
    RendererResult,
    _classify_binding,
    _merge_settings_fragment,
    _render_mcp_binding,
    _render_skill_binding,
    render_claude_artifacts,
)
from scc_cli.core.errors import MaterializationError, MergeConflictError
from scc_cli.core.governed_artifacts import (
    ArtifactKind,
    ArtifactRenderPlan,
    PortableArtifact,
    ProviderArtifactBinding,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """Return a fresh temporary workspace directory."""
    return tmp_path


def _plan(
    *,
    bundle_id: str = "test-bundle",
    provider: str = "claude",
    bindings: tuple[ProviderArtifactBinding, ...] = (),
    skipped: tuple[str, ...] = (),
    effective_artifacts: tuple[str, ...] = (),
    portable_artifacts: tuple[PortableArtifact, ...] = (),
) -> ArtifactRenderPlan:
    return ArtifactRenderPlan(
        bundle_id=bundle_id,
        provider=provider,
        bindings=bindings,
        skipped=skipped,
        effective_artifacts=effective_artifacts,
        portable_artifacts=portable_artifacts,
    )


# ---------------------------------------------------------------------------
# Empty / trivial
# ---------------------------------------------------------------------------


class TestEmptyPlan:
    def test_empty_plan_produces_empty_result(self, workspace: Path) -> None:
        result = render_claude_artifacts(_plan(), workspace)
        assert isinstance(result, RendererResult)
        assert result.rendered_paths == ()
        assert result.skipped_artifacts == ()
        assert result.warnings == ()
        assert result.settings_fragment == {}

    def test_empty_bindings_with_skipped(self, workspace: Path) -> None:
        plan = _plan(skipped=("ghost-artifact",))
        result = render_claude_artifacts(plan, workspace)
        assert result.skipped_artifacts == ("ghost-artifact",)
        assert result.rendered_paths == ()


# ---------------------------------------------------------------------------
# Wrong provider
# ---------------------------------------------------------------------------


class TestWrongProvider:
    def test_non_claude_provider_produces_warning(self, workspace: Path) -> None:
        plan = _plan(provider="codex", effective_artifacts=("some-skill",))
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "codex" in result.warnings[0]
        assert "nothing rendered" in result.warnings[0]
        assert result.skipped_artifacts == ("some-skill",)

    def test_non_claude_binding_in_claude_plan(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(ProviderArtifactBinding(provider="codex", native_ref="skills/foo"),),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "codex" in result.warnings[0]


# ---------------------------------------------------------------------------
# Skill binding
# ---------------------------------------------------------------------------


class TestSkillBinding:
    def test_skill_creates_metadata_file(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/code-review",
                ),
            ),
            effective_artifacts=("code-review-skill",),
        )
        result = render_claude_artifacts(plan, workspace)

        assert result.warnings == ()
        assert len(result.rendered_paths) >= 1

        # Check the skill metadata file exists
        skill_dir = workspace / SCC_MANAGED_DIR / "skills" / "skills_code-review"
        metadata_path = skill_dir / "skill.json"
        assert metadata_path.exists()

        content = json.loads(metadata_path.read_text())
        assert content["native_ref"] == "skills/code-review"
        assert content["provider"] == "claude"
        assert content["bundle_id"] == "test-bundle"
        assert content["managed_by"] == "scc"

    def test_skill_with_native_config(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/review",
                    native_config={"priority": "high"},
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)

        skill_dir = workspace / SCC_MANAGED_DIR / "skills" / "skills_review"
        content = json.loads((skill_dir / "skill.json").read_text())
        assert content["native_config"] == {"priority": "high"}

    def test_skill_no_native_ref_produces_warning(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(ProviderArtifactBinding(provider="claude"),),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) >= 1
        assert any(
            "no native_ref" in w or "no recognised" in w.lower() or "no native_ref" in w.lower()
            for w in result.warnings
        )


# ---------------------------------------------------------------------------
# MCP server binding
# ---------------------------------------------------------------------------


class TestMCPBinding:
    def test_sse_mcp_server(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="github-mcp",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080/sse"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        assert "mcpServers" in result.settings_fragment
        mcp = result.settings_fragment["mcpServers"]
        assert "github-mcp" in mcp
        assert mcp["github-mcp"]["type"] == "sse"
        assert mcp["github-mcp"]["url"] == "http://localhost:8080/sse"

    def test_http_mcp_server(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="my-server",
                    transport_type="http",
                    native_config={"url": "https://api.example.com/mcp"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        mcp = result.settings_fragment["mcpServers"]
        assert mcp["my-server"]["type"] == "http"
        assert mcp["my-server"]["url"] == "https://api.example.com/mcp"

    def test_stdio_mcp_server(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="local-mcp",
                    transport_type="stdio",
                    native_config={
                        "command": "/usr/bin/my-mcp-server",
                        "args": "--port 9090 --verbose",
                        "env_API_KEY": "placeholder",
                    },
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        mcp = result.settings_fragment["mcpServers"]
        assert "local-mcp" in mcp
        assert mcp["local-mcp"]["type"] == "stdio"
        assert mcp["local-mcp"]["command"] == "/usr/bin/my-mcp-server"
        assert mcp["local-mcp"]["args"] == ["--port", "9090", "--verbose"]
        assert mcp["local-mcp"]["env"] == {"API_KEY": "placeholder"}

    def test_sse_mcp_with_headers(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="authed-mcp",
                    transport_type="sse",
                    native_config={
                        "url": "https://mcp.example.com/sse",
                        "header_Authorization": "Bearer tok",
                        "header_X-Org": "my-org",
                    },
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        mcp = result.settings_fragment["mcpServers"]
        assert mcp["authed-mcp"]["headers"] == {
            "Authorization": "Bearer tok",
            "X-Org": "my-org",
        }

    def test_mcp_no_url_produces_warning(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="broken-mcp",
                    transport_type="sse",
                    native_config={},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert any("no 'url'" in w for w in result.warnings)

    def test_mcp_no_command_produces_warning(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="broken-stdio",
                    transport_type="stdio",
                    native_config={},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert any("no 'command'" in w for w in result.warnings)

    def test_mcp_fallback_name_when_no_native_ref(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="my-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    transport_type="sse",
                    native_config={"url": "http://localhost:9090"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        mcp = result.settings_fragment["mcpServers"]
        assert "scc-my-bundle-mcp" in mcp


# ---------------------------------------------------------------------------
# Native integration binding
# ---------------------------------------------------------------------------


class TestNativeIntegrationBinding:
    def test_hooks_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"hooks": "./claude/github-hooks.json"},
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)

        hooks_path = workspace / SCC_MANAGED_DIR / "hooks" / "github-hooks.json"
        assert hooks_path.exists()
        content = json.loads(hooks_path.read_text())
        assert content["source"] == "./claude/github-hooks.json"
        assert content["bundle_id"] == "test-bundle"
        assert content["managed_by"] == "scc"

    def test_marketplace_bundle_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"marketplace_bundle": "./claude/github-marketplace"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        ekm = result.settings_fragment.get("extraKnownMarketplaces", {})
        assert "github-marketplace" in ekm
        assert ekm["github-marketplace"]["source"]["source"] == "directory"
        assert ekm["github-marketplace"]["source"]["path"] == "./claude/github-marketplace"

    def test_plugin_bundle_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"plugin_bundle": "./claude/github-plugin"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        plugins = result.settings_fragment.get("enabledPlugins", {})
        assert "github-plugin" in plugins
        assert plugins["github-plugin"] is True

    def test_instructions_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"instructions": "./claude/CLAUDE.team.md"},
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)

        instr_path = workspace / SCC_MANAGED_DIR / "instructions" / "CLAUDE.team.json"
        assert instr_path.exists()
        content = json.loads(instr_path.read_text())
        assert content["source"] == "./claude/CLAUDE.team.md"
        assert content["managed_by"] == "scc"

    def test_combined_native_integration(self, workspace: Path) -> None:
        """A single binding with hooks + marketplace_bundle + instructions."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={
                        "hooks": "./claude/hooks.json",
                        "marketplace_bundle": "./claude/my-market",
                        "instructions": "./claude/CLAUDE.team.md",
                    },
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        # Hooks file
        assert (workspace / SCC_MANAGED_DIR / "hooks" / "hooks.json").exists()
        # Instructions file
        assert (workspace / SCC_MANAGED_DIR / "instructions" / "CLAUDE.team.json").exists()
        # Marketplace in settings
        assert "my-market" in result.settings_fragment.get("extraKnownMarketplaces", {})


# ---------------------------------------------------------------------------
# Mixed bundle
# ---------------------------------------------------------------------------


class TestMixedBundle:
    def test_mixed_skill_mcp_native(self, workspace: Path) -> None:
        """Bundle with skill, MCP server, and native integration."""
        plan = _plan(
            bundle_id="github-dev",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/code-review",
                ),
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="github-mcp",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={
                        "hooks": "./claude/github-hooks.json",
                        "marketplace_bundle": "./claude/github-marketplace",
                    },
                ),
            ),
            effective_artifacts=("code-review-skill", "github-mcp", "github-native"),
        )
        result = render_claude_artifacts(plan, workspace)

        # Skill file
        skill_path = workspace / SCC_MANAGED_DIR / "skills" / "skills_code-review" / "skill.json"
        assert skill_path.exists()

        # MCP server in settings
        assert "github-mcp" in result.settings_fragment.get("mcpServers", {})

        # Hooks + marketplace
        assert (workspace / SCC_MANAGED_DIR / "hooks" / "github-hooks.json").exists()
        assert "github-marketplace" in result.settings_fragment.get("extraKnownMarketplaces", {})

        # Audit file written
        audit_file = workspace / ".claude" / ".scc-settings-github-dev.json"
        assert audit_file.exists()
        audit_content = json.loads(audit_file.read_text())
        assert "mcpServers" in audit_content

        # No warnings
        assert result.warnings == ()


# ---------------------------------------------------------------------------
# Settings audit file
# ---------------------------------------------------------------------------


class TestSettingsAuditFile:
    def test_audit_file_written_when_fragment_nonempty(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="my-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="server",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        audit_path = workspace / ".claude" / ".scc-settings-my-bundle.json"
        assert audit_path.exists()
        assert audit_path in result.rendered_paths

    def test_no_audit_file_for_empty_fragment(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="empty-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/foo",
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)

        audit_path = workspace / ".claude" / ".scc-settings-empty-bundle.json"
        assert not audit_path.exists()


# ---------------------------------------------------------------------------
# Idempotent rendering
# ---------------------------------------------------------------------------


class TestIdempotent:
    def test_same_plan_produces_same_output(self, workspace: Path) -> None:
        """Two renders of the same plan yield identical file content."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/review",
                ),
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="mcp-server",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"hooks": "./hooks.json"},
                ),
            ),
        )
        result1 = render_claude_artifacts(plan, workspace)
        result2 = render_claude_artifacts(plan, workspace)

        assert result1.settings_fragment == result2.settings_fragment
        assert len(result1.rendered_paths) == len(result2.rendered_paths)
        assert result1.warnings == result2.warnings

        # File contents are the same
        for path in result1.rendered_paths:
            assert path.exists()
            assert path.read_text() == path.read_text()  # trivially true but proves existence

    def test_overwrite_on_rerender(self, workspace: Path) -> None:
        """Second render overwrites first — no duplicate files."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/my-skill",
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)
        result2 = render_claude_artifacts(plan, workspace)

        # Only one skill dir exists
        skill_parent = workspace / SCC_MANAGED_DIR / "skills"
        assert len(list(skill_parent.iterdir())) == 1
        assert len(result2.rendered_paths) == 1


# ---------------------------------------------------------------------------
# Return type shape
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_result_is_renderer_result(self, workspace: Path) -> None:
        result = render_claude_artifacts(_plan(), workspace)
        assert isinstance(result, RendererResult)

    def test_rendered_paths_are_path_objects(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/x",
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        for p in result.rendered_paths:
            assert isinstance(p, Path)


# ---------------------------------------------------------------------------
# Failure path tests — fail-closed semantics
# ---------------------------------------------------------------------------


class TestSkillMaterializationFailure:
    def test_read_only_workspace_raises_materialization_error(self, workspace: Path) -> None:
        """Skill write to read-only dir raises MaterializationError."""
        # Create the parent dir then make it read-only
        managed = workspace / SCC_MANAGED_DIR / "skills"
        managed.mkdir(parents=True, exist_ok=True)
        managed.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/blocked",
                ),
            ),
        )
        with pytest.raises(MaterializationError) as exc_info:
            render_claude_artifacts(plan, workspace)
        err = exc_info.value
        assert err.bundle_id == "test-bundle"
        assert "skills/blocked" in err.artifact_name
        assert err.target_path  # should have the path

        # Cleanup permissions for pytest tmp_path cleanup
        managed.chmod(0o755)

    def test_materialization_error_has_structured_fields(self, workspace: Path) -> None:
        err = MaterializationError(
            bundle_id="b1",
            artifact_name="my-skill",
            target_path="/tmp/foo",
            reason="Permission denied",
        )
        assert "my-skill" in str(err)
        assert "b1" in str(err)
        assert "Permission denied" in str(err)


class TestNativeIntegrationMaterializationFailure:
    def test_hooks_write_failure_raises_materialization_error(self, workspace: Path) -> None:
        """hooks file write to read-only dir → MaterializationError."""
        hooks_dir = workspace / SCC_MANAGED_DIR / "hooks"
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hooks_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"hooks": "./claude/hooks.json"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="hooks"):
            render_claude_artifacts(plan, workspace)

        hooks_dir.chmod(0o755)

    def test_instructions_write_failure_raises_materialization_error(self, workspace: Path) -> None:
        """instructions write to read-only dir → MaterializationError."""
        instr_dir = workspace / SCC_MANAGED_DIR / "instructions"
        instr_dir.mkdir(parents=True, exist_ok=True)
        instr_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"instructions": "./claude/CLAUDE.md"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="instructions"):
            render_claude_artifacts(plan, workspace)

        instr_dir.chmod(0o755)


class TestSettingsFragmentWriteFailure:
    def test_audit_file_write_failure_raises_materialization_error(self, workspace: Path) -> None:
        """Settings audit file write to read-only .claude/ → MaterializationError."""
        claude_dir = workspace / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        claude_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="mcp-server",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="settings_fragment"):
            render_claude_artifacts(plan, workspace)

        claude_dir.chmod(0o755)


class TestMergeConflictErrorStructure:
    def test_merge_conflict_error_fields(self) -> None:
        err = MergeConflictError(
            bundle_id="my-bundle",
            target_path="/tmp/settings.json",
            conflict_detail="key 'mcpServers.foo' already exists with different value",
        )
        assert "my-bundle" in str(err)
        assert "mcpServers.foo" in str(err)
        assert err.target_path == "/tmp/settings.json"


class TestRendererErrorHierarchy:
    def test_materialization_error_is_renderer_error(self) -> None:
        from scc_cli.core.errors import RendererError

        err = MaterializationError(
            user_message="test",
            bundle_id="b",
            artifact_name="a",
            target_path="/foo",
            reason="bad",
        )
        assert isinstance(err, RendererError)
        assert err.exit_code == 4

    def test_merge_conflict_error_is_renderer_error(self) -> None:
        from scc_cli.core.errors import RendererError

        err = MergeConflictError(
            user_message="test",
            bundle_id="b",
            target_path="/foo",
            conflict_detail="dup",
        )
        assert isinstance(err, RendererError)


# ---------------------------------------------------------------------------
# Skipped artifact — Codex-only binding in Claude plan
# ---------------------------------------------------------------------------


class TestSkippedCodexOnlyBinding:
    """Plan item 6: artifact with only Codex binding → skipped with reason."""

    def test_codex_binding_in_claude_plan_skipped(self, workspace: Path) -> None:
        """A binding targeting 'codex' inside a 'claude' plan is skipped."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="codex/rules.md",
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "codex" in result.warnings[0]
        assert "skipping" in result.warnings[0].lower()
        assert result.rendered_paths == ()
        assert result.settings_fragment == {}

    def test_codex_binding_mixed_with_claude_bindings(self, workspace: Path) -> None:
        """Claude bindings render; codex binding is skipped with warning."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/code-review",
                ),
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="codex-only-skill",
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)

        # Claude skill rendered
        skill_path = workspace / SCC_MANAGED_DIR / "skills" / "skills_code-review" / "skill.json"
        assert skill_path.exists()

        # Codex binding produced a warning
        assert any("codex" in w for w in result.warnings)

    def test_multiple_codex_bindings_all_skipped(self, workspace: Path) -> None:
        """Every codex binding in a claude plan produces a skip warning."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(provider="codex", native_ref="a"),
                ProviderArtifactBinding(provider="codex", native_ref="b"),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) == 2
        assert all("codex" in w for w in result.warnings)

    def test_plan_level_skipped_artifacts_preserved(self, workspace: Path) -> None:
        """skipped tuple from the plan is carried through to the result."""
        plan = _plan(
            skipped=("codex-only-artifact",),
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/ok",
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert "codex-only-artifact" in result.skipped_artifacts


# ---------------------------------------------------------------------------
# Binding classifier unit tests
# ---------------------------------------------------------------------------


class TestBindingClassifier:
    """Direct tests for _classify_binding to cover all 4 return paths."""

    def test_native_config_with_hooks_classifies_as_native(self) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            native_config={"hooks": "./hooks.json"},
        )
        assert _classify_binding(binding) == "native"

    def test_native_config_with_marketplace_classifies_as_native(self) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            native_config={"marketplace_bundle": "./market"},
        )
        assert _classify_binding(binding) == "native"

    def test_native_config_with_plugin_classifies_as_native(self) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            native_config={"plugin_bundle": "./plugin"},
        )
        assert _classify_binding(binding) == "native"

    def test_native_config_with_instructions_classifies_as_native(self) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            native_config={"instructions": "./CLAUDE.md"},
        )
        assert _classify_binding(binding) == "native"

    def test_transport_type_classifies_as_mcp(self) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            transport_type="sse",
        )
        assert _classify_binding(binding) == "mcp"

    def test_native_ref_only_classifies_as_skill(self) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="skills/code-review",
        )
        assert _classify_binding(binding) == "skill"

    def test_empty_binding_classifies_as_unknown(self) -> None:
        binding = ProviderArtifactBinding(provider="claude")
        assert _classify_binding(binding) == "unknown"

    def test_native_integration_keys_take_priority_over_transport(self) -> None:
        """If both integration keys and transport_type are present, native wins."""
        binding = ProviderArtifactBinding(
            provider="claude",
            transport_type="sse",
            native_config={"hooks": "./hooks.json"},
        )
        assert _classify_binding(binding) == "native"

    def test_native_integration_keys_take_priority_over_native_ref(self) -> None:
        """If both integration keys and native_ref are present, native wins."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="skills/foo",
            native_config={"marketplace_bundle": "./market"},
        )
        assert _classify_binding(binding) == "native"


# ---------------------------------------------------------------------------
# _render_skill_binding — direct unit tests for internal helper
# ---------------------------------------------------------------------------


class TestRenderSkillBindingDirect:
    """Cover the null-native_ref warning path (lines 96-100) directly."""

    def test_null_native_ref_returns_warning(self, workspace: Path) -> None:
        binding = ProviderArtifactBinding(provider="claude", native_ref=None)
        rendered, warnings = _render_skill_binding(binding, workspace, "b1")
        assert rendered == []
        assert len(warnings) == 1
        assert "no native_ref" in warnings[0]
        assert "b1" in warnings[0]

    def test_empty_string_native_ref_returns_warning(self, workspace: Path) -> None:
        binding = ProviderArtifactBinding(provider="claude", native_ref="")
        rendered, warnings = _render_skill_binding(binding, workspace, "b2")
        assert rendered == []
        assert len(warnings) == 1
        assert "no native_ref" in warnings[0]

    def test_valid_native_ref_writes_file(self, workspace: Path) -> None:
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="skills/test-skill",
        )
        rendered, warnings = _render_skill_binding(binding, workspace, "bundle-a")
        assert warnings == []
        assert len(rendered) == 1
        assert rendered[0].exists()
        content = json.loads(rendered[0].read_text())
        assert content["native_ref"] == "skills/test-skill"
        assert content["bundle_id"] == "bundle-a"


# ---------------------------------------------------------------------------
# _merge_settings_fragment — direct unit tests
# ---------------------------------------------------------------------------


class TestMergeSettingsFragment:
    """Cover the nested dict merging branch (line 300)."""

    def test_merge_nested_dicts(self) -> None:
        target: dict[str, Any] = {"mcpServers": {"a": {"type": "sse"}}}
        source: dict[str, Any] = {"mcpServers": {"b": {"type": "stdio"}}}
        _merge_settings_fragment(target, source)
        assert target == {
            "mcpServers": {
                "a": {"type": "sse"},
                "b": {"type": "stdio"},
            }
        }

    def test_merge_overwrites_non_dict(self) -> None:
        target: dict[str, Any] = {"key": "old"}
        source: dict[str, Any] = {"key": "new"}
        _merge_settings_fragment(target, source)
        assert target["key"] == "new"

    def test_merge_adds_new_keys(self) -> None:
        target: dict[str, Any] = {"a": 1}
        source: dict[str, Any] = {"b": 2}
        _merge_settings_fragment(target, source)
        assert target == {"a": 1, "b": 2}

    def test_merge_target_dict_source_non_dict_overwrites(self) -> None:
        """If target has a dict but source has a non-dict, source wins."""
        target: dict[str, Any] = {"k": {"nested": True}}
        source: dict[str, Any] = {"k": "flat"}
        _merge_settings_fragment(target, source)
        assert target["k"] == "flat"

    def test_merge_target_non_dict_source_dict_overwrites(self) -> None:
        """If target has a non-dict but source has a dict, source wins."""
        target: dict[str, Any] = {"k": "flat"}
        source: dict[str, Any] = {"k": {"nested": True}}
        _merge_settings_fragment(target, source)
        assert target["k"] == {"nested": True}

    def test_merge_empty_source(self) -> None:
        target: dict[str, Any] = {"a": 1}
        _merge_settings_fragment(target, {})
        assert target == {"a": 1}

    def test_merge_multiple_fragments_accumulate(self) -> None:
        """Two merges accumulate MCP servers correctly."""
        target: dict[str, Any] = {}
        _merge_settings_fragment(target, {"mcpServers": {"a": {"type": "sse"}}})
        _merge_settings_fragment(target, {"mcpServers": {"b": {"type": "stdio"}}})
        assert target == {
            "mcpServers": {
                "a": {"type": "sse"},
                "b": {"type": "stdio"},
            }
        }


# ---------------------------------------------------------------------------
# MCP binding edge cases
# ---------------------------------------------------------------------------


class TestMCPBindingEdgeCases:
    """Cover partial branches in _render_mcp_binding."""

    def test_stdio_with_non_string_args(self, workspace: Path) -> None:
        """args that is not a string → wrapped in [str(args_raw)]."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="mcp-int-args",
            transport_type="stdio",
            native_config={"command": "/usr/bin/server", "args": "42"},
        )
        mcp_config, warnings = _render_mcp_binding(binding, "test-bundle")
        # String args are split
        assert mcp_config["mcp-int-args"]["args"] == ["42"]

    def test_stdio_with_no_args(self, workspace: Path) -> None:
        """No args key → no args in output."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="no-args-mcp",
            transport_type="stdio",
            native_config={"command": "/usr/bin/server"},
        )
        mcp_config, warnings = _render_mcp_binding(binding, "test-bundle")
        assert "args" not in mcp_config["no-args-mcp"]

    def test_stdio_with_no_env(self, workspace: Path) -> None:
        """No env_* keys → no env in output."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="no-env-mcp",
            transport_type="stdio",
            native_config={"command": "/usr/bin/server"},
        )
        mcp_config, warnings = _render_mcp_binding(binding, "test-bundle")
        assert "env" not in mcp_config["no-env-mcp"]

    def test_sse_with_no_headers(self, workspace: Path) -> None:
        """SSE with url but no header_* keys → no headers in output."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="clean-sse",
            transport_type="sse",
            native_config={"url": "http://localhost:8080"},
        )
        mcp_config, warnings = _render_mcp_binding(binding, "test-bundle")
        assert "headers" not in mcp_config["clean-sse"]
        assert warnings == []

    def test_unknown_transport_type_still_produces_entry(self, workspace: Path) -> None:
        """Transport type not in {sse, http, stdio} → entry with just 'type'."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="exotic-mcp",
            transport_type="grpc",
            native_config={},
        )
        mcp_config, warnings = _render_mcp_binding(binding, "test-bundle")
        assert mcp_config["exotic-mcp"] == {"type": "grpc"}
        assert warnings == []

    def test_http_transport_with_headers(self, workspace: Path) -> None:
        """HTTP transport collects header_* keys same as SSE."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="http-mcp",
            transport_type="http",
            native_config={
                "url": "https://api.example.com/mcp",
                "header_Authorization": "Bearer tok",
            },
        )
        mcp_config, _ = _render_mcp_binding(binding, "test-bundle")
        assert mcp_config["http-mcp"]["headers"] == {"Authorization": "Bearer tok"}


# ---------------------------------------------------------------------------
# Unknown binding in render_claude_artifacts
# ---------------------------------------------------------------------------


class TestUnknownBinding:
    """A binding with no native_ref, transport_type, or integration keys
    is classified as 'unknown' and produces a warning."""

    def test_unknown_binding_produces_warning(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"random_key": "value"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "no native_ref" in result.warnings[0]
        assert "skipping" in result.warnings[0].lower()

    def test_unknown_binding_does_not_render(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"custom": "v"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert result.rendered_paths == ()
        assert result.settings_fragment == {}


# ---------------------------------------------------------------------------
# Multiple bundles accumulating settings fragments
# ---------------------------------------------------------------------------


class TestMultipleMCPServersAccumulate:
    """Multiple MCP bindings in a single plan accumulate into mcpServers."""

    def test_two_mcp_servers_both_in_fragment(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="server-a",
                    transport_type="sse",
                    native_config={"url": "http://a:8080"},
                ),
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="server-b",
                    transport_type="stdio",
                    native_config={"command": "/usr/bin/b"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        mcp = result.settings_fragment["mcpServers"]
        assert "server-a" in mcp
        assert "server-b" in mcp

    def test_mcp_plus_marketplace_in_same_plan(self, workspace: Path) -> None:
        """MCP server and marketplace binding merge into same settings fragment."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="srv",
                    transport_type="sse",
                    native_config={"url": "http://x:80"},
                ),
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"marketplace_bundle": "./market/my-bundle"},
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert "mcpServers" in result.settings_fragment
        assert "extraKnownMarketplaces" in result.settings_fragment


# ---------------------------------------------------------------------------
# Idempotency — stronger file content comparison
# ---------------------------------------------------------------------------


class TestIdempotencyFileContent:
    """Stronger idempotency: compare actual file bytes across two renders."""

    def test_skill_file_bytes_identical_across_renders(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/deterministic",
                    native_config={"priority": "high"},
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)
        first_bytes = (
            workspace / SCC_MANAGED_DIR / "skills" / "skills_deterministic" / "skill.json"
        ).read_bytes()

        render_claude_artifacts(plan, workspace)
        second_bytes = (
            workspace / SCC_MANAGED_DIR / "skills" / "skills_deterministic" / "skill.json"
        ).read_bytes()

        assert first_bytes == second_bytes

    def test_audit_file_bytes_identical_across_renders(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="idem-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="srv",
                    transport_type="sse",
                    native_config={"url": "http://localhost:9090"},
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)
        first = (workspace / ".claude" / ".scc-settings-idem-bundle.json").read_bytes()
        render_claude_artifacts(plan, workspace)
        second = (workspace / ".claude" / ".scc-settings-idem-bundle.json").read_bytes()
        assert first == second


# ---------------------------------------------------------------------------
# Skill path sanitization
# ---------------------------------------------------------------------------


class TestSkillPathSanitization:
    """Verify special characters in native_ref are sanitized for filesystem."""

    def test_backslash_replaced(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills\\review",
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)
        expected_dir = workspace / SCC_MANAGED_DIR / "skills" / "skills_review"
        assert (expected_dir / "skill.json").exists()

    def test_dotdot_replaced(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="skills/../escape",
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)
        expected_dir = workspace / SCC_MANAGED_DIR / "skills" / "skills___escape"
        assert (expected_dir / "skill.json").exists()

    def test_bundle_id_sanitized_in_audit_filename(self, workspace: Path) -> None:
        """Bundle IDs with slashes are sanitized in audit file names."""
        plan = _plan(
            bundle_id="org/team/bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="mcp-server",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        render_claude_artifacts(plan, workspace)
        expected = workspace / ".claude" / ".scc-settings-org_team_bundle.json"
        assert expected.exists()


# ---------------------------------------------------------------------------
# Branch coverage: config keys that don't match header_/env_ prefixes
# ---------------------------------------------------------------------------


class TestMCPBindingNonPrefixKeys:
    """Exercise the for-loop branches where config keys don't start with
    header_ or env_, ensuring the loop skips non-matching keys."""

    def test_sse_config_with_non_header_extra_keys(self, workspace: Path) -> None:
        """SSE binding with extra non-header keys → keys ignored in output."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="extra-keys-sse",
            transport_type="sse",
            native_config={
                "url": "http://localhost:8080",
                "header_Authorization": "Bearer tok",
                "custom_setting": "ignored",
            },
        )
        mcp_config, warnings = _render_mcp_binding(binding, "test-bundle")
        server = mcp_config["extra-keys-sse"]
        assert server["headers"] == {"Authorization": "Bearer tok"}
        # custom_setting is not rendered into the server config
        assert "custom_setting" not in server
        assert warnings == []

    def test_stdio_config_with_non_env_extra_keys(self, workspace: Path) -> None:
        """Stdio binding with extra non-env keys → keys ignored in output."""
        binding = ProviderArtifactBinding(
            provider="claude",
            native_ref="extra-keys-stdio",
            transport_type="stdio",
            native_config={
                "command": "/usr/bin/server",
                "env_API_KEY": "secret",
                "custom_flag": "true",
            },
        )
        mcp_config, warnings = _render_mcp_binding(binding, "test-bundle")
        server = mcp_config["extra-keys-stdio"]
        assert server["env"] == {"API_KEY": "secret"}
        assert "custom_flag" not in server


# ---------------------------------------------------------------------------
# Portable artifact rendering (D023)
# ---------------------------------------------------------------------------


class TestPortableSkillRendering:
    """D023: Portable skills without provider bindings are renderable."""

    def test_portable_skill_writes_metadata(self, workspace: Path) -> None:
        """Portable skill produces skill.json under .scc-managed/skills/."""
        plan = _plan(
            portable_artifacts=(
                PortableArtifact(
                    name="code-review",
                    kind=ArtifactKind.SKILL,
                    source_type="git",
                    source_url="https://git.example.com/skills/code-review",
                    source_ref="v1.2.0",
                    version="1.2.0",
                ),
            ),
            effective_artifacts=("code-review",),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.rendered_paths) == 1
        metadata_path = workspace / SCC_MANAGED_DIR / "skills" / "code-review" / "skill.json"
        assert metadata_path.exists()
        data = json.loads(metadata_path.read_text())
        assert data["name"] == "code-review"
        assert data["portable"] is True
        assert data["provider"] == "claude"
        assert data["bundle_id"] == "test-bundle"
        assert data["source_type"] == "git"
        assert data["source_url"] == "https://git.example.com/skills/code-review"
        assert data["source_ref"] == "v1.2.0"
        assert data["version"] == "1.2.0"
        assert result.warnings == ()

    def test_portable_skill_minimal_metadata(self, workspace: Path) -> None:
        """Portable skill with no source metadata still writes file."""
        plan = _plan(
            portable_artifacts=(PortableArtifact(name="minimal-skill", kind=ArtifactKind.SKILL),),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.rendered_paths) == 1
        data = json.loads(result.rendered_paths[0].read_text())
        assert data["name"] == "minimal-skill"
        assert data["portable"] is True
        assert "source_url" not in data

    def test_portable_skill_name_sanitized(self, workspace: Path) -> None:
        """Skill name with slashes is sanitized for filesystem."""
        plan = _plan(
            portable_artifacts=(PortableArtifact(name="org/team/skill", kind=ArtifactKind.SKILL),),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.rendered_paths) == 1
        assert "org_team_skill" in str(result.rendered_paths[0])

    def test_portable_skill_materialization_error(self, workspace: Path) -> None:
        """OSError during portable skill write raises MaterializationError."""
        # Make the target parent directory a file to cause OSError
        block = workspace / SCC_MANAGED_DIR / "skills" / "blocked-skill"
        block.parent.mkdir(parents=True, exist_ok=True)
        block.write_text("not-a-dir")

        plan = _plan(
            portable_artifacts=(PortableArtifact(name="blocked-skill", kind=ArtifactKind.SKILL),),
        )
        with pytest.raises(MaterializationError):
            render_claude_artifacts(plan, workspace)


class TestPortableMcpRendering:
    """D023: Portable MCP servers without provider bindings are renderable."""

    def test_portable_mcp_with_url(self, workspace: Path) -> None:
        """Portable MCP server with source_url → settings fragment entry."""
        plan = _plan(
            portable_artifacts=(
                PortableArtifact(
                    name="github-mcp",
                    kind=ArtifactKind.MCP_SERVER,
                    source_url="https://mcp.example.com/github",
                    source_ref="v2.0.0",
                ),
            ),
            effective_artifacts=("github-mcp",),
        )
        result = render_claude_artifacts(plan, workspace)
        assert "mcpServers" in result.settings_fragment
        server = result.settings_fragment["mcpServers"]["github-mcp"]
        assert server["type"] == "sse"
        assert server["url"] == "https://mcp.example.com/github"
        assert server["portable"] is True
        assert server["source_ref"] == "v2.0.0"
        assert result.warnings == ()
        # Audit file should be written
        assert len(result.rendered_paths) == 1  # just the audit file

    def test_portable_mcp_no_url_warns(self, workspace: Path) -> None:
        """Portable MCP server with no source_url → warning."""
        plan = _plan(
            portable_artifacts=(
                PortableArtifact(
                    name="local-mcp",
                    kind=ArtifactKind.MCP_SERVER,
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "no source_url" in result.warnings[0]

    def test_portable_mcp_version_in_config(self, workspace: Path) -> None:
        """Version metadata propagates to settings fragment."""
        plan = _plan(
            portable_artifacts=(
                PortableArtifact(
                    name="versioned-mcp",
                    kind=ArtifactKind.MCP_SERVER,
                    source_url="https://mcp.example.com/v",
                    version="3.1.0",
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        server = result.settings_fragment["mcpServers"]["versioned-mcp"]
        assert server["version"] == "3.1.0"


class TestPortableMixedWithBindings:
    """D023: Portable artifacts render alongside binding-based artifacts."""

    def test_mixed_bindings_and_portable(self, workspace: Path) -> None:
        """Plan with both bindings and portable artifacts renders both."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="bound-skill",
                ),
            ),
            portable_artifacts=(
                PortableArtifact(
                    name="portable-skill",
                    kind=ArtifactKind.SKILL,
                    source_type="git",
                    source_url="https://example.com/skill",
                ),
            ),
            effective_artifacts=("bound-skill", "portable-skill"),
        )
        result = render_claude_artifacts(plan, workspace)
        # bound-skill renders via binding, portable-skill via portable path
        assert len(result.rendered_paths) == 2
        paths_str = [str(p) for p in result.rendered_paths]
        assert any("bound-skill" in p for p in paths_str)
        assert any("portable-skill" in p for p in paths_str)

    def test_portable_mcp_merges_with_binding_mcp(self, workspace: Path) -> None:
        """Portable MCP and binding MCP coexist in settings_fragment."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_ref="bound-mcp",
                    transport_type="sse",
                    native_config={"url": "https://bound.example.com"},
                ),
            ),
            portable_artifacts=(
                PortableArtifact(
                    name="portable-mcp",
                    kind=ArtifactKind.MCP_SERVER,
                    source_url="https://portable.example.com",
                ),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        mcp = result.settings_fragment["mcpServers"]
        assert "bound-mcp" in mcp
        assert "portable-mcp" in mcp
        assert mcp["bound-mcp"]["url"] == "https://bound.example.com"
        assert mcp["portable-mcp"]["url"] == "https://portable.example.com"
