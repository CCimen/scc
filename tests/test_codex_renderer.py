"""Characterization tests for the Codex renderer.

Verifies that render_codex_artifacts() produces expected file structures
and MCP fragments from known ArtifactRenderPlans.

Covers:
- Empty plan → empty result
- Skill binding → skill metadata file under .agents/skills/
- MCP server binding (SSE/HTTP/stdio) → mcpServers MCP fragment
- Native integration binding (plugin_bundle, rules, hooks, instructions)
- Mixed bundle with multiple binding types
- Plan targeting wrong provider → skip with warning
- Non-codex binding in plan → skip with warning
- Empty native_ref on skill → warning
- Missing URL on MCP SSE → warning
- Missing command on MCP stdio → warning
- MCP audit file written for non-empty fragments
- Hooks merge strategy (existing file preserved)
- Deterministic/idempotent rendering (same plan → same output)
- Return type shape
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scc_cli.adapters.codex_renderer import (
    CODEX_CONFIG_DIR,
    CODEX_PLUGIN_DIR,
    CODEX_RULES_DIR,
    INSTRUCTIONS_SUBDIR,
    SCC_MANAGED_DIR,
    SCC_SECTION_END,
    SCC_SECTION_START,
    SKILLS_DIR,
    RendererResult,
    _classify_binding,
    _render_mcp_binding,
    _render_native_integration_binding,
    _render_skill_binding,
    render_codex_artifacts,
)
from scc_cli.core.errors import MaterializationError, MergeConflictError
from scc_cli.core.governed_artifacts import (
    ArtifactRenderPlan,
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
    provider: str = "codex",
    bindings: tuple[ProviderArtifactBinding, ...] = (),
    skipped: tuple[str, ...] = (),
    effective_artifacts: tuple[str, ...] = (),
) -> ArtifactRenderPlan:
    return ArtifactRenderPlan(
        bundle_id=bundle_id,
        provider=provider,
        bindings=bindings,
        skipped=skipped,
        effective_artifacts=effective_artifacts,
    )


# ---------------------------------------------------------------------------
# Empty / trivial
# ---------------------------------------------------------------------------


class TestEmptyPlan:
    def test_empty_plan_produces_empty_result(self, workspace: Path) -> None:
        result = render_codex_artifacts(_plan(), workspace)
        assert isinstance(result, RendererResult)
        assert result.rendered_paths == ()
        assert result.skipped_artifacts == ()
        assert result.warnings == ()
        assert result.mcp_fragment == {}

    def test_empty_bindings_with_skipped(self, workspace: Path) -> None:
        plan = _plan(skipped=("ghost-artifact",))
        result = render_codex_artifacts(plan, workspace)
        assert result.skipped_artifacts == ("ghost-artifact",)
        assert result.rendered_paths == ()


# ---------------------------------------------------------------------------
# Wrong provider
# ---------------------------------------------------------------------------


class TestWrongProvider:
    def test_non_codex_provider_produces_warning(self, workspace: Path) -> None:
        plan = _plan(provider="claude", effective_artifacts=("some-skill",))
        result = render_codex_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "claude" in result.warnings[0]
        assert "nothing rendered" in result.warnings[0]
        assert result.skipped_artifacts == ("some-skill",)

    def test_non_codex_binding_in_codex_plan(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(provider="claude", native_ref="skills/foo"),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "claude" in result.warnings[0]


# ---------------------------------------------------------------------------
# Skill binding
# ---------------------------------------------------------------------------


class TestSkillBinding:
    def test_skill_creates_metadata_file(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/code-review",
                ),
            ),
            effective_artifacts=("code-review-skill",),
        )
        result = render_codex_artifacts(plan, workspace)

        assert result.warnings == ()
        assert len(result.rendered_paths) >= 1

        # Check the skill metadata file exists under .agents/skills/
        skill_dir = workspace / SKILLS_DIR / "skills_code-review"
        metadata_path = skill_dir / "skill.json"
        assert metadata_path.exists()

        content = json.loads(metadata_path.read_text())
        assert content["native_ref"] == "skills/code-review"
        assert content["provider"] == "codex"
        assert content["bundle_id"] == "test-bundle"
        assert content["managed_by"] == "scc"

    def test_skill_with_native_config(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/review",
                    native_config={"priority": "high"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        skill_dir = workspace / SKILLS_DIR / "skills_review"
        content = json.loads((skill_dir / "skill.json").read_text())
        assert content["native_config"] == {"priority": "high"}

    def test_skill_no_native_ref_produces_warning(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(provider="codex"),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        assert len(result.warnings) >= 1
        assert any(
            "no native_ref" in w or "no recognised" in w.lower()
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
                    provider="codex",
                    native_ref="github-mcp",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080/sse"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        assert "mcpServers" in result.mcp_fragment
        mcp = result.mcp_fragment["mcpServers"]
        assert "github-mcp" in mcp
        assert mcp["github-mcp"]["type"] == "sse"
        assert mcp["github-mcp"]["url"] == "http://localhost:8080/sse"

    def test_http_mcp_server(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="my-server",
                    transport_type="http",
                    native_config={"url": "https://api.example.com/mcp"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        mcp = result.mcp_fragment["mcpServers"]
        assert mcp["my-server"]["type"] == "http"
        assert mcp["my-server"]["url"] == "https://api.example.com/mcp"

    def test_stdio_mcp_server(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
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
        result = render_codex_artifacts(plan, workspace)

        mcp = result.mcp_fragment["mcpServers"]
        assert "local-mcp" in mcp
        assert mcp["local-mcp"]["type"] == "stdio"
        assert mcp["local-mcp"]["command"] == "/usr/bin/my-mcp-server"
        assert mcp["local-mcp"]["args"] == ["--port", "9090", "--verbose"]
        assert mcp["local-mcp"]["env"] == {"API_KEY": "placeholder"}

    def test_sse_mcp_with_headers(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
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
        result = render_codex_artifacts(plan, workspace)

        mcp = result.mcp_fragment["mcpServers"]
        assert mcp["authed-mcp"]["headers"] == {
            "Authorization": "Bearer tok",
            "X-Org": "my-org",
        }

    def test_mcp_no_url_produces_warning(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="broken-mcp",
                    transport_type="sse",
                    native_config={},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        assert any("no 'url'" in w for w in result.warnings)

    def test_mcp_no_command_produces_warning(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="broken-stdio",
                    transport_type="stdio",
                    native_config={},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        assert any("no 'command'" in w for w in result.warnings)

    def test_mcp_fallback_name_when_no_native_ref(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="my-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    transport_type="sse",
                    native_config={"url": "http://localhost:9090"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        mcp = result.mcp_fragment["mcpServers"]
        assert "scc-my-bundle-mcp" in mcp


# ---------------------------------------------------------------------------
# Native integration binding
# ---------------------------------------------------------------------------


class TestNativeIntegrationBinding:
    def test_plugin_bundle_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"plugin_bundle": "./codex/github-plugin"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        plugin_path = workspace / CODEX_PLUGIN_DIR / "plugin.json"
        assert plugin_path.exists()
        content = json.loads(plugin_path.read_text())
        assert content["source"] == "./codex/github-plugin"
        assert content["provider"] == "codex"
        assert content["bundle_id"] == "test-bundle"
        assert content["managed_by"] == "scc"
        assert plugin_path in result.rendered_paths

    def test_rules_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"rules": "./codex/rules/github.rules"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        rules_path = workspace / CODEX_RULES_DIR / "github.rules.json"
        assert rules_path.exists()
        content = json.loads(rules_path.read_text())
        assert content["source"] == "./codex/rules/github.rules"
        assert content["bundle_id"] == "test-bundle"
        assert content["managed_by"] == "scc"
        assert rules_path in result.rendered_paths

    def test_hooks_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./codex/github-hooks.json"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        hooks_path = workspace / CODEX_CONFIG_DIR / "hooks.json"
        assert hooks_path.exists()
        content = json.loads(hooks_path.read_text())
        assert "scc_managed" in content
        assert "test-bundle" in content["scc_managed"]
        assert content["scc_managed"]["test-bundle"]["source"] == "./codex/github-hooks.json"
        assert content["scc_managed"]["test-bundle"]["managed_by"] == "scc"
        assert hooks_path in result.rendered_paths

    def test_hooks_merge_preserves_existing(self, workspace: Path) -> None:
        """Existing non-SCC content in hooks.json should be preserved."""
        codex_dir = workspace / CODEX_CONFIG_DIR
        codex_dir.mkdir(parents=True, exist_ok=True)
        hooks_path = codex_dir / "hooks.json"
        existing = {"user_hook": {"command": "lint", "event": "pre-commit"}}
        hooks_path.write_text(json.dumps(existing, indent=2) + "\n")

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./codex/hooks-src.json"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        content = json.loads(hooks_path.read_text())
        # User hook preserved
        assert content["user_hook"]["command"] == "lint"
        # SCC-managed section added
        assert "scc_managed" in content
        assert "test-bundle" in content["scc_managed"]

    def test_hooks_merge_corrupted_file_overwrites(self, workspace: Path) -> None:
        """Corrupted hooks.json should be overwritten with warning."""
        codex_dir = workspace / CODEX_CONFIG_DIR
        codex_dir.mkdir(parents=True, exist_ok=True)
        hooks_path = codex_dir / "hooks.json"
        hooks_path.write_text("not-valid-json!!!")

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./codex/hooks-src.json"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        assert any("Could not parse" in w for w in result.warnings)
        content = json.loads(hooks_path.read_text())
        assert "scc_managed" in content

    def test_instructions_binding(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"instructions": "./codex/AGENTS.team.md"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        instr_path = workspace / SCC_MANAGED_DIR / "instructions" / "AGENTS.team.json"
        assert instr_path.exists()
        content = json.loads(instr_path.read_text())
        assert content["source"] == "./codex/AGENTS.team.md"
        assert content["provider"] == "codex"
        assert content["managed_by"] == "scc"
        assert instr_path in result.rendered_paths

    def test_combined_native_integration(self, workspace: Path) -> None:
        """A single binding with plugin_bundle + rules + hooks + instructions."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={
                        "plugin_bundle": "./codex/github-plugin",
                        "rules": "./codex/rules/github.rules",
                        "hooks": "./codex/hooks-src.json",
                        "instructions": "./codex/AGENTS.team.md",
                    },
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        # Plugin file
        assert (workspace / CODEX_PLUGIN_DIR / "plugin.json").exists()
        # Rules file
        assert (workspace / CODEX_RULES_DIR / "github.rules.json").exists()
        # Hooks file
        assert (workspace / CODEX_CONFIG_DIR / "hooks.json").exists()
        # Instructions file
        assert (workspace / SCC_MANAGED_DIR / "instructions" / "AGENTS.team.json").exists()
        # No warnings expected
        assert result.warnings == ()


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
                    provider="codex",
                    native_ref="skills/code-review",
                ),
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="github-mcp",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={
                        "plugin_bundle": "./codex/github-plugin",
                        "rules": "./codex/rules/github.rules",
                    },
                ),
            ),
            effective_artifacts=("code-review-skill", "github-mcp", "github-native"),
        )
        result = render_codex_artifacts(plan, workspace)

        # Skill file under .agents/skills/
        skill_path = (
            workspace / SKILLS_DIR / "skills_code-review" / "skill.json"
        )
        assert skill_path.exists()

        # MCP server in fragment
        assert "github-mcp" in result.mcp_fragment.get("mcpServers", {})

        # Plugin + rules
        assert (workspace / CODEX_PLUGIN_DIR / "plugin.json").exists()
        assert (workspace / CODEX_RULES_DIR / "github.rules.json").exists()

        # Audit file written
        audit_file = workspace / CODEX_CONFIG_DIR / ".scc-mcp-github-dev.json"
        assert audit_file.exists()
        audit_content = json.loads(audit_file.read_text())
        assert "mcpServers" in audit_content

        # No warnings
        assert result.warnings == ()


