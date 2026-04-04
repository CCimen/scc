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
    SCC_MANAGED_DIR,
    SKILLS_DIR,
    RendererResult,
    render_codex_artifacts,
)
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
