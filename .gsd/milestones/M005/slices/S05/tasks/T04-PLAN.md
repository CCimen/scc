---
estimated_steps: 7
estimated_files: 1
skills_used: []
---

# T04: Cross-provider render plan equivalence and pipeline integration tests

Write integration tests that exercise the full planning→rendering pipeline:
1. Same org config + same team → same shared artifacts (skills, MCP) appear in both Claude and Codex plans
2. Provider-specific bindings appear only for the matching provider
3. Switching provider re-renders from same plan, produces different native outputs
4. End-to-end: NormalizedOrgConfig → resolve_render_plan → render_*_artifacts → verify file outputs
5. Backward compatibility: teams without governed_artifacts config → old marketplace pipeline still works
6. Coverage across the pipeline seam: bundle_resolver + renderer boundary contracts verified

## Inputs

- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/adapters/codex_renderer.py`

## Expected Output

- `tests/test_render_pipeline_integration.py`

## Verification

uv run pytest tests/test_render_pipeline_integration.py -v && uv run pytest --rootdir "$PWD" -q
