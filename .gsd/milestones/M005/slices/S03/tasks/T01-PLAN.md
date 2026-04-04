---
estimated_steps: 29
estimated_files: 3
skills_used: []
---

# T01: Define governed artifact core models from spec-06

Create the governed-artifact type hierarchy specified in spec-06 as frozen dataclasses. These models (GovernedArtifact, ArtifactBundle, ArtifactInstallIntent, ProviderArtifactBinding, ArtifactRenderPlan, ArtifactKind) define the provider-neutral bundle architecture's type surface. They are pure data definitions with no behavioral logic.

## Steps

1. Read `specs/06-governed-artifacts.md` to confirm model names, fields, and relationships.
2. Create `src/scc_cli/core/governed_artifacts.py` with:
   - `ArtifactKind` enum: `skill`, `mcp_server`, `native_integration`, `bundle`
   - `ArtifactInstallIntent` enum: `required`, `available`, `disabled`, `request_only`
   - `GovernedArtifact` frozen dataclass: kind, name, version, publisher, pinned, provenance fields
   - `ProviderArtifactBinding` frozen dataclass: provider name, native_ref, native_config dict, transport_type
   - `ArtifactBundle` frozen dataclass: name, description, artifacts list, install_intent
   - `ArtifactRenderPlan` frozen dataclass: bundle_id, provider, bindings list, skipped list, effective_artifacts
3. Add re-exports in `src/scc_cli/core/contracts.py` so downstream code can import from either location.
4. Create `tests/test_governed_artifact_models.py` with:
   - Construction tests for each model with all fields
   - Frozen immutability assertions
   - Enum membership and value coverage tests
   - Default value tests
5. Run `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pytest tests/test_governed_artifact_models.py`.

## Must-Haves

- [ ] All 6 model types exist as frozen dataclasses or enums
- [ ] Models use only stdlib types (dataclasses, enum) — no pydantic dependency
- [ ] ProviderArtifactBinding is provider-specific (Claude and Codex are NOT flattened)
- [ ] ArtifactBundle carries install_intent, not raw marketplace URLs
- [ ] Re-exports added to core/contracts.py
- [ ] Unit tests pass

## Verification

- `uv run ruff check`
- `uv run mypy src/scc_cli`
- `uv run pytest tests/test_governed_artifact_models.py -v`
- `uv run pytest --rootdir "$PWD" -q` (all 4106+ tests still pass)

## Inputs

- ``specs/06-governed-artifacts.md` — canonical model specification`
- ``src/scc_cli/core/contracts.py` — existing contracts module for re-exports`
- ``src/scc_cli/core/enums.py` — existing enum patterns to follow`

## Expected Output

- ``src/scc_cli/core/governed_artifacts.py` — new module with 6 model types`
- ``src/scc_cli/core/contracts.py` — updated with re-exports`
- ``tests/test_governed_artifact_models.py` — new unit tests`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_governed_artifact_models.py -v && uv run pytest --rootdir "$PWD" -q
