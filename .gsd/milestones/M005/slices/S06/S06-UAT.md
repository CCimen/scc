# S06: Diagnostics, docs truthfulness, guardrails, and milestone validation for team-pack model — UAT

**Milestone:** M005
**Written:** 2026-04-04T21:15:48.430Z

## UAT: S06 — Diagnostics, docs truthfulness, guardrails, and milestone validation

### Preconditions
- Working directory: `scc-sync-1.7.3`
- Python 3.10+ with `uv` installed
- Dependencies synced: `uv sync`

---

### UAT-1: Doctor checks report team-pack diagnostics

**Steps:**
1. Run `uv run pytest tests/test_doctor_artifact_checks.py -v`
2. Verify all 25 tests pass across 5 test classes:
   - `TestCheckTeamContext` (6 tests): standalone mode, no profile, profile not found, no bundles, with bundles, exception handling
   - `TestCheckBundleResolution` (6 tests): no org config, no profile, no bundles, success, missing bundle, exception
   - `TestCheckCatalogHealth` (6 tests): no org config, empty catalog, healthy catalog, missing artifact, orphan binding, exception
   - `TestBuildArtifactDiagnosticsSummary` (6 tests): standalone, no profile, active profile, normalization failure, profile not found, skipped artifacts
   - `TestRunAllChecksIntegration` (1 test): artifact checks registered in run_all_checks

**Expected:** 25/25 passed

### UAT-2: Truthfulness guardrails enforce accurate docs claims

**Steps:**
1. Run `uv run pytest tests/test_docs_truthfulness.py -v`
2. Verify all 18 tests pass covering:
   - No stale network mode names in blocked_by strings and user warnings
   - README: no Docker Desktop hard requirement, no stale network modes, mentions safety audit, describes core safety engine, mentions runtime wrappers
   - Example JSON uses valid network policy values
   - Safety engine and adapter files exist
   - Codex capability_profile: supports_skills=True, supports_native_integrations=True
   - Provider profiles are asymmetric and truthful
   - Schema includes governed_artifacts and enabled_bundles
   - Renderer docstrings say 'metadata' not 'content'
   - sync_marketplace_settings_for_start is transitional
   - Bundle resolver portable comment is truthful

**Expected:** 18/18 passed

### UAT-3: File-size guardrail passes without xfail

**Steps:**
1. Run `uv run pytest tests/test_file_sizes.py -v`
2. Verify no xfail marker is present in the test
3. Verify no source file exceeds 1100 lines

**Expected:** 1/1 passed, no xfail, no files above threshold

### UAT-4: Function-size guardrail passes without xfail

**Steps:**
1. Run `uv run pytest tests/test_function_sizes.py -v`
2. Verify no xfail marker is present in the test
3. Verify no function exceeds 300 lines

**Expected:** 1/1 passed, no xfail, no functions above threshold

### UAT-5: Import boundaries and architecture invariants hold

**Steps:**
1. Run `uv run pytest tests/test_import_boundaries.py tests/test_architecture_invariants.py -v`
2. Verify all 33 tests pass (31 boundary + 2 invariants)

**Expected:** 33/33 passed

### UAT-6: Full verification gate passes

**Steps:**
1. Run `uv run ruff check` — expect 0 errors
2. Run `uv run mypy src/scc_cli` — expect 0 issues in 289 files
3. Run `uv run pytest --rootdir "$PWD" -q` — expect 4463+ passed, 0 failed

**Expected:** All three gates green

### UAT-7: VALIDATION.md exists and covers all exit criteria

**Steps:**
1. Open `.gsd/milestones/M005/VALIDATION.md`
2. Verify it contains:
   - Verdict: PASS
   - 9 numbered exit criteria, each with ✅ and evidence
   - Slice delivery summary table (S01–S06 all ✅)
   - Risk retirement table

**Expected:** All exit criteria documented with evidence, verdict is PASS

### Edge Cases

**EC-1: Doctor artifacts check degrades gracefully with no org config**
- Verified by `TestCheckTeamContext::test_standalone_mode_when_no_org_config`, `TestCheckBundleResolution::test_none_when_no_org_config`, `TestCheckCatalogHealth::test_none_when_no_org_config`

**EC-2: Catalog health detects orphan bindings**
- Verified by `TestCheckCatalogHealth::test_binding_for_unknown_artifact`

**EC-3: Doctor checks handle unexpected exceptions without crashing**
- Verified by exception-handling tests in each check class
