---
id: S04
parent: M007-cqttot
milestone: M007-cqttot
provides:
  - core/constants.py contains only product-level constants — no provider-specific values
  - Guardrail test prevents re-introduction of Claude constants into core
  - profile.py documented as Claude-only provider module
requires:
  - slice: S01
    provides: ProviderRuntimeSpec registry and fail-closed dispatch — S04 localizes the remaining non-registry Claude constants that S01 did not address
affects:
  - S05
key_files:
  - src/scc_cli/core/constants.py
  - src/scc_cli/docker/core.py
  - src/scc_cli/docker/credentials.py
  - src/scc_cli/docker/launch.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/profile.py
  - tests/test_no_claude_constants_in_core.py
key_decisions:
  - Localized Claude constants in all 5 consumer modules (docker/, adapters/, application/) in a single pass rather than splitting across tasks
  - Used underscore-prefixed names (_SANDBOX_IMAGE, _CLAUDE_AGENT_NAME) to signal module-private scope
  - Renamed adapter/application constants to _CLAUDE_* prefix for self-documentation while docker/ kept original names since the entire module is Claude-specific
  - Used tokenize-based scanning for constant definitions (avoiding docstring/comment false positives) and simple string matching for import-line scanning in guardrail test
patterns_established:
  - Provider-specific constants localized as underscore-prefixed module-private values in the consumer module, not shared through core
  - Guardrail test combining tokenize-based definition scanning with import-line scanning to prevent constant re-introduction
  - Module-level docstrings documenting provider-specific modules (profile.py as Claude-only) with explicit rationale for hardcoded references
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M007-cqttot/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-05T14:06:37.172Z
blocker_discovered: false
---

# S04: Legacy Claude path isolation and Docker module cleanup

**Localized 9 Claude-specific constants from core/constants.py into 5 consumer modules, renamed to self-documenting _CLAUDE_* prefixes, documented profile.py as Claude-only, and added a tokenize-based guardrail test preventing re-introduction.**

## What Happened

S04 eliminated the false impression that Claude runtime values (image names, volume names, mount paths, credential keys, marketplace repo) were shared concerns by moving them out of core/constants.py into the adapter modules that actually use them.

**T01** localized all 9 Claude-specific constants into their 5 consumer modules: docker/core.py got `_SANDBOX_IMAGE` and `_SANDBOX_DATA_MOUNT`; docker/credentials.py got `_OAUTH_CREDENTIAL_KEY` and `_SANDBOX_DATA_VOLUME`; docker/launch.py got `_SAFETY_NET_POLICY_FILENAME`, `_SANDBOX_DATA_MOUNT`, and `_SANDBOX_DATA_VOLUME`; adapters/oci_sandbox_runtime.py got `_AGENT_NAME` and `_SANDBOX_DATA_VOLUME`; application/start_session.py got `_SANDBOX_IMAGE`. After removal, core/constants.py retains only CLI_VERSION, CURRENT_SCHEMA_VERSION, and WORKTREE_BRANCH_PREFIX — genuine product-level values. Four test files were updated to import from localized sources using aliased imports to minimize test churn.

**T02** renamed the localized constants to explicitly Claude-prefixed names for self-documentation: `_CLAUDE_AGENT_NAME`, `_CLAUDE_DATA_VOLUME` (in oci_sandbox_runtime.py), `_DOCKER_DESKTOP_CLAUDE_IMAGE` (in start_session.py). The docker/ module kept its original names since the entire module is Claude-specific (Docker Desktop sandbox adapter). profile.py received a module-level docstring documenting it as Claude provider only with intentional hardcoded references to `.claude/settings.local.json`.

**T03** added tests/test_no_claude_constants_in_core.py with two guardrail tests: (1) a tokenize-based scan of core/constants.py that fails if any Claude-specific NAME token reappears, (2) a codebase-wide scan for import lines pulling Claude constants from core.constants. Also fixed a ruff I001 import-sorting violation in test_oci_sandbox_runtime.py introduced by T02's import restructuring.

## Verification

**Slice-level verification (all pass):**

1. `rg` scan for Claude-constant imports from core.constants across src/scc_cli/ — zero matches (exit code 1 = no hits)
2. `uv run pytest tests/test_no_claude_constants_in_core.py -v` — 2/2 guardrail tests pass
3. `uv run pytest -q` — 4720 passed, 23 skipped, 2 xfailed (net +2 from guardrail tests)
4. `uv run ruff check` — 0 errors
5. core/constants.py contains only CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX — verified by reading the file

## Requirements Advanced

- R001 — Eliminated false shared-constant coupling between core and 5 provider-specific consumer modules, improving cohesion and reducing change risk when adding future providers

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T01 extended scope beyond docker/ to also localize constants in adapters/oci_sandbox_runtime.py and application/start_session.py — required to make the core/constants.py removal safe. T02 was reduced to renaming and documentation since T01 had already done the full localization. These deviations did not change the outcome — the slice delivered exactly what the plan specified.

## Known Limitations

None. All Claude-specific constants are fully localized with guardrail protection.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/core/constants.py` — Stripped 9 Claude-specific constants; now holds only CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX
- `src/scc_cli/docker/core.py` — Added _SANDBOX_IMAGE and _SANDBOX_DATA_MOUNT as module-private constants
- `src/scc_cli/docker/credentials.py` — Added _OAUTH_CREDENTIAL_KEY and _SANDBOX_DATA_VOLUME as module-private constants
- `src/scc_cli/docker/launch.py` — Added _SAFETY_NET_POLICY_FILENAME, _SANDBOX_DATA_MOUNT, _SANDBOX_DATA_VOLUME as module-private constants
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — Added _CLAUDE_AGENT_NAME and _CLAUDE_DATA_VOLUME as module-private constants
- `src/scc_cli/application/start_session.py` — Added _DOCKER_DESKTOP_CLAUDE_IMAGE as module-private constant
- `src/scc_cli/commands/profile.py` — Updated module docstring to document Claude provider only status
- `tests/test_no_claude_constants_in_core.py` — New guardrail test with tokenize-based definition scanning and import-line scanning
- `tests/test_oci_sandbox_runtime.py` — Updated imports for localized constants; fixed ruff I001 import-sorting violation
- `tests/test_application_start_session.py` — Updated imports for localized constants
- `tests/test_start_session_image_routing.py` — Updated imports for localized constants
- `tests/test_docker_policy_integration.py` — Updated imports for localized constants
