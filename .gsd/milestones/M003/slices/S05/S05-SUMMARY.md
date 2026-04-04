---
id: S05
parent: M003
milestone: M003
provides:
  - Truthful README and user-facing strings aligned with NetworkPolicy enum vocabulary
  - 5 guardrail tests preventing stale network-mode vocabulary regression
  - Full exit gate baseline: 3464 tests, ruff clean, mypy clean
requires:
  - slice: S03
    provides: Enforced web-egress topology implementation that S05 verifies documentation accuracy against
  - slice: S04
    provides: Provider destination validation and operator diagnostics that S05 verifies documentation accuracy against
affects:
  []
key_files:
  - src/scc_cli/application/compute_effective_config.py
  - src/scc_cli/commands/config.py
  - tests/test_config_explain.py
  - README.md
  - tests/test_docs_truthfulness.py
key_decisions:
  - README Requires line lists Docker generically (Engine, Desktop, OrbStack, Colima) per Constitution §3 — no Docker Desktop hard dependency
  - Regex used for string-literal and README scanning in guardrail tests (sufficient for content matching); tokenize pattern reserved for code identifier scanning per existing test_runtime_detection_hotspots.py convention
  - Guardrail tests validate example JSON network_policy values against canonical NetworkPolicy enum to prevent drift
patterns_established:
  - Docs-truthfulness guardrail tests: scan source blocked_by strings, command warnings, README claims, and example JSON values against canonical enums to prevent vocabulary drift
  - Dual scanning strategy: tokenize for Python identifier scanning (per test_runtime_detection_hotspots.py), regex for string-literal and prose scanning (per test_docs_truthfulness.py)
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T11:10:24.131Z
blocker_discovered: false
---

# S05: Verification, docs truthfulness, and milestone closeout

**Purged all stale network-mode vocabulary from source/tests/docs and added 5 guardrail tests preventing regression; full exit gate passes (3464 tests, ruff clean, mypy clean)**

## What Happened

S05 closed M003 by ensuring every user-facing string, README claim, and test fixture reflects the current network-mode vocabulary (open / web-egress-enforced / locked-down-web) and the actual enforcement model.

T01 updated six stale strings across four files. In `compute_effective_config.py`, two `blocked_by` diagnostic strings still said "isolated" — changed to "locked-down-web". In `config.py`, the proxy warning said "corp-proxy-only" — changed to "web-egress-enforced". In `test_config_explain.py`, fixture values and a docstring used "corp-proxy" — changed to "web-egress-enforced". In `README.md`, four edits: (1) generalized Docker requirement from "Docker Desktop 4.50+" to "Docker (Engine, Desktop, OrbStack, or Colima)" per Constitution §3, (2) replaced the stale enforcement-scope bullet with an accurate topology-based description including the IPv4-only v1 disclosure, (3) changed the org-config example from "unrestricted" to "open", and (4) updated troubleshooting table from "Start Docker Desktop" to "Start Docker (Desktop, Engine, or compatible daemon)".

T02 created `tests/test_docs_truthfulness.py` with 5 guardrail tests: (a) scans source `blocked_by=` strings for stale network mode names, (b) scans command warning strings for stale names, (c) verifies README has no Docker Desktop hard requirement, (d) scans README for stale network mode values, and (e) validates all example JSON `network_policy` values against the canonical `NetworkPolicy` enum. All 5 tests pass against the T01-fixed codebase. The full exit gate (ruff + mypy + pytest) passes with 3464 total tests (3437 passed + 23 skipped + 4 xfailed), meeting the ≥3464 threshold.

## Verification

All slice-level checks pass:
- `uv run pytest --rootdir "$PWD" tests/test_config_explain.py -q` — 31/31 passed
- `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` — 5/5 passed
- `grep -c 'network_policy=isolated' src/scc_cli/application/compute_effective_config.py` — 0
- `grep -c 'corp-proxy-only' src/scc_cli/commands/config.py` — 0
- `grep -c '"unrestricted"' README.md` — 0
- `! grep -q 'Requires.*Docker Desktop' README.md` — pass
- `uv run ruff check` — All checks passed
- `uv run mypy src/scc_cli` — Success: no issues found in 249 source files
- `uv run pytest --rootdir "$PWD" -q` — 3437 passed, 23 skipped, 4 xfailed (3464 total ≥ 3464 threshold)

## Requirements Advanced

- R001 — Added 5 guardrail tests in test_docs_truthfulness.py that mechanically prevent stale vocabulary drift in user-facing strings, README, and example configs — advancing maintainability by making truthfulness regressions test-visible

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T01 encountered transient edit-tool failures on README.md (edits reported success but did not persist). Resolved via absolute paths and sed as fallback. No functional deviation from the plan.

## Known Limitations

None. All planned vocabulary fixes and guardrail tests are in place.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/application/compute_effective_config.py` — Updated two blocked_by diagnostic strings from 'isolated' to 'locked-down-web'
- `src/scc_cli/commands/config.py` — Updated proxy warning from 'corp-proxy-only' to 'web-egress-enforced'
- `tests/test_config_explain.py` — Updated fixture values and docstring from 'corp-proxy' to 'web-egress-enforced'
- `README.md` — Generalized Docker requirement, rewrote enforcement scope with topology description, updated example JSON and troubleshooting table
- `tests/test_docs_truthfulness.py` — Created 5 guardrail tests preventing stale network-mode vocabulary and README truthfulness regression