# ---------------------------------------------------------------------------
# MCP audit file
# ---------------------------------------------------------------------------


class TestMCPAuditFile:
    def test_audit_file_written_when_fragment_nonempty(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="my-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="server",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        audit_path = workspace / CODEX_CONFIG_DIR / ".scc-mcp-my-bundle.json"
        assert audit_path.exists()
        assert audit_path in result.rendered_paths

    def test_no_audit_file_for_empty_fragment(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="empty-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/foo",
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        audit_path = workspace / CODEX_CONFIG_DIR / ".scc-mcp-empty-bundle.json"
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
                    provider="codex",
                    native_ref="skills/review",
                ),
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="mcp-server",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"rules": "./codex/rules/test.rules"},
                ),
            ),
        )
        result1 = render_codex_artifacts(plan, workspace)
        result2 = render_codex_artifacts(plan, workspace)

        assert result1.mcp_fragment == result2.mcp_fragment
        assert len(result1.rendered_paths) == len(result2.rendered_paths)
        assert result1.warnings == result2.warnings

        # File contents are the same
        for path in result1.rendered_paths:
            assert path.exists()

    def test_overwrite_on_rerender(self, workspace: Path) -> None:
        """Second render overwrites first — no duplicate files."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/my-skill",
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)
        result2 = render_codex_artifacts(plan, workspace)

        # Only one skill dir exists
        skill_parent = workspace / SKILLS_DIR
        assert len(list(skill_parent.iterdir())) == 1
        assert len(result2.rendered_paths) == 1


# ---------------------------------------------------------------------------
# Return type shape
# ---------------------------------------------------------------------------


class TestReturnType:
    def test_result_is_renderer_result(self, workspace: Path) -> None:
        result = render_codex_artifacts(_plan(), workspace)
        assert isinstance(result, RendererResult)

    def test_rendered_paths_are_path_objects(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/x",
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        for p in result.rendered_paths:
            assert isinstance(p, Path)

    def test_mcp_fragment_is_dict(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="mcp-srv",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        assert isinstance(result.mcp_fragment, dict)
        assert "mcpServers" in result.mcp_fragment


# ---------------------------------------------------------------------------
# Failure path tests — fail-closed semantics
# ---------------------------------------------------------------------------


class TestSkillMaterializationFailure:
    def test_read_only_workspace_raises_materialization_error(
        self, workspace: Path
    ) -> None:
        """Skill write to read-only dir raises MaterializationError."""
        skills = workspace / SKILLS_DIR
        skills.mkdir(parents=True, exist_ok=True)
        skills.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/blocked",
                ),
            ),
        )
        with pytest.raises(MaterializationError) as exc_info:
            render_codex_artifacts(plan, workspace)
        err = exc_info.value
        assert err.bundle_id == "test-bundle"
        assert "skills/blocked" in err.artifact_name

        skills.chmod(0o755)


class TestPluginCreationFailure:
    def test_plugin_write_failure_raises_materialization_error(
        self, workspace: Path
    ) -> None:
        """Plugin file write to read-only dir → MaterializationError."""
        plugin_dir = workspace / CODEX_PLUGIN_DIR
        plugin_dir.mkdir(parents=True, exist_ok=True)
        plugin_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"plugin_bundle": "./codex/plugin-src"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="plugin"):
            render_codex_artifacts(plan, workspace)

        plugin_dir.chmod(0o755)


class TestRulesWriteFailure:
    def test_rules_write_failure_raises_materialization_error(
        self, workspace: Path
    ) -> None:
        """Rules file write to read-only dir → MaterializationError."""
        rules_dir = workspace / CODEX_RULES_DIR
        rules_dir.mkdir(parents=True, exist_ok=True)
        rules_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"rules": "./codex/rules/safety.rules"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="rules"):
            render_codex_artifacts(plan, workspace)

        rules_dir.chmod(0o755)


class TestHooksWriteFailure:
    def test_hooks_write_failure_raises_materialization_error(
        self, workspace: Path
    ) -> None:
        """hooks.json write to read-only dir → MaterializationError."""
        codex_dir = workspace / CODEX_CONFIG_DIR
        codex_dir.mkdir(parents=True, exist_ok=True)
        codex_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./codex/hooks-src.json"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="hooks"):
            render_codex_artifacts(plan, workspace)

        codex_dir.chmod(0o755)

    def test_hooks_read_os_error_raises_materialization_error(
        self, workspace: Path
    ) -> None:
        """OSError reading existing hooks.json → MaterializationError (not warning)."""
        codex_dir = workspace / CODEX_CONFIG_DIR
        codex_dir.mkdir(parents=True, exist_ok=True)
        hooks_path = codex_dir / "hooks.json"
        # Create hooks.json as a directory to cause an OSError on read
        hooks_path.mkdir()

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./codex/hooks-src.json"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="hooks"):
            render_codex_artifacts(plan, workspace)

        hooks_path.rmdir()


class TestInstructionsWriteFailure:
    def test_instructions_write_failure_raises_materialization_error(
        self, workspace: Path
    ) -> None:
        """instructions write to read-only dir → MaterializationError."""
        instr_dir = workspace / SCC_MANAGED_DIR / "instructions"
        instr_dir.mkdir(parents=True, exist_ok=True)
        instr_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"instructions": "./codex/AGENTS.md"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="instructions"):
            render_codex_artifacts(plan, workspace)

        instr_dir.chmod(0o755)


class TestMCPAuditWriteFailure:
    def test_mcp_audit_file_write_failure_raises_materialization_error(
        self, workspace: Path
    ) -> None:
        """MCP audit file write to read-only .codex/ → MaterializationError."""
        codex_dir = workspace / CODEX_CONFIG_DIR
        codex_dir.mkdir(parents=True, exist_ok=True)
        codex_dir.chmod(0o444)

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="mcp-server",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        with pytest.raises(MaterializationError, match="mcp_fragment"):
            render_codex_artifacts(plan, workspace)

        codex_dir.chmod(0o755)


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
# Internal helper: _render_skill_binding — direct coverage
# ---------------------------------------------------------------------------


class TestRenderSkillBindingDirect:
    """Test _render_skill_binding directly to reach code paths unreachable
    through the public API (the classifier routes bindings with no native_ref
    to 'unknown', never calling _render_skill_binding)."""

    def test_null_native_ref_returns_warning(self, workspace: Path) -> None:
        """Lines 113-117: early return with warning when native_ref is None."""
        binding = ProviderArtifactBinding(provider="codex", native_ref=None)
        rendered, warnings = _render_skill_binding(binding, workspace, "b1")
        assert rendered == []
        assert len(warnings) == 1
        assert "no native_ref" in warnings[0]
        assert "b1" in warnings[0]

    def test_empty_string_native_ref_returns_warning(self, workspace: Path) -> None:
        """Empty string is also falsy — same early return."""
        binding = ProviderArtifactBinding(provider="codex", native_ref="")
        rendered, warnings = _render_skill_binding(binding, workspace, "b2")
        assert rendered == []
        assert len(warnings) == 1

    def test_normal_ref_creates_file(self, workspace: Path) -> None:
        """Sanity: valid ref through the helper produces a metadata file."""
        binding = ProviderArtifactBinding(
            provider="codex", native_ref="skills/test"
        )
        rendered, warnings = _render_skill_binding(binding, workspace, "b3")
        assert len(rendered) == 1
        assert rendered[0].name == "skill.json"
        assert warnings == []

    def test_path_sanitisation_dotdot(self, workspace: Path) -> None:
        """Path traversal chars replaced in skill directory name."""
        binding = ProviderArtifactBinding(
            provider="codex", native_ref="../../etc/passwd"
        )
        rendered, warnings = _render_skill_binding(binding, workspace, "b4")
        assert len(rendered) == 1
        # '..' replaced with '_', '/' replaced with '_'
        dir_name = rendered[0].parent.name
        assert ".." not in dir_name
        assert "/" not in dir_name

    def test_path_sanitisation_backslash(self, workspace: Path) -> None:
        """Backslash in native_ref is sanitised."""
        binding = ProviderArtifactBinding(
            provider="codex", native_ref="skills\\code-review"
        )
        rendered, warnings = _render_skill_binding(binding, workspace, "b5")
        assert len(rendered) == 1
        dir_name = rendered[0].parent.name
        assert "\\" not in dir_name


# ---------------------------------------------------------------------------
# Internal helper: _render_mcp_binding — edge cases
# ---------------------------------------------------------------------------


class TestRenderMCPBindingDirect:
    """Test _render_mcp_binding directly for branch-closing coverage."""

    def test_sse_with_url_no_headers(self, workspace: Path) -> None:
        """SSE transport with url but zero header_* keys → no 'headers' key
        in output.  Closes the partial branch at line 181→180."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="clean-mcp",
            transport_type="sse",
            native_config={"url": "http://localhost:9090"},
        )
        config, warnings = _render_mcp_binding(binding, "b1")
        assert warnings == []
        server = config["clean-mcp"]
        assert "headers" not in server
        assert server["url"] == "http://localhost:9090"

    def test_http_with_url_no_headers(self, workspace: Path) -> None:
        """HTTP transport with url but zero header_* keys."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="http-mcp",
            transport_type="http",
            native_config={"url": "https://api.example.com"},
        )
        config, warnings = _render_mcp_binding(binding, "b2")
        assert warnings == []
        assert "headers" not in config["http-mcp"]

    def test_unknown_transport_type(self, workspace: Path) -> None:
        """Transport type not sse/http/stdio → no command/url/args parsed.
        Closes the partial branch at line 186→208."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="exotic-mcp",
            transport_type="grpc",
            native_config={"endpoint": "localhost:50051"},
        )
        config, warnings = _render_mcp_binding(binding, "b3")
        assert warnings == []
        server = config["exotic-mcp"]
        assert server["type"] == "grpc"
        # No url/command/args parsing for unknown transport
        assert "url" not in server
        assert "command" not in server

    def test_stdio_with_command_no_env_keys(self, workspace: Path) -> None:
        """stdio transport with command but no env_* keys → no 'env' key.
        Closes the partial branch at line 203→202."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="simple-stdio",
            transport_type="stdio",
            native_config={"command": "/usr/bin/server"},
        )
        config, warnings = _render_mcp_binding(binding, "b4")
        assert warnings == []
        server = config["simple-stdio"]
        assert server["command"] == "/usr/bin/server"
        assert "env" not in server
        assert "args" not in server

    def test_stdio_with_non_string_args(self, workspace: Path) -> None:
        """Non-string args value → goes through [str(args_raw)] branch."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="int-args-mcp",
            transport_type="stdio",
            native_config={"command": "/usr/bin/srv", "args": 42},  # type: ignore[dict-item]
        )
        config, warnings = _render_mcp_binding(binding, "b5")
        server = config["int-args-mcp"]
        assert server["args"] == ["42"]

    def test_stdio_no_args_key(self, workspace: Path) -> None:
        """No 'args' key in config → args_raw is None, no 'args' in output."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="no-args-mcp",
            transport_type="stdio",
            native_config={"command": "/bin/tool"},
        )
        config, warnings = _render_mcp_binding(binding, "b6")
        assert "args" not in config["no-args-mcp"]

    def test_multiple_env_keys_collected(self, workspace: Path) -> None:
        """Multiple env_* keys are all collected into env dict."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="multi-env",
            transport_type="stdio",
            native_config={
                "command": "/bin/tool",
                "env_FOO": "bar",
                "env_BAZ": "qux",
            },
        )
        config, warnings = _render_mcp_binding(binding, "b7")
        server = config["multi-env"]
        assert server["env"] == {"FOO": "bar", "BAZ": "qux"}

    def test_sse_with_extra_non_header_keys_no_headers(self, workspace: Path) -> None:
        """SSE with leftover config keys (not header_*) → loop body for
        header collection executes but no keys match.
        Closes partial branch 181→180."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="extra-mcp",
            transport_type="sse",
            native_config={"url": "http://localhost", "custom_key": "val"},
        )
        config, warnings = _render_mcp_binding(binding, "b8")
        server = config["extra-mcp"]
        assert "headers" not in server
        assert server["url"] == "http://localhost"

    def test_stdio_with_extra_non_env_keys_no_env(self, workspace: Path) -> None:
        """stdio with leftover config keys (not env_*) → loop body for
        env collection executes but no keys match.
        Closes partial branch 203→202."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="extra-stdio",
            transport_type="stdio",
            native_config={"command": "/bin/tool", "custom_key": "val"},
        )
        config, warnings = _render_mcp_binding(binding, "b9")
        server = config["extra-stdio"]
        assert "env" not in server
        assert server["command"] == "/bin/tool"


