---
id: S03
parent: M001
milestone: M001
provides:
  - A stronger safety net for S04 typed-contract and error/audit work.
  - Explicit tests for the truthful network-policy ordering introduced in S02.
  - Launch-boundary proof for the current fail-closed safety-net behavior.
requires:
  - slice: S02
    provides: Green post-migration baseline with truthful network vocabulary.
affects:
  - S04
key_files:
  - tests/test_launch_proxy_env.py
  - tests/test_start_wizard_quick_resume_flow.py
  - tests/test_start_wizard_workspace_quick_resume.py
  - tests/test_context_recording_warning.py
  - tests/test_config_inheritance.py
  - tests/test_config_explain.py
  - tests/test_network_policy.py
  - tests/test_docker_policy.py
  - tests/test_docker_policy_integration.py
  - tests/test_plugin_isolation.py
key_decisions:
  - Keep characterization work focused on missing seams instead of duplicating already-strong coverage.
  - State the truthful policy ordering directly in tests so later refactors cannot silently reinterpret the new names.
  - Characterize the current safety baseline at the launch boundary rather than pretending the future shared SafetyEngine already exists.
patterns_established:
  - Prefer small characterization additions at missing seams over broad duplicate test suites.
  - When terminology changes meaning, add direct helper-level tests for the new ordering as well as integration-level assertions.
  - Characterize the current implementation seam honestly instead of writing tests for architecture that has not been built yet.
observability_surfaces:
  - New explicit tests for continue-session launch behavior and network-policy-driven env propagation.
  - New direct tests for truthful network-policy ordering and exact blocked_by diagnostics.
  - New launch-boundary test proving fail-closed safety policy injection still happens without org config.
drill_down_paths:
  - .gsd/milestones/M001/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T15:35:40.448Z
blocker_discovered: false
---

# S03: Characterization tests for fragile current behavior

**Added focused characterization coverage for launch/resume, config-policy ordering, and fail-closed safety behavior, then revalidated the full gate.**

## What Happened

This slice strengthened characterization coverage around the fragile behavior M001 is trying to preserve before deeper architectural changes land. On the launch side, the repo already had good quick-resume wizard characterization, so I added only the missing high-level tests for continue-session handoff and the negative proxy-env case. On the config side, I added explicit tests for the truthful network-policy ordering and tightened the locked-down-web MCP blocking assertion to include the exact block-reason diagnostic. On the safety side, the helper functions were already well covered, so I added one launch-boundary test proving that sandbox launch still writes the fail-closed default policy when no org config is present. The slice closed with the full fixed gate passing, which means the added characterization did not destabilize the repo.

## Verification

Verified each new characterization cluster with focused pytest runs, then ran the full fixed gate successfully: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

I added only focused characterization tests where coverage was missing, because the repo already had substantial launch, config, and safety coverage. The safety task characterized the current policy-extraction/injection seam rather than a future SafetyEngine that does not exist yet.

## Known Limitations

The current safety tests still characterize policy extraction, validation, and sandbox injection rather than direct command-family enforcement. That is accurate for the current codebase and should not be overstated in docs or future planning.

## Follow-ups

S04 can now introduce typed contracts and error/audit seams with clearer protection around launch/resume behavior, truthful network policy ordering, and fail-closed safety policy handling.

## Files Created/Modified

- `tests/test_launch_proxy_env.py` — Added launch-level characterization for continue-session handoff and the negative proxy-env case.
- `tests/test_config_inheritance.py` — Tightened config inheritance characterization to assert the exact locked-down-web block reason.
- `tests/test_network_policy.py` — Added explicit tests for truthful network-policy ordering.
- `tests/test_plugin_isolation.py` — Added a launch-boundary safety characterization proving fail-closed default policy injection.
