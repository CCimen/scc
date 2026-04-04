---
estimated_steps: 10
estimated_files: 3
skills_used: []
---

# T01: Add governed-artifact diagnostics to doctor checks and support bundle

Extend doctor checks to report:
1. Active team context and enabled bundles
2. Selected provider and effective render plan
3. Rendered vs skipped vs blocked artifacts with reasons
4. Bundle resolution health (all referenced bundles exist, all artifacts resolvable)

Extend support bundle to include:
1. Effective ArtifactRenderPlan for the active session
2. Renderer results: which files written, which skipped, which failed
3. Bundle catalog summary from org config

Add tests for both diagnostic surfaces.

## Inputs

- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/core/governed_artifacts.py`

## Expected Output

- `src/scc_cli/doctor/checks/artifacts.py`
- `tests/test_doctor_artifact_checks.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_doctor_artifact_checks.py -v && uv run pytest --rootdir "$PWD" -q