# ---------------------------------------------------------------------------
# Internal helper: _classify_binding — unit tests
# ---------------------------------------------------------------------------


class TestClassifyBinding:
    """Unit tests for _classify_binding to verify classification dispatch."""

    def test_native_integration_keys_wins(self) -> None:
        """Binding with integration keys in native_config → 'native'."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="something",
            transport_type="sse",
            native_config={"plugin_bundle": "./plugin"},
        )
        assert _classify_binding(binding) == "native"

    def test_transport_type_without_integration_keys(self) -> None:
        """Binding with transport_type but no integration keys → 'mcp'."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="server",
            transport_type="stdio",
            native_config={"command": "/bin/x"},
        )
        assert _classify_binding(binding) == "mcp"

    def test_native_ref_only(self) -> None:
        """Binding with native_ref only → 'skill'."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_ref="skills/my-skill",
        )
        assert _classify_binding(binding) == "skill"

    def test_empty_binding(self) -> None:
        """Binding with nothing → 'unknown'."""
        binding = ProviderArtifactBinding(provider="codex")
        assert _classify_binding(binding) == "unknown"

    def test_rules_key_classifies_as_native(self) -> None:
        """The 'rules' key in native_config → 'native'."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_config={"rules": "./rules/safety.rules"},
        )
        assert _classify_binding(binding) == "native"

    def test_hooks_key_classifies_as_native(self) -> None:
        """The 'hooks' key → 'native'."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_config={"hooks": "./hooks.json"},
        )
        assert _classify_binding(binding) == "native"

    def test_instructions_key_classifies_as_native(self) -> None:
        """The 'instructions' key → 'native'."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_config={"instructions": "./AGENTS.md"},
        )
        assert _classify_binding(binding) == "native"

    def test_unknown_config_keys_with_transport_still_mcp(self) -> None:
        """Non-integration config keys + transport_type → 'mcp', not 'native'."""
        binding = ProviderArtifactBinding(
            provider="codex",
            transport_type="sse",
            native_config={"url": "http://localhost:8080", "custom": "val"},
        )
        assert _classify_binding(binding) == "mcp"

    def test_integration_key_trumps_transport(self) -> None:
        """Integration key present + transport_type set → 'native' wins."""
        binding = ProviderArtifactBinding(
            provider="codex",
            transport_type="sse",
            native_config={"hooks": "./hooks.json", "url": "http://localhost"},
        )
        assert _classify_binding(binding) == "native"


