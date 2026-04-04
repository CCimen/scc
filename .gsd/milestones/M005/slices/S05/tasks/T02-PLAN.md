---
estimated_steps: 10
estimated_files: 1
skills_used: []
---

# T02: Characterization tests for Claude renderer

Write characterization tests for src/scc_cli/adapters/claude_renderer.py:
1. Skill rendering: skill artifact → installed in Claude skill surface
2. MCP rendering: MCP server artifact → Claude-native MCP configuration
3. Marketplace rendering: native_integration with Claude marketplace binding → marketplace metadata
4. Hook rendering: native_integration with Claude hook binding → hook configuration
5. Mixed bundle: bundle with skills + MCP + native → all rendered correctly
6. Skipped artifact: artifact with only Codex binding → skipped with reason
7. Idempotency: same plan rendered twice → identical output
8. Failure: materialization error → blocked with diagnostic
9. Coverage target: >90% branch coverage on claude_renderer.py

## Inputs

- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/core/governed_artifacts.py`

## Expected Output

- `tests/test_claude_renderer.py (extended)`

## Verification

uv run pytest tests/test_claude_renderer.py -v && uv run pytest --cov=scc_cli.adapters.claude_renderer --cov-report=term-missing --cov-branch
