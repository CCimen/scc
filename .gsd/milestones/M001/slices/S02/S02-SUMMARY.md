---
id: S02
parent: M001
milestone: M001
provides:
  - A truthful vocabulary baseline for later characterization and typed-contract work.
  - Updated config/schema/example/test surfaces that no longer normalize the old policy names into active M001 code.
  - A green post-migration baseline for S03 and S04.
requires:
  - slice: S01
    provides: Documented green baseline and repo-truth inventory.
affects:
  - S03
  - S04
key_files:
  - src/scc_cli/core/enums.py
  - src/scc_cli/core/network_policy.py
  - src/scc_cli/application/compute_effective_config.py
  - src/scc_cli/commands/config.py
  - src/scc_cli/commands/launch/sandbox.py
  - src/scc_cli/adapters/docker_sandbox_runtime.py
  - src/scc_cli/marketplace/schema.py
  - src/scc_cli/schemas/org-v1.schema.json
  - README.md
  - examples/11-release-readiness-org.json
  - tests/test_config_inheritance.py
key_decisions:
  - Rename the enum symbols as well as the string values so the code reads natively in the new vocabulary.
  - Keep unrelated prose uses of isolated/unrestricted untouched unless they actually name the network-policy concept.
  - Use targeted policy-surface searches for verification instead of naive whole-word greps.
patterns_established:
  - When a terminology migration reuses common English words, verify policy-bearing surfaces with targeted searches rather than naive repo-wide grep.
  - Rename code symbols and serialized values together so the implementation stops thinking in legacy terms.
  - Use the fixed gate as the final proof for cross-cutting vocabulary changes.
observability_surfaces:
  - Targeted policy-surface verification search proving no legacy network-policy values or enum names remain on live surfaces.
  - Task summaries recording both the migration inventory and the full-gate proof after the rename.
drill_down_paths:
  - .gsd/milestones/M001/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T15:29:15.330Z
blocker_discovered: false
---

# S02: Truthful network vocabulary migration

**Renamed SCC’s live network-policy surfaces to open, web-egress-enforced, and locked-down-web while keeping the full verification gate green.**

## What Happened

This slice migrated SCC’s live network-policy vocabulary from unrestricted / corp-proxy-only / isolated to open / web-egress-enforced / locked-down-web. The change covered the core enum, policy ordering helpers, runtime and launch checks, effective-config diagnostics, typed marketplace/schema definitions, example org configs, README guidance, and the affected tests. The migration was intentionally scoped so unrelated English uses of isolated or unrestricted stayed untouched when they did not refer to the network-policy concept. The slice closed with the full fixed verification gate still green, which demonstrates that the terminology changed without breaking behavior.

## Verification

Verified the migration with a targeted search that found no legacy network-policy values or enum member names in the active src/tests/examples/README/plan/constitution surfaces, clean LSP diagnostics on edited Python modules, and a full passing run of `uv run ruff check && uv run mypy src/scc_cli && uv run pytest`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Verification used a narrowed search for policy-bearing surfaces because broad text searches now mostly hit unrelated English uses of the same words, such as allowed-plugin unrestricted semantics and isolated worktree phrasing.

## Known Limitations

Historical summaries and some current GSD planning prose still refer to the old vocabulary. Broad text searches across the repo still find unrelated uses of isolated/unrestricted that are not network-policy surfaces.

## Follow-ups

Current .gsd planning and state artifacts still contain historical mentions of the old vocabulary. Leave task summaries historical, but refresh any still-active milestone planning text when the roadmap is next rewritten.

## Files Created/Modified

- `src/scc_cli/core/enums.py` — Replaced legacy network policy enum members and values with the truthful vocabulary.
- `src/scc_cli/core/network_policy.py` — Updated policy ordering helpers to use open, web-egress-enforced, and locked-down-web.
- `src/scc_cli/application/compute_effective_config.py` — Updated effective-config blocking diagnostics for locked-down-web policy.
- `src/scc_cli/commands/config.py` — Updated config warnings and launch/runtime checks to use web-egress-enforced terminology.
- `src/scc_cli/commands/launch/sandbox.py` — Updated sandbox launch proxy handling to the new network-policy enum member.
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — Updated sandbox runtime adapter to the new network-policy enum member.
- `src/scc_cli/marketplace/schema.py` — Updated typed marketplace schema network_policy literals to the truthful vocabulary.
- `src/scc_cli/schemas/org-v1.schema.json` — Updated the bundled org schema network_policy enums to the truthful vocabulary.
- `README.md` — Updated README guidance and examples to the truthful network-policy vocabulary.
- `examples/11-release-readiness-org.json` — Updated example organization configs to use open, web-egress-enforced, and locked-down-web.
- `tests/test_config_inheritance.py` — Updated representative config and launch tests to assert against the truthful vocabulary.