# ---------------------------------------------------------------------------
# Asymmetry: Claude-only native_integration → skipped for Codex
# ---------------------------------------------------------------------------


class TestProviderAsymmetry:
    """Plan item 7: bundle with Claude-only native_integration → skipped
    for Codex with clear reason."""

    def test_claude_only_binding_skipped_in_codex_plan(self, workspace: Path) -> None:
        """A binding with provider='claude' in a Codex plan is skipped."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"plugin_bundle": "./claude/plugin"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "claude" in result.warnings[0]
        assert "skipping" in result.warnings[0].lower()
        assert result.rendered_paths == ()

    def test_mixed_claude_and_codex_bindings(self, workspace: Path) -> None:
        """Claude bindings are skipped; Codex bindings are rendered."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="claude",
                    native_config={"plugin_bundle": "./claude/plugin"},
                ),
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/code-review",
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        # Claude binding skipped with warning
        assert any("claude" in w for w in result.warnings)
        # Codex binding rendered
        assert len(result.rendered_paths) == 1
        assert "skill.json" in str(result.rendered_paths[0])

    def test_arbitrary_provider_binding_skipped(self, workspace: Path) -> None:
        """Any non-codex provider binding is skipped, not just 'claude'."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="gemini",
                    native_ref="skills/gemini-skill",
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        assert len(result.warnings) == 1
        assert "gemini" in result.warnings[0]

    def test_codex_plan_wrong_provider_skips_all(self, workspace: Path) -> None:
        """Plan with provider='claude' → everything skipped, no rendering."""
        plan = _plan(
            provider="claude",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/foo",
                ),
            ),
            effective_artifacts=("foo-skill",),
        )
        result = render_codex_artifacts(plan, workspace)
        assert "nothing rendered" in result.warnings[0]
        assert result.skipped_artifacts == ("foo-skill",)
        assert result.rendered_paths == ()


# ---------------------------------------------------------------------------
# AGENTS.md / instructions rendering (plan item 6)
# ---------------------------------------------------------------------------


class TestAGENTSMdRendering:
    """Plan item 6: native_integration with Codex instructions binding
    → AGENTS.md section (via .codex/.scc-managed/instructions/)."""

    def test_instructions_creates_metadata_under_scc_managed(
        self, workspace: Path
    ) -> None:
        """Instructions binding writes to .codex/.scc-managed/instructions/."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"instructions": "team-guidelines/AGENTS.md"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        instr_path = workspace / SCC_MANAGED_DIR / INSTRUCTIONS_SUBDIR / "AGENTS.json"
        assert instr_path.exists()
        content = json.loads(instr_path.read_text())
        assert content["source"] == "team-guidelines/AGENTS.md"
        assert content["provider"] == "codex"
        assert content["bundle_id"] == "test-bundle"
        assert content["managed_by"] == "scc"
        assert instr_path in result.rendered_paths

    def test_instructions_filename_derived_from_stem(self, workspace: Path) -> None:
        """The output filename stem matches the source path's stem."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"instructions": "docs/coding-standards.md"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        expected = workspace / SCC_MANAGED_DIR / INSTRUCTIONS_SUBDIR / "coding-standards.json"
        assert expected.exists()

    def test_multiple_instructions_bindings(self, workspace: Path) -> None:
        """Two instruction bindings produce two metadata files."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"instructions": "docs/AGENTS.md"},
                ),
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"instructions": "docs/STYLE.md"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)
        instr_dir = workspace / SCC_MANAGED_DIR / INSTRUCTIONS_SUBDIR
        files = sorted(f.name for f in instr_dir.iterdir())
        assert "AGENTS.json" in files
        assert "STYLE.json" in files
        assert len(result.rendered_paths) == 2


