---
id: S06
parent: M005
milestone: M005
provides:
  - Team-pack diagnostic checks for doctor and support-bundle
  - 18 truthfulness guardrail tests enforcing accurate docs claims
  - File/function size guardrails passing without xfail
  - VALIDATION.md with evidence for all M005 exit criteria
requires:
  - slice: S03
    provides: NormalizedOrgConfig typed model and from_dict() factory
  - slice: S04
    provides: Bundle resolver, ArtifactRenderPlan, and provider-native renderers
  - slice: S05
    provides: Contract and characterization test coverage for pipeline modules
affects:
  []
key_files:
  - src/scc_cli/doctor/checks/artifacts.py
  - src/scc_cli/doctor/checks/__init__.py
  - src/scc_cli/application/support_bundle.py
  - tests/test_doctor_artifact_checks.py
  - tests/test_docs_truthfulness.py
  - tests/test_file_sizes.py
  - tests/test_function_sizes.py
  - src/scc_cli/adapters/codex_agent_provider.py
  - src/scc_cli/adapters/codex_renderer.py
  - src/scc_cli/adapters/claude_renderer.py
  - src/scc_cli/core/bundle_resolver.py
  - src/scc_cli/schemas/org-v1.schema.json
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/application/compute_effective_config.py
  - src/scc_cli/commands/reset.py
  - src/scc_cli/commands/org/update_cmd.py
  - .gsd/milestones/M005/VALIDATION.md
key_decisions:
  - Artifact diagnostics in support bundle keyed as 'governed_artifacts' to match domain language
  - Doctor checks return None to skip when not applicable, matching existing patterns
  - Catalog health check considers orphan bindings as errors
  - Codex capability_profile updated to supports_skills=True and supports_native_integrations=True to match renderer implementation
  - Portable artifacts without bindings are 'policy-effective' not 'renderable'
  - sync_marketplace_settings_for_start marked as transitional; bundle pipeline is canonical
  - Use NormalizedOrgConfig.from_dict() to avoid import boundary violation from doctor to adapters
  - Extracted wizard step handlers as standalone functions returning union types (_PickerContinue | _PickerExit)
  - All ruff per-file-ignores confirmed permanent — no transitional ignores to remove
  - compute_effective_config.py at 852 lines justified as cohesive single-responsibility module (93% coverage, below 1100 hard threshold)
patterns_established:
  - Doctor checks for governed-artifact diagnostics: check_team_context, check_bundle_resolution, check_catalog_health — each returns None to skip when not applicable
  - Support bundle governed_artifacts section with effective render plan, renderer results, and catalog summary
  - Truthfulness guardrail tests pattern: regex scan for prose/schema content, tokenize for Python identifiers
  - Union return types for extracted wizard step handlers (_PickerContinue | _PickerExit) enabling exhaustive pattern matching
  - VALIDATION.md pattern: exit criteria checklist with evidence, slice delivery summary, and risk retirement table
observability_surfaces:
  - scc doctor — three new artifact checks: team context, bundle resolution, catalog health
  - scc support — governed_artifacts section in support bundle with render plan and renderer results
drill_down_paths:
  - .gsd/milestones/M005/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S06/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S06/tasks/T03-SUMMARY.md
  - .gsd/milestones/M005/slices/S06/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T21:15:48.430Z
blocker_discovered: false
---

# S06: Diagnostics, docs truthfulness, guardrails, and milestone validation for team-pack model

**Added team-pack diagnostics to doctor/support-bundle, fixed four docs truthfulness gaps, removed all guardrail xfails by extracting four oversized functions, and validated all M005 exit criteria with a clean verification gate (4463 passed, 0 failed).**

## What Happened

S06 closed M005 by ensuring all operator-facing surfaces accurately describe the governed-artifact/team-pack model and that all architecture quality guardrails pass without transitional exemptions.

**T01 — Doctor checks and support-bundle diagnostics.** Created `src/scc_cli/doctor/checks/artifacts.py` with three new doctor checks: `check_team_context()` reports the active team profile and enabled bundles; `check_bundle_resolution()` exercises the resolver and reports missing/resolvable bundles; `check_catalog_health()` validates the governed-artifact catalog for orphan bindings and missing artifact references. Added `build_artifact_diagnostics_summary()` for the support bundle's `governed_artifacts` section, covering effective render plan, renderer results, and bundle catalog summary. All 25 diagnostic tests pass. Fixed an early-return logic issue in `check_catalog_health()` — orphan bindings with no artifacts would have silently passed the empty-catalog guard.

**T02 — Truthfulness fixes.** Addressed four specific gaps: (1) bundle resolver comment updated from 'renderable' to 'policy-effective' for portable artifacts without bindings; (2) Codex `capability_profile` corrected to `supports_skills=True` and `supports_native_integrations=True`; (3) both renderer module docstrings updated to say 'metadata-only' for native integration output; (4) `sync_marketplace_settings_for_start` marked as explicitly transitional. Updated `org-v1.schema.json` with `governed_artifacts` and `enabled_bundles` sections. Fixed an import boundary violation in T01's `artifacts.py` — replaced direct `adapters.config_normalizer` import with `NormalizedOrgConfig.from_dict()`. Removed a stale xfail on `test_file_size_limits`. Added 8 truthfulness guardrail tests (18 total in test_docs_truthfulness.py).

