---
estimated_steps: 17
estimated_files: 1
skills_used: []
---

# T05: Structural guardrail test, provider metadata source verification, and full suite gate

**Structural anti-drift guardrail (main maintainability guard of M008):**

Create tests/test_launch_preflight_guardrail.py with a structural test that scans the five launch entry-point files for inline preflight orchestration. The test should:
1. Parse each of the five files (flow.py, flow_interactive.py, worktree_commands.py, orchestrator_handlers.py ×2 functions) using tokenize or AST
2. Assert that none of them contain direct calls to `ensure_provider_image()`, `ensure_provider_auth()`, `choose_start_provider()`, or `resolve_active_provider()` — all of which should now flow through preflight.py
3. Assert that each file imports from `commands.launch.preflight`
4. This is a mechanical guardrail — if someone adds inline preflight back to one of the five sites, this test fails immediately.

Pattern: similar to test_no_claude_constants_in_core.py and test_import_boundaries.py — structural scanning, not behavioral mocking.

**Single provider metadata source verification:**
5. Add a guardrail test (in the same file or test_docs_truthfulness.py) verifying that image refs, display names, and adapter lookup all resolve from one source — the ProviderRuntimeSpec registry (core/provider_registry.py) and _PROVIDER_DISPATCH (dependencies.py). The test scans for hardcoded image refs or display name strings outside of those two canonical locations plus the adapter modules that own them.
6. This catches the exact consistency bug M008 is cleaning: scattered provider constants that drift.

**Full verification gate:**
7. ruff check on all touched files
8. mypy on all touched source files
9. Focused pytest on characterization, preflight, and guardrail tests
10. Full pytest suite (must be >= 4820 with zero regressions)
11. Verify via rg that start_claude no longer appears in the codebase
12. Verify preflight.py has no imports from core/ except types/errors (D046 architecture guard)

## Inputs

- `src/scc_cli/commands/launch/preflight.py`
- `src/scc_cli/core/provider_registry.py`
- `src/scc_cli/commands/launch/dependencies.py`

## Expected Output

- `tests/test_launch_preflight_guardrail.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