# ---------------------------------------------------------------------------
# Merge strategy (plan item 8): SCC-managed sections marked; non-SCC preserved
# ---------------------------------------------------------------------------


class TestMergeStrategy:
    """Plan item 8: SCC-managed sections are clearly marked and non-SCC
    content is preserved during merge."""

    def test_hooks_scc_managed_key_isolates_scc_content(
        self, workspace: Path
    ) -> None:
        """SCC content goes under 'scc_managed' key, not at top level."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./hooks-src.json"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        hooks = json.loads(
            (workspace / CODEX_CONFIG_DIR / "hooks.json").read_text()
        )
        # SCC content is inside 'scc_managed', not scattered at root
        assert "scc_managed" in hooks
        # Only 'scc_managed' key exists (nothing else at top level)
        assert set(hooks.keys()) == {"scc_managed"}

    def test_hooks_multi_bundle_merge(self, workspace: Path) -> None:
        """Two bundles rendering hooks → both appear under scc_managed."""
        plan1 = _plan(
            bundle_id="bundle-a",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./hooks-a.json"},
                ),
            ),
        )
        plan2 = _plan(
            bundle_id="bundle-b",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./hooks-b.json"},
                ),
            ),
        )
        render_codex_artifacts(plan1, workspace)
        render_codex_artifacts(plan2, workspace)

        hooks = json.loads(
            (workspace / CODEX_CONFIG_DIR / "hooks.json").read_text()
        )
        assert "bundle-a" in hooks["scc_managed"]
        assert "bundle-b" in hooks["scc_managed"]
        assert hooks["scc_managed"]["bundle-a"]["source"] == "./hooks-a.json"
        assert hooks["scc_managed"]["bundle-b"]["source"] == "./hooks-b.json"

    def test_hooks_preserves_user_content_after_multi_bundle(
        self, workspace: Path
    ) -> None:
        """User content persists through multiple SCC-managed writes."""
        codex_dir = workspace / CODEX_CONFIG_DIR
        codex_dir.mkdir(parents=True, exist_ok=True)
        hooks_path = codex_dir / "hooks.json"
        hooks_path.write_text(json.dumps({"my_hook": {"event": "save"}}) + "\n")

        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"hooks": "./hooks-x.json"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        hooks = json.loads(hooks_path.read_text())
        assert hooks["my_hook"]["event"] == "save"
        assert "scc_managed" in hooks

    def test_plugin_manifest_has_managed_by_scc(self, workspace: Path) -> None:
        """Plugin manifest includes managed_by=scc for identification."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"plugin_bundle": "./my-plugin"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        plugin = json.loads(
            (workspace / CODEX_PLUGIN_DIR / "plugin.json").read_text()
        )
        assert plugin["managed_by"] == "scc"

    def test_rules_metadata_has_managed_by_scc(self, workspace: Path) -> None:
        """Rules metadata includes managed_by=scc for identification."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"rules": "./rules/safety.rules"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        rules = json.loads(
            (workspace / CODEX_RULES_DIR / "safety.rules.json").read_text()
        )
        assert rules["managed_by"] == "scc"

    def test_instructions_metadata_has_managed_by_scc(self, workspace: Path) -> None:
        """Instructions metadata includes managed_by=scc for identification."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"instructions": "./AGENTS.md"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        instr = json.loads(
            (workspace / SCC_MANAGED_DIR / INSTRUCTIONS_SUBDIR / "AGENTS.json").read_text()
        )
        assert instr["managed_by"] == "scc"

    def test_skill_metadata_has_managed_by_scc(self, workspace: Path) -> None:
        """Skill metadata includes managed_by=scc for identification."""
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/test",
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)

        skill = json.loads(
            (workspace / SKILLS_DIR / "skills_test" / "skill.json").read_text()
        )
        assert skill["managed_by"] == "scc"