**T03 — Guardrail cleanup.** Four functions exceeded the 300-line limit: `interactive_start` (524 lines), `compute_effective_config` (424), `org_update_cmd` (309), and `reset_cmd` (308). Each was decomposed: wizard step handlers extracted as standalone functions returning `_PickerContinue | _PickerExit` union types; config computation helpers `_merge_team_mcp_servers`/`_merge_project_config` extracted; org update split into `_update_single_team`/`_update_all_teams`; reset split into `_execute_factory_reset`. The xfail marker on `test_function_size_limits` was removed. All ruff per-file-ignores were audited and confirmed permanent (T201 for CLI stdout, UP037 for defensive annotation).

**T04 — Milestone validation.** Ran the complete M005 verification gate: ruff check (0 errors), mypy (0 issues, 289 files), pytest (4463 passed, 23 skipped, 2 xfailed). Validated all 9 exit criteria with evidence: zero modules over 1100 lines (baseline had 3 at 1665/1493/1336); one module in 800–1100 zone justified (compute_effective_config.py at 852, 93% coverage); top-20 no longer dominated by monoliths; 31/31 import boundary tests pass; typed models adopted throughout config/policy/launch; silent failure swallowing removed with fail-closed renderers; file/function size guardrails pass without xfail; 18/18 truthfulness tests pass. Wrote VALIDATION.md with evidence for each criterion.

## Verification

All slice verification checks pass:

1. `uv run ruff check` — All checks passed (exit 0)
2. `uv run mypy src/scc_cli` — Success: no issues found in 289 source files (exit 0)
3. `uv run pytest tests/test_doctor_artifact_checks.py -v` — 25/25 passed (exit 0)
4. `uv run pytest tests/test_docs_truthfulness.py -v` — 18/18 passed (exit 0)
5. `uv run pytest tests/test_file_sizes.py tests/test_function_sizes.py -v` — 2/2 passed, no xfail (exit 0)
6. `uv run pytest tests/test_import_boundaries.py -v` — 31/31 passed (exit 0)
7. `uv run pytest tests/test_architecture_invariants.py -v` — 2/2 passed (exit 0)
8. `uv run pytest --rootdir "$PWD" -q` — 4463 passed, 23 skipped, 2 xfailed (exit 0)

## Requirements Advanced

- R001 — S06 completed the M005 quality cycle: doctor checks now report governed-artifact health, docs truthfulness is mechanically enforced (18 tests), file/function size guardrails pass without xfail after extracting 4 oversized functions, and all 9 M005 exit criteria validated. 4463 tests passing.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 fixed an import boundary violation introduced in T01 — doctor/checks/artifacts.py had a direct import from scc_cli.adapters.config_normalizer. Replaced with NormalizedOrgConfig.from_dict() which uses importlib internally to preserve the boundary. T03 used NormalizedTeamConfig instead of TeamProfile for _merge_team_mcp_servers type annotation (mypy caught the mismatch). Both were corrected within the slice.

## Known Limitations

compute_effective_config.py remains at 852 lines (in the 800–1100 warning zone). Justified as cohesive single-responsibility module with 93% coverage. Two xfails in test_ui_integration.py are test-runner isolation issues (module caching), not architectural debt.

## Follow-ups

None. M005 is fully validated and ready for completion.

## Files Created/Modified

- `src/scc_cli/doctor/checks/artifacts.py` — New file: three doctor checks (team context, bundle resolution, catalog health) and governed-artifact diagnostics summary builder
- `src/scc_cli/doctor/checks/__init__.py` — Registered artifact checks in run_all_checks()
- `src/scc_cli/application/support_bundle.py` — Added governed_artifacts section to support bundle manifest
- `tests/test_doctor_artifact_checks.py` — New file: 25 tests covering all diagnostic surfaces
- `src/scc_cli/adapters/codex_agent_provider.py` — Fixed capability_profile: supports_skills=True, supports_native_integrations=True
- `src/scc_cli/adapters/codex_renderer.py` — Updated docstring to say 'metadata-only' for native integration output
- `src/scc_cli/adapters/claude_renderer.py` — Updated docstring to say 'metadata-only' for native integration output
- `src/scc_cli/core/bundle_resolver.py` — Updated comment: portable artifacts without bindings are 'policy-effective' not 'renderable'
- `src/scc_cli/application/start_session.py` — Marked sync_marketplace_settings_for_start as transitional
- `src/scc_cli/schemas/org-v1.schema.json` — Added governed_artifacts and enabled_bundles sections
- `tests/test_docs_truthfulness.py` — Added 8 truthfulness guardrail tests (18 total)
- `tests/test_file_sizes.py` — Removed stale xfail on test_file_size_limits
- `tests/test_function_sizes.py` — Removed xfail on test_function_size_limits
- `src/scc_cli/commands/launch/flow_interactive.py` — Extracted wizard step handlers (_handle_workspace_picker, _handle_workspace_source) with union return types
- `src/scc_cli/application/compute_effective_config.py` — Extracted _merge_team_mcp_servers and _merge_project_config helpers
- `src/scc_cli/commands/reset.py` — Extracted _execute_factory_reset helper
- `src/scc_cli/commands/org/update_cmd.py` — Extracted _update_single_team and _update_all_teams helpers
- `.gsd/milestones/M005/VALIDATION.md` — M005 milestone validation with evidence for all 9 exit criteria
