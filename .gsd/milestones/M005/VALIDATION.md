# M005 Milestone Validation: Architecture Quality, Strictness, And Hardening

**Validated:** 2026-04-04
**Verdict:** PASS

---

## Exit Criteria Checklist

### 1. All modules over 1100 lines reduced below threshold ✅

**Baseline (pre-M005):** 3 modules exceeded 1100 lines:
- `commands/launch/flow.py` — 1665 lines
- `ui/dashboard/orchestrator.py` — 1493 lines
- `setup.py` — 1336 lines

**Current state:** Zero modules exceed 1100 lines. Largest file is `compute_effective_config.py` at 852 lines.

**Evidence:** `find src/scc_cli -name "*.py" -exec wc -l {} + | sort -rn | awk '$1 > 1100 && $2 != "total"'` returns empty.

### 2. Every module above 800 lines split or justified ✅

**Current 800+ modules:** 1 file
- `application/compute_effective_config.py` — 852 lines

**Justification:** This module is a single-responsibility config computation pipeline. It contains 7 data classes (ConfigDecision, BlockedItem, DelegationDenied, MCPServer, SessionConfig, EffectiveConfig, StdioValidationResult) and the matching pure functions that evaluate team delegation, plugin/MCP allowlists, network policy, and project config merging. It was already split in T03 (extracted `_merge_team_mcp_servers` and `_merge_project_config`). The remaining code is cohesive — all functions serve the single `compute_effective_config()` entry point. It sits in the warning zone (800–1100) but below the hard fail threshold (1100). Test coverage is 93%.

**Evidence:** `test_file_sizes.py` passes (1/1, no xfail). The file size guardrail warning threshold is 800, fail threshold is 1100.

### 3. Top-20 hotspot list no longer dominated by orchestration monoliths ✅

**Baseline top-5:** flow.py (1665), orchestrator.py (1493), setup.py (1336), dashboard.py (1084), settings.py (1081)

**Current top-5:** compute_effective_config.py (852), setup.py (794), settings.py (792), picker.py (786), keys.py (784)

The largest file dropped from 1665 to 852 lines (49% reduction). The top-20 no longer contains any file above 852 lines. The former monoliths were decomposed: flow.py → flow.py (125) + flow_interactive.py (724) + flow_session.py + flow_types.py; orchestrator.py → orchestrator.py (160) + orchestrator_handlers.py (783) + orchestrator_menus.py + orchestrator_container_actions.py; setup.py → setup.py (794) + setup_config.py + setup_ui.py; dashboard.py → dashboard.py (187) + dashboard_loaders.py + dashboard_models.py.

### 4. Direct runtime/backend imports from core/app/commands/UI removed ✅

**Evidence:** `test_import_boundaries.py` — 31/31 tests pass, no xfail. `test_architecture_invariants.py` — 2/2 tests pass (application_forbidden_imports, application_no_direct_io_calls).

Import boundary violations fixed during M005:
- `core/personal_profiles.py` no longer imports from `docker.launch`
- `application/dashboard.py` no longer imports `docker.core.ContainerInfo` (uses `ports/models.py`)
- `doctor/checks/artifacts.py` uses `NormalizedOrgConfig.from_dict()` instead of importing from adapters

### 5. Internal config/policy logic uses typed models ✅

**Evidence:**
- `ports/config_models.py` defines typed config models (NormalizedOrgConfig, NormalizedTeamConfig, etc.)
- `core/governed_artifacts.py` defines typed artifact models (GovernedArtifact, ArtifactBinding, ArtifactRenderPlan, etc.)
- `core/bundle_resolver.py` operates on typed BundleResolution results
- `application/launch/wizard_models.py` provides typed wizard state
- `application/interaction_requests.py` provides typed interaction flows
- Config computation in `compute_effective_config.py` uses ConfigDecision, BlockedItem, DelegationDenied, MCPServer, SessionConfig, and EffectiveConfig dataclasses

### 6. Silent failure swallowing removed from maintained paths ✅

**Evidence:**
- Renderer failures are fail-closed with clear diagnostics (S04)
- Bundle resolution failures produce explicit error results (S04)
- Doctor checks return structured CheckResult with severity levels (S06/T01)
- Support bundle includes governed_artifacts diagnostics (S06/T01)
- `sync_marketplace_settings_for_start` is marked as transitional; bundle pipeline is canonical (S06/T02)

### 7. File/function size tests pass without xfail ✅

**Evidence:**
- `test_file_sizes.py` — 1/1 passed, no xfail markers
- `test_function_sizes.py` — 1/1 passed, no xfail markers (xfail removed in T03)

**Remaining xfails in the test suite (2):**
- `test_ui_integration.py` lines 441 and 462 — these are test-runner isolation issues (module caching between tests), not guardrail or architectural xfails. They pass individually but fail when run in the full suite due to Python module import state. These do not represent architectural debt.

### 8. Docs and diagnostics are truthful ✅

**Evidence:**
- `test_docs_truthfulness.py` — 18/18 tests pass, covering:
  - Codex capability_profile accuracy (supports_skills, supports_native_integrations)
  - Portable artifact contract language ("policy-effective" not "renderable")
  - Renderer docstring accuracy ("metadata-only" for native integrations)
  - org-v1.schema.json includes governed_artifacts and enabled_bundles
  - Provider surface asymmetry is documented as intentional
- Doctor checks accurately report team context, bundle resolution, and catalog health (25 tests)
- Support bundle includes governed_artifacts diagnostics

### 9. Verification gate passes ✅

| Gate | Command | Result |
|------|---------|--------|
| Lint | `uv run ruff check` | All checks passed |
| Types (mypy) | `uv run mypy src/scc_cli` | Success: 0 issues in 289 files |
| Tests | `uv run pytest --rootdir "$PWD" -q` | 4463 passed, 23 skipped, 2 xfailed |
| Coverage | pytest --cov --cov-branch | 73% overall (23558 stmts, 6343 miss) |

---

## Slice Delivery Summary

| Slice | Title | Status | Key Deliverables |
|-------|-------|--------|------------------|
| S01 | Maintainability baseline and refactor queue | ✅ Complete | Inventories, characterization tests, hotspot protection |
| S02 | Decompose oversized modules and repair boundaries | ✅ Complete | All >1100 modules split; boundary violations fixed |
| S03 | Typed config model adoption and strict typing cleanup | ✅ Complete | Typed config models adopted; cast-heavy paths replaced |
| S04 | Provider-neutral artifact pipeline and renderers | ✅ Complete | Bundle resolver, render plan, Claude+Codex renderers, fail-closed |
| S05 | Coverage on governed-artifact/team-pack seams | ✅ Complete | Contract tests for bundle resolution, render plan, both renderers |
| S06 | Diagnostics, docs truthfulness, guardrails, validation | ✅ Complete | Doctor checks, truthfulness tests, guardrails pass, validation |

---

## Risk Retirement

| Risk | Status | Evidence |
|------|--------|----------|
| Large files resist decomposition | Retired | All >1100 reduced; only 1 file in 800-1100 zone (justified) |
| Boundary violations re-introduced | Retired | 31 import boundary tests + 2 architecture invariant tests enforce |
| Guardrails remain xfailed | Retired | File/function size tests pass without xfail |
| Docs claim unimplemented capabilities | Retired | 18 truthfulness tests enforce accurate claims |
| Provider surface asymmetry causes confusion | Retired | Asymmetry documented as intentional in docs and tests |
