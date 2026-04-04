---
estimated_steps: 10
estimated_files: 1
skills_used: []
---

# T03: Characterization tests for Codex renderer

Write characterization tests for src/scc_cli/adapters/codex_renderer.py:
1. Skill rendering: skill artifact → .agents/skills/ placement
2. MCP rendering: MCP server artifact → .codex/config.toml or .mcp.json entry
3. Plugin bundle rendering: native_integration with Codex plugin binding → .codex-plugin/plugin.json
4. Rules rendering: native_integration with Codex rules binding → .codex/rules/*.rules
5. Hooks rendering: native_integration with Codex hooks binding → .codex/hooks.json
6. AGENTS.md rendering: native_integration with Codex instructions binding → AGENTS.md section
7. Asymmetry test: bundle with Claude-only native_integration → skipped for Codex with clear reason
8. Merge strategy: SCC-managed sections marked; non-SCC content preserved
9. Coverage target: >90% branch coverage on codex_renderer.py

## Inputs

- `src/scc_cli/adapters/codex_renderer.py`
- `src/scc_cli/core/governed_artifacts.py`

## Expected Output

- `tests/test_codex_renderer.py (extended)`

## Verification

uv run pytest tests/test_codex_renderer.py -v && uv run pytest --cov=scc_cli.adapters.codex_renderer --cov-report=term-missing --cov-branch
