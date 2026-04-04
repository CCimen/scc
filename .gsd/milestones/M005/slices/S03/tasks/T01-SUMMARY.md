---
id: T01
parent: S03
milestone: M005
key_files:
  - src/scc_cli/core/governed_artifacts.py
  - src/scc_cli/core/contracts.py
  - tests/test_governed_artifact_models.py
key_decisions:
  - Used tuple[str, ...] for collection fields to enforce full immutability, matching existing contracts.py pattern
  - ProviderArtifactBinding.native_config typed as dict[str, str] to keep provider config surface tight and string-serializable
  - ArtifactInstallIntent.REQUEST_ONLY uses 'request-only' (hyphenated) value matching spec-06 YAML vocabulary
duration: 
verification_result: passed
completed_at: 2026-04-04T17:28:19.198Z
blocker_discovered: false
---

# T01: Added 6 frozen model types (ArtifactKind, ArtifactInstallIntent, GovernedArtifact, ProviderArtifactBinding, ArtifactBundle, ArtifactRenderPlan) implementing spec-06 governed artifact type hierarchy with 20 passing tests

**Added 6 frozen model types (ArtifactKind, ArtifactInstallIntent, GovernedArtifact, ProviderArtifactBinding, ArtifactBundle, ArtifactRenderPlan) implementing spec-06 governed artifact type hierarchy with 20 passing tests**

## What Happened

Created src/scc_cli/core/governed_artifacts.py with the complete spec-06 type hierarchy: 2 str enums (ArtifactKind with 4 members, ArtifactInstallIntent with 4 members) and 4 frozen dataclasses (GovernedArtifact, ProviderArtifactBinding, ArtifactBundle, ArtifactRenderPlan). All models use only stdlib types (dataclasses, enum) — no pydantic dependency. ProviderArtifactBinding keeps Claude and Codex native details asymmetric per spec. Added re-exports to contracts.py. Created 20 unit tests covering construction, defaults, immutability, enum coverage, re-export identity, and a cross-model integration test matching the spec-06 YAML example.

## Verification

All 4 verification commands passed: ruff check (0 errors), mypy src/scc_cli (0 issues in 285 files), pytest on new test file (20/20 passed), full test suite (4099 passed, 23 skipped, 3 xfailed, 1 xpassed — no regressions).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3900ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3900ms |
| 3 | `uv run pytest tests/test_governed_artifact_models.py -v` | 0 | ✅ pass | 1320ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 69180ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/governed_artifacts.py`
- `src/scc_cli/core/contracts.py`
- `tests/test_governed_artifact_models.py`
