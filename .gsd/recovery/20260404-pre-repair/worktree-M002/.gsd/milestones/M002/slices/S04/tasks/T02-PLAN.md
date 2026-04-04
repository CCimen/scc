---
estimated_steps: 25
estimated_files: 8
skills_used: []
---

# T02: Adopt the shared preflight and audit seam in direct and worktree start paths

Carry the new boundary through the real entrypoints so direct `scc start` and worktree auto-start cannot bypass provider validation or audit persistence. Keep `bootstrap.py` as the only adapter composition root, require provider plus audit wiring up front, and preserve existing dry-run plus human/JSON error behavior while making worktree auto-start team-aware.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| default adapter bundle from `bootstrap.py` | fail fast with typed launch-builder errors rather than letting entrypoints start with partial provider or audit wiring | N/A | reject partially wired dependency bundles instead of guessing defaults |
| direct `scc start` CLI boundary | surface blocked preflight through the existing human/JSON error boundary and keep runtime stopped | N/A | preserve current output contracts rather than swallowing invalid-plan or blocked-policy reasons |
| worktree auto-start team propagation | treat missing `selected_profile` propagation as a correctness bug because preflight would silently fall back to open-network semantics | N/A | preserve direct-start and worktree behavior parity for team-aware launches |

## Load Profile

- **Shared resources**: shared dependency builder, shared audit sink, fake runtime, and selected-profile config state.
- **Per-operation cost**: one prepared launch plan plus one or two audit appends per live start path.
- **10x breakpoint**: repeated blocked launches will show up as audit noise and failing tests before compute cost becomes interesting.

## Negative Tests

- **Malformed inputs**: missing `agent_provider`, missing `audit_event_sink`, and partially wired adapter bundles.
- **Error paths**: blocked preflight keeps the fake runtime at zero launches for both direct start and worktree auto-start, including JSON output mode.
- **Boundary conditions**: successful standalone starts and successful worktree auto-starts both emit the same canonical event sequence with the correct workspace path and team context.

## Steps

1. Add `src/scc_cli/commands/launch/dependencies.py` as the shared live dependency and plan builder, keeping marketplace-sync gating in one place.
2. Require provider and audit-sink wiring up front and surface missing wiring through typed errors instead of ad hoc command-layer checks.
3. Route direct `scc start` and worktree auto-start through the shared builder and `finalize_launch(...)`, deriving worktree team context from `selected_profile` so org-policy preflight stays honest.
4. Extend focused bootstrap, CLI, integration, and worktree tests so bypassing preflight, skipping audit writes, or starting the runtime after a blocked preflight becomes a failing test.

## Must-Haves

- [ ] Live dependency construction requires both `agent_provider` and `audit_event_sink` before preparing a real launch plan.
- [ ] `src/scc_cli/commands/launch/flow.py` and `src/scc_cli/commands/worktree/worktree_commands.py` both finish live starts through `finalize_launch(...)`.
- [ ] Worktree auto-start carries `selected_profile` into `StartSessionRequest.team` so provider preflight stays team-aware under locked-down policies.
- [ ] Focused tests fail loudly if either entrypoint bypasses preflight, skips audit writes, or starts the runtime after a blocked preflight.

## Inputs

- ``src/scc_cli/bootstrap.py``
- ``src/scc_cli/application/launch/finalize_launch.py``
- ``src/scc_cli/application/start_session.py``
- ``src/scc_cli/commands/launch/flow.py``
- ``src/scc_cli/commands/worktree/worktree_commands.py``
- ``tests/fakes/__init__.py``
- ``tests/conftest.py``

## Expected Output

- ``src/scc_cli/commands/launch/dependencies.py``
- ``src/scc_cli/bootstrap.py``
- ``src/scc_cli/commands/launch/flow.py``
- ``src/scc_cli/commands/worktree/worktree_commands.py``
- ``tests/test_bootstrap.py``
- ``tests/test_cli.py``
- ``tests/test_integration.py``
- ``tests/test_worktree_cwd.py``

## Verification

uv run pytest --rootdir "$PWD" ./tests/test_bootstrap.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q

## Observability Impact

Makes both live entrypoints append the same canonical audit events and surface the same typed preflight failures; entrypoint-specific bypasses become visible as missing audit records or unexpected runtime starts in focused tests.
