---
estimated_steps: 9
estimated_files: 4
skills_used: []
---

# T01: Bundle resolution: compute ArtifactRenderPlan from NormalizedOrgConfig

Create src/scc_cli/core/bundle_resolver.py with a pure function resolve_render_plan(org_config: NormalizedOrgConfig, team_name: str, provider: str) -> ArtifactRenderPlan. This function:
1. Reads the team profile's enabled_bundles list from org_config
2. Resolves each bundle ID against the org's governed_artifacts catalog
3. Filters artifacts by install_intent and provider compatibility
4. Produces bindings for artifacts that have ProviderArtifactBinding for the target provider
5. Reports skipped artifacts (no binding for provider, disabled, unavailable)
6. Returns a complete ArtifactRenderPlan

Also extend NormalizedOrgConfig and NormalizedTeamConfig to carry governed_artifacts and enabled_bundles fields.

This is a pure core function — no imports from marketplace/, adapters/, or commands/.

## Inputs

- `src/scc_cli/core/governed_artifacts.py`
- `src/scc_cli/ports/config_models.py`
- `specs/06-governed-artifacts.md`

## Expected Output

- `src/scc_cli/core/bundle_resolver.py`
- `tests/test_bundle_resolver.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_bundle_resolver.py -v && uv run pytest --rootdir "$PWD" -q
