# S05: Coverage on governed-artifact/team-pack planning and renderer seams — UAT

**Milestone:** M005
**Written:** 2026-04-04T20:25:00.296Z

## UAT: S05 — Coverage on governed-artifact/team-pack planning and renderer seams

### Preconditions
- Python 3.10+ with uv installed
- Working directory: `scc-sync-1.7.3/`
- Dependencies installed: `uv sync`

---

### UAT-1: Bundle resolver contract tests pass and cover all 9 behavior contracts

**Steps:**
1. Run `uv run pytest tests/test_bundle_resolver_contracts.py -v`
2. Verify 59 tests pass
3. Verify test classes cover: `TestHappyPath`, `TestMultiBundle`, `TestSharedArtifacts`, `TestProviderSpecificNative`, `TestInstallIntentFiltering`, `TestMissingBundleReference`, `TestMissingArtifactInBundle`, `TestEmptyTeamConfig`, `TestStructuralReturnType`, `TestResolveSingleBundleEdgeCases`

**Expected:** 59 passed, 0 failed. Each class has at least 2 tests.

---

### UAT-2: Bundle resolver has 100% branch coverage

**Steps:**
1. Run `rm -f .coverage .coverage.*`
2. Run `uv run pytest tests/test_bundle_resolver_contracts.py --cov=scc_cli.core.bundle_resolver --cov-report=term-missing --cov-branch -p no:randomly -q`
3. Check the coverage line for `bundle_resolver.py`

**Expected:** 73 stmts, 0 miss, 26 branches, 0 partial → 100% coverage.

---

### UAT-3: Claude renderer characterization tests pass and achieve 100% coverage

**Steps:**
1. Run `uv run pytest tests/test_claude_renderer.py -v`
2. Verify 74 tests pass (34 original + 40 new)
3. Run `rm -f .coverage .coverage.*`
4. Run `uv run pytest tests/test_claude_renderer.py --cov=scc_cli.adapters.claude_renderer --cov-report=term-missing --cov-branch -p no:randomly -q`
5. Check the coverage line for `claude_renderer.py`

**Expected:** 74 passed, 0 failed. 160 stmts, 0 miss, 58 branches, 0 partial → 100%.

---

### UAT-4: Codex renderer characterization tests pass and achieve 100% coverage

**Steps:**
1. Run `uv run pytest tests/test_codex_renderer.py -v`
2. Verify 86 tests pass (38 original + 48 new)
3. Run `rm -f .coverage .coverage.*`
4. Run `uv run pytest tests/test_codex_renderer.py --cov=scc_cli.adapters.codex_renderer --cov-report=term-missing --cov-branch -p no:randomly -q`
5. Check the coverage line for `codex_renderer.py`

**Expected:** 86 passed, 0 failed. 178 stmts, 0 miss, 56 branches, 0 partial → 100%.

---

### UAT-5: Cross-provider pipeline integration tests pass

**Steps:**
1. Run `uv run pytest tests/test_render_pipeline_integration.py -v`
2. Verify 44 tests pass
3. Verify test classes cover: `TestSharedArtifactEquivalence`, `TestProviderSpecificFiltering`, `TestProviderSwitchRerenders`, `TestEndToEndClaude`, `TestEndToEndCodex`, `TestBackwardCompatibility`, `TestBoundaryContracts`, `TestMultiBundleRendering`, `TestCrossProviderEquivalence`, `TestDisabledFilteredExclusion`

**Expected:** 44 passed, 0 failed.

---

### UAT-6: Full test suite passes with no regressions

**Steps:**
1. Run `uv run pytest --rootdir "$PWD" -q`
2. Verify total passed count is ≥4428
3. Verify 0 failures

**Expected:** 4428+ passed, 23 skipped, 3 xfailed, 0 failures.

---

### UAT-7: Lint and type checks pass

**Steps:**
1. Run `uv run ruff check`
2. Run `uv run mypy src/scc_cli`

**Expected:** ruff: "All checks passed!". mypy: "Success: no issues found in 288 source files."

---

### Edge Cases Covered by Tests

| Edge Case | Test Location | What It Verifies |
|-----------|--------------|-----------------|
| Missing bundle reference | test_bundle_resolver_contracts.py::TestMissingBundleReference | Clear error message listing available bundles |
| Missing artifact in bundle | test_bundle_resolver_contracts.py::TestMissingArtifactInBundle | Partial resolution with skip report |
| Empty team config | test_bundle_resolver_contracts.py::TestEmptyTeamConfig | Empty plan, no error |
| Codex-only binding in Claude renderer | test_claude_renderer.py::TestSkippedCrossProviderBindings | Skipped with clear reason |
| Claude-only binding in Codex renderer | test_codex_renderer.py::TestProviderAsymmetry | Skipped with clear reason |
| Renderer materialization error | test_claude_renderer.py (failure tests) | Blocked with diagnostic |
| Teams without governed_artifacts | test_render_pipeline_integration.py::TestBackwardCompatibility | Old marketplace pipeline still works |
| Same plan, both providers | test_render_pipeline_integration.py::TestCrossProviderEquivalence | Shared artifacts present in both, native-only in matching provider |
| Disabled artifacts | test_render_pipeline_integration.py::TestDisabledFilteredExclusion | Excluded from render plan |
| Idempotent re-rendering | test_claude_renderer.py, test_codex_renderer.py (idempotency classes) | Byte-identical output on repeated renders |
