---
estimated_steps: 21
estimated_files: 8
skills_used: []
---

# T02: Wire Codex through DefaultAdapters and prove seam coexistence

Close the composition-root proof so Codex is reachable through the same provider-neutral seam as Claude without forcing higher layers to import adapter modules directly. This task also leaves behind loud diagnostics for future refactors by extending bootstrap, fake-adapter, and seam tests instead of relying on implicit wiring.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `src/scc_cli/bootstrap.py` composition root | stop and repair wiring there; do not bypass bootstrap with direct adapter imports | N/A | reject partial `DefaultAdapters` states that wire Codex in only some construction sites |
| focused seam tests | treat failing tests as the source of truth and localize the missing construction site before the full suite | N/A | update assertions only if the shared seam contract intentionally changes |

## Steps

1. Wire `CodexAgentProvider` into `src/scc_cli/bootstrap.py` and ensure `DefaultAdapters` can carry both `agent_provider` and `codex_agent_provider`, using a safe `| None = None` default for shared construction sites.
2. Update `tests/fakes/__init__.py` plus inline `DefaultAdapters(...)` construction sites in `tests/test_cli.py` and `tests/test_integration.py` so fake wiring stays coherent and callers do not silently break.
3. Add or extend focused assertions in `tests/test_bootstrap.py` and, if needed, `tests/test_application_start_session.py` or `tests/test_core_contracts.py` so the seam proves Codex can coexist with Claude through the same contracts.
4. Re-run `tests/test_import_boundaries.py` so only `bootstrap.py` remains allowed to import `scc_cli.adapters.*`.
5. Finish with the targeted seam/bootstrap tests and then the repo gate, fixing wiring regressions before handoff.

## Must-Haves

- [ ] `bootstrap.py` remains the only composition-root importer of `scc_cli.adapters.*` while exposing Codex through `DefaultAdapters`.
- [ ] All known `DefaultAdapters(...)` construction sites compile with the new field and use `FakeAgentProvider()` where appropriate.
- [ ] Focused tests fail clearly if Codex wiring disappears or if higher layers import adapter modules directly.
- [ ] The completed task leaves launch wiring easier to inspect under R001 instead of adding a hidden special case.

## Negative Tests

- **Malformed inputs**: inline `DefaultAdapters(...)` constructions that omit the new field are caught by focused tests instead of surfacing later at runtime.
- **Error paths**: `tests/test_import_boundaries.py` fails if application or command layers import `CodexAgentProvider` directly.
- **Boundary conditions**: both providers can coexist in `DefaultAdapters` while `agent_provider` remains the current seam entrypoint.

## Inputs

- ``src/scc_cli/adapters/codex_agent_provider.py``
- ``src/scc_cli/bootstrap.py``
- ``tests/test_bootstrap.py``
- ``tests/fakes/__init__.py``
- ``tests/test_cli.py``
- ``tests/test_integration.py``
- ``tests/test_application_start_session.py``
- ``tests/test_core_contracts.py``
- ``tests/test_import_boundaries.py``

## Expected Output

- ``src/scc_cli/bootstrap.py``
- ``tests/test_bootstrap.py``
- ``tests/fakes/__init__.py``
- ``tests/test_cli.py``
- ``tests/test_integration.py``

## Verification

uv run pytest tests/test_bootstrap.py tests/test_import_boundaries.py tests/test_application_start_session.py tests/test_core_contracts.py tests/test_cli.py tests/test_integration.py -q && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q

## Observability Impact

Bootstrap/import-boundary tests become the inspection surface for missing Codex wiring. A future agent can run the targeted pytest command to see whether the break is in composition-root wiring, fake-adapter construction sites, or architectural boundary enforcement.
