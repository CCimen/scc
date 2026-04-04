---
estimated_steps: 24
estimated_files: 5
skills_used: []
---

# T03: Build shared live launch dependency and plan helpers

Create the shared command-layer helper that builds provider-aware and audit-aware live start dependencies and prepares live start plans once. This keeps direct-start and worktree entrypoints from reconstructing `StartSessionDependencies` inline and gives the slice one place to enforce required provider plus audit wiring before preflight ever runs.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| default adapter bundle from `bootstrap.py` | fail fast with typed launch-builder errors rather than letting entrypoints start with partial provider/audit wiring | N/A | reject partially wired dependency bundles instead of guessing defaults |
| live-plan preparation helper | preserve existing marketplace-sync gating for standalone, offline, dry-run, and team-aware launches | N/A | keep request/org-config combinations on the current sync path rather than inventing a second preparation branch |

## Load Profile

- **Shared resources**: one live dependency bundle plus one prepared start plan per launch attempt.
- **Per-operation cost**: existing plan preparation plus one provider check and one audit-sink check.
- **10x breakpoint**: drift in duplicated builder logic breaks correctness long before performance becomes interesting.

## Negative Tests

- **Malformed inputs**: missing `agent_provider`, missing `audit_event_sink`, and partially wired adapter bundles.
- **Error paths**: standalone, offline, and dry-run requests preserve current sync behavior while still using the shared helper.
- **Boundary conditions**: team-aware launch requests with org config and standalone launches without org config both prepare through the same helper.

## Steps

1. Add or refine `build_start_session_dependencies(...)` and `prepare_live_start_plan(...)` in `src/scc_cli/commands/launch/dependencies.py` so live start paths share provider, sink, and marketplace-sync wiring.
2. Require provider and audit-sink wiring up front and surface missing wiring through typed errors instead of ad hoc command-layer checks.
3. Keep the helper command-layer owned and composition-root fed; do not add direct adapter imports to launch or worktree command modules.
4. Add focused bootstrap and command-surface coverage that fails if live dependency construction drifts from the shared helper.

## Must-Haves

- [ ] Live dependency construction requires both `agent_provider` and `audit_event_sink` before preparing a real launch plan.
- [ ] Shared helpers preserve the existing marketplace-sync gating behavior for direct launches.
- [ ] Command modules consume the same live builder instead of reconstructing `StartSessionDependencies` inline.
- [ ] Focused tests fail if composition-root wiring or shared helper behavior drifts.

## Inputs

- ``src/scc_cli/application/start_session.py``
- ``src/scc_cli/bootstrap.py``
- ``src/scc_cli/commands/launch/dependencies.py``
- ``src/scc_cli/commands/launch/flow.py``
- ``tests/fakes/__init__.py``

## Expected Output

- ``src/scc_cli/commands/launch/dependencies.py``
- ``src/scc_cli/bootstrap.py``
- ``tests/test_bootstrap.py``
- ``tests/test_cli.py``

## Verification

- Focused builder coverage proves provider and audit wiring are required and that direct-start preparation consumes the shared helper.
- `uv run pytest --rootdir "$PWD" ./tests/test_bootstrap.py ./tests/test_cli.py -q`

## Observability Impact

- Signals added/changed: builder failures become typed launch-builder errors instead of downstream preflight surprises.
- How a future agent inspects this: rerun `uv run pytest --rootdir "$PWD" ./tests/test_bootstrap.py ./tests/test_cli.py -q` to localize wiring drift before touching runtime paths.
- Failure state exposed: missing provider or sink wiring is visible at dependency-build time rather than after partial command execution.
