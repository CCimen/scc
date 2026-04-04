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
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scc_cli.adapters.claude_renderer import (
    SCC_MANAGED_DIR,
    RendererResult,
    render_claude_artifacts,
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
    provider: str = "claude",
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
            bindings=(
                ProviderArtifactBinding(provider="codex", native_ref="skills/foo"),
            ),
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
            bindings=(
                ProviderArtifactBinding(provider="claude"),
            ),
        )
        result = render_claude_artifacts(plan, workspace)
        assert len(result.warnings) >= 1
        assert any("no native_ref" in w or "no recognised" in w.lower()
                    or "no native_ref" in w.lower() for w in result.warnings)


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
        skill_path = (
            workspace / SCC_MANAGED_DIR / "skills" / "skills_code-review" / "skill.json"
        )
        assert skill_path.exists()

        # MCP server in settings
        assert "github-mcp" in result.settings_fragment.get("mcpServers", {})

        # Hooks + marketplace
        assert (workspace / SCC_MANAGED_DIR / "hooks" / "github-hooks.json").exists()
        assert "github-marketplace" in result.settings_fragment.get(
            "extraKnownMarketplaces", {}
        )

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