# ---------------------------------------------------------------------------
# SCC section markers are exported (for callers doing AGENTS.md merge)
# ---------------------------------------------------------------------------


class TestSCCSectionMarkers:
    """Verify that SCC section markers are available as module constants."""

    def test_start_marker_exists(self) -> None:
        assert "SCC-MANAGED START" in SCC_SECTION_START

    def test_end_marker_exists(self) -> None:
        assert "SCC-MANAGED END" in SCC_SECTION_END

    def test_markers_are_comment_lines(self) -> None:
        assert SCC_SECTION_START.startswith("#")
        assert SCC_SECTION_END.startswith("#")


# ---------------------------------------------------------------------------
# _render_native_integration_binding — direct edge cases
# ---------------------------------------------------------------------------


class TestRenderNativeIntegrationDirect:
    """Direct tests for _render_native_integration_binding edge cases."""

    def test_empty_native_config_renders_nothing(self, workspace: Path) -> None:
        """Binding with empty native_config but classified as native via
        some external override → renders nothing, no crash."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_config={},
        )
        rendered, warnings = _render_native_integration_binding(
            binding, workspace, "empty-bundle"
        )
        assert rendered == []
        assert warnings == []

    def test_unknown_config_keys_ignored(self, workspace: Path) -> None:
        """Config keys outside _INTEGRATION_KEYS are silently ignored."""
        binding = ProviderArtifactBinding(
            provider="codex",
            native_config={"unknown_key": "some-value", "another": "val"},
        )
        rendered, warnings = _render_native_integration_binding(
            binding, workspace, "unknown-bundle"
        )
        assert rendered == []
        assert warnings == []

    def test_hooks_bundle_id_scoping(self, workspace: Path) -> None:
        """Each bundle gets its own key under scc_managed in hooks.json."""
        binding1 = ProviderArtifactBinding(
            provider="codex",
            native_config={"hooks": "./a.json"},
        )
        binding2 = ProviderArtifactBinding(
            provider="codex",
            native_config={"hooks": "./b.json"},
        )
        _render_native_integration_binding(binding1, workspace, "alpha")
        _render_native_integration_binding(binding2, workspace, "beta")

        hooks = json.loads(
            (workspace / CODEX_CONFIG_DIR / "hooks.json").read_text()
        )
        assert hooks["scc_managed"]["alpha"]["source"] == "./a.json"
        assert hooks["scc_managed"]["beta"]["source"] == "./b.json"


# ---------------------------------------------------------------------------
# Idempotent byte-level comparison
# ---------------------------------------------------------------------------


class TestIdempotentByteLevel:
    """Stronger idempotency check: byte-level file content comparison."""

    def test_skill_file_byte_identical_on_rerender(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="skills/review",
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)
        first_bytes = (
            workspace / SKILLS_DIR / "skills_review" / "skill.json"
        ).read_bytes()

        render_codex_artifacts(plan, workspace)
        second_bytes = (
            workspace / SKILLS_DIR / "skills_review" / "skill.json"
        ).read_bytes()

        assert first_bytes == second_bytes

    def test_plugin_file_byte_identical_on_rerender(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_config={"plugin_bundle": "./plugin-src"},
                ),
            ),
        )
        render_codex_artifacts(plan, workspace)
        first_bytes = (workspace / CODEX_PLUGIN_DIR / "plugin.json").read_bytes()

        render_codex_artifacts(plan, workspace)
        second_bytes = (workspace / CODEX_PLUGIN_DIR / "plugin.json").read_bytes()

        assert first_bytes == second_bytes

    def test_mcp_fragment_identical_on_rerender(self, workspace: Path) -> None:
        plan = _plan(
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="mcp-x",
                    transport_type="sse",
                    native_config={"url": "http://localhost:9090"},
                ),
            ),
        )
        r1 = render_codex_artifacts(plan, workspace)
        r2 = render_codex_artifacts(plan, workspace)
        assert json.dumps(r1.mcp_fragment, sort_keys=True) == json.dumps(
            r2.mcp_fragment, sort_keys=True
        )


# ---------------------------------------------------------------------------
# MCP audit file: bundle_id sanitisation
# ---------------------------------------------------------------------------


class TestMCPAuditBundleIdSanitisation:
    """Audit file names sanitise slashes in bundle_id."""

    def test_slash_in_bundle_id_sanitised(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="org/my-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="mcp-srv",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        audit_path = workspace / CODEX_CONFIG_DIR / ".scc-mcp-org_my-bundle.json"
        assert audit_path.exists()
        assert audit_path in result.rendered_paths

    def test_backslash_in_bundle_id_sanitised(self, workspace: Path) -> None:
        plan = _plan(
            bundle_id="org\\my-bundle",
            bindings=(
                ProviderArtifactBinding(
                    provider="codex",
                    native_ref="mcp-srv",
                    transport_type="sse",
                    native_config={"url": "http://localhost:8080"},
                ),
            ),
        )
        result = render_codex_artifacts(plan, workspace)

        audit_path = workspace / CODEX_CONFIG_DIR / ".scc-mcp-org_my-bundle.json"
        assert audit_path.exists()
        assert audit_path in result.rendered_paths
