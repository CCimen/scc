---
estimated_steps: 25
estimated_files: 4
skills_used: []
---

# T04: Route direct start and worktree auto-start through the shared launch finalizer

Close the integration loop by forcing both live launch entrypoints to consume the shared builder and to finish through `finalize_launch(...)`. Preserve current sync, dry-run, and output behavior for direct `scc start`, propagate `selected_profile` into worktree auto-start so provider policy stays team-aware, and extend focused CLI/integration coverage so bypassing preflight or audit becomes a failing test instead of silent drift.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| direct `scc start` entrypoint | surface the preflight error through the existing CLI/JSON boundary and keep runtime stopped | N/A | preserve current human/JSON output contracts rather than swallowing the invalid-plan or blocked-policy reason |
| worktree auto-start team propagation | treat missing `selected_profile` propagation as a correctness bug because preflight would silently fall back to open-network semantics | N/A | preserve direct-start and worktree behavior parity for team-aware launches |
| shared builder plus `finalize_launch(...)` | reuse the same pass/fail boundary for both entrypoints instead of allowing one path to bypass audit or preflight | N/A | keep standalone/offline behavior intact while still reaching the shared boundary |

## Load Profile

- **Shared resources**: shared audit sink, shared dependency builder, fake runtime, and selected-profile config state.
- **Per-operation cost**: one prepared launch plan plus one or two audit appends per live start path.
- **10x breakpoint**: repeated blocked launches will show up as audit noise and failing tests before compute cost becomes interesting.

## Negative Tests

- **Malformed inputs**: standalone/offline combinations preserve current behavior while still flowing through the shared boundary when live startup is requested.
- **Error paths**: blocked preflight keeps the fake runtime at zero launches for both direct start and worktree auto-start.
- **Boundary conditions**: successful standalone starts and successful worktree auto-starts both emit the same canonical event sequence with the correct workspace path and team context.

## Steps

1. Route direct `scc start` through shared live-plan preparation and `finalize_launch(...)`, preserving current sync, dry-run, and JSON/human output behavior.
2. Route worktree auto-start through the same builder and finalizer, deriving team context from `selected_profile` so org-policy preflight and audit behavior match direct start.
3. Extend focused CLI and integration tests proving both entrypoints append canonical events, blocked launches fail before runtime start, and selected-profile propagation is preserved.
4. Finish with the focused entrypoint verification and rely on the slice-level lint/type checks for final confidence.

## Must-Haves

- [ ] `src/scc_cli/commands/launch/flow.py` and `src/scc_cli/commands/worktree/worktree_commands.py` both finish live starts through `finalize_launch(...)`.
- [ ] Worktree auto-start carries `selected_profile` into `StartSessionRequest.team` so provider preflight stays team-aware under locked-down policies.
- [ ] Success paths emit the same canonical audit events regardless of entrypoint.
- [ ] Focused tests fail loudly if either entrypoint bypasses preflight, skips audit writes, or starts the runtime after a blocked preflight.

## Inputs

- ``src/scc_cli/commands/launch/dependencies.py``
- ``src/scc_cli/application/launch/finalize_launch.py``
- ``src/scc_cli/commands/launch/flow.py``
- ``src/scc_cli/commands/worktree/worktree_commands.py``
- ``tests/test_cli.py``
- ``tests/test_integration.py``

## Expected Output

- ``src/scc_cli/commands/launch/flow.py``
- ``src/scc_cli/commands/worktree/worktree_commands.py``
- ``tests/test_cli.py``
- ``tests/test_integration.py``

## Verification

- Focused entrypoint coverage proves both live paths use the shared builder/finalizer and preserve runtime-stopped behavior on blocked launches.
- `uv run pytest --rootdir "$PWD" ./tests/test_cli.py ./tests/test_integration.py -q`

## Observability Impact

- Signals added/changed: both live entrypoints append the same canonical audit events and surface the same typed preflight failures.
- How a future agent inspects this: rerun `uv run pytest --rootdir "$PWD" ./tests/test_cli.py ./tests/test_integration.py -q` to see which entrypoint drifted.
- Failure state exposed: entrypoint-specific bypasses become visible as missing audit events or unexpected runtime starts.
