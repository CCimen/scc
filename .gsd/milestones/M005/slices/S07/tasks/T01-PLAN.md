---
estimated_steps: 5
estimated_files: 4
skills_used: []
---

# T01: Extend ArtifactRenderPlan and resolver to carry portable artifact metadata

1. Add a PortableArtifact dataclass (name, kind, source metadata) to governed_artifacts.py.
2. Add portable_artifacts: tuple[PortableArtifact, ...] field to ArtifactRenderPlan.
3. In _resolve_single_bundle, when an artifact has no provider bindings AND is SKILL or MCP_SERVER kind, create a PortableArtifact from the GovernedArtifact and add it to the plan's portable_artifacts.
4. Update existing resolver tests to verify portable_artifacts population.
5. Verify all existing tests still pass.

## Inputs

- `src/scc_cli/core/governed_artifacts.py`
- `src/scc_cli/core/bundle_resolver.py`

## Expected Output

- `src/scc_cli/core/governed_artifacts.py with PortableArtifact dataclass`
- `src/scc_cli/core/bundle_resolver.py populating portable_artifacts`

## Verification

uv run pytest tests/test_bundle_resolver.py tests/test_bundle_resolver_contracts.py -v && uv run mypy src/scc_cli/core/governed_artifacts.py src/scc_cli/core/bundle_resolver.py
