---
estimated_steps: 10
estimated_files: 2
skills_used: []
---

# T01: Contract tests for bundle resolution and render plan computation

Write comprehensive contract tests for src/scc_cli/core/bundle_resolver.py:
1. Happy path: team with enabled bundles → complete ArtifactRenderPlan with correct bindings and effective_artifacts
2. Multi-bundle: team enables multiple bundles → artifacts deduplicated and ordered
3. Shared artifacts: skill + MCP appear in plan for both providers with no provider-specific bindings
4. Provider-specific: native_integration with Claude binding → appears for Claude, skipped for Codex
5. Install intent filtering: disabled artifacts excluded, required auto-included, available preserved
6. Missing bundle reference: clear error message listing available bundles
7. Missing artifact in bundle: partial resolution with skip report
8. Empty team config: empty plan, no error
9. Coverage target: >95% branch coverage on bundle_resolver.py

## Inputs

- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/core/governed_artifacts.py`

## Expected Output

- `tests/test_bundle_resolver_contracts.py`

## Verification

uv run pytest tests/test_bundle_resolver_contracts.py -v && uv run pytest --cov=scc_cli.core.bundle_resolver --cov-report=term-missing --cov-branch
