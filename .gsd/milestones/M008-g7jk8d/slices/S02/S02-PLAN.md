# S02: Auth/readiness wording truthfulness, Docker Desktop cleanup, and adapter dispatch consolidation

**Goal:** Auth wording is truthful with three-tier distinction. Stale Docker Desktop references removed from active paths. Container lifecycle commands are consistent. Provider adapter dispatch consolidated.
**Demo:** After this: Doctor, setup summary, and choose-provider screen use consistent auth vocabulary. No 'Docker Desktop' in active error paths. Provider adapter dispatch uses shared lookup.

## Tasks
- [x] **T01: Fixed 6 misleading auth-status strings across provider_choice.py, setup.py, and doctor checks; added 5-test guardrail preventing vocabulary regression** — Audit every user-facing string that describes provider readiness:

1. Doctor output (checks/environment.py, render.py) — currently uses 'auth cache present'
2. Setup summary (setup.py _render_setup_summary, _render_provider_status) — uses what vocabulary?
3. Provider choice prompt (provider_choice.py prompt_for_provider_choice) — uses 'connected' vs 'sign-in required'
4. Auth bootstrap (auth_bootstrap.py) — uses 'auth cache is missing'

Establish canonical three-tier vocabulary:
- 'auth cache present' — when we only check file existence (not 'connected')
- 'image available' — when provider image exists locally (not 'ready')
- 'launch-ready' — only when BOTH auth + image are present

Fix mismatches. In particular:
- provider_choice.py: change 'connected' to 'auth cache present' and 'sign-in required' to 'sign-in needed'
- setup summary: distinguish auth vs image in the completion display
- doctor: keep current vocabulary (already truthful) but add image check alongside auth check in grouped output

Add guardrail test scanning for banned terms ('connected' meaning auth cache, standalone 'ready' meaning only one tier).
  - Estimate: 35min
  - Files: src/scc_cli/commands/launch/provider_choice.py, src/scc_cli/setup.py, src/scc_cli/doctor/checks/environment.py, tests/test_auth_vocabulary_guardrail.py
  - Verify: uv run pytest tests/test_auth_vocabulary_guardrail.py -v && uv run ruff check
- [x] **T02: Removed Docker Desktop from active user-facing paths; added lifecycle inventory consistency and Docker Desktop boundary guardrails** — Docker Desktop cleanup:
1. admin.py:480 — change 'Ensure Docker Desktop is running' to 'Ensure Docker is running'
2. container_commands.py:304 prune_cmd comment — reword to mention 'containers not created by SCC' rather than 'Docker Desktop'
3. Scan all remaining user-facing strings in commands/ for 'Docker Desktop' via rg — fix to 'Docker' or 'container runtime'
4. Keep Docker Desktop references ONLY in: docker/core.py, docker/launch.py, docker/sandbox.py, adapters/docker_sandbox_runtime.py, adapters/docker_runtime_probe.py, core/errors.py (typed error for Desktop-specific failures)

Lifecycle inventory consistency:
5. Verify scc list, scc stop, scc prune, scc status, dashboard container actions, and session resume all use docker.list_scc_containers() or its running variant as the SCC-managed inventory source
6. Check that stale/non-SCC containers (no scc labels) don't pollute the active inventory
7. Write a focused test verifying inventory consistency across command surfaces

Update test_docs_truthfulness.py with Docker Desktop boundary guardrail.
  - Estimate: 30min
  - Files: src/scc_cli/commands/admin.py, src/scc_cli/commands/worktree/container_commands.py, tests/test_docs_truthfulness.py, tests/test_lifecycle_inventory_consistency.py
  - Verify: uv run pytest tests/test_docs_truthfulness.py tests/test_lifecycle_inventory_consistency.py -v && uv run ruff check
- [x] **T03: Consolidated provider adapter dispatch into shared get_agent_provider() helper; verified init template branding and added 3 guardrail tests** — Provider adapter dispatch:
1. In provider_choice.py collect_provider_readiness(): the hardcoded adapters_by_provider dict maps provider_id to adapter fields. Extract into a shared helper or reuse the _PROVIDER_DISPATCH pattern from dependencies.py.
2. In setup.py _run_provider_onboarding(): same hardcoded provider_map. Use the shared helper.
3. The goal: one dispatch surface for 'which adapter field is the AgentProvider for provider X' — consumed by dependencies.py, provider_choice.py, and setup.py.

Branding:
4. Verify init.py .scc.yaml template uses 'Sandboxed Coding CLI' per D045 (NOT 'Sandboxed Code CLI'). If it says 'Sandboxed Code CLI', that is the old D030 wording and must be corrected to match D045.
5. Add/update guardrail test verifying .scc.yaml template matches D045 product name.

Note: the live codebase already shows 'Sandboxed Coding CLI' in init.py line 73 — verify it's correct and add the test.
  - Estimate: 25min
  - Files: src/scc_cli/commands/launch/provider_choice.py, src/scc_cli/setup.py, src/scc_cli/commands/init.py, tests/test_docs_truthfulness.py
  - Verify: uv run pytest tests/test_docs_truthfulness.py tests/test_start_provider_choice.py -v && uv run ruff check && uv run mypy src/scc_cli/commands/launch/provider_choice.py src/scc_cli/setup.py
- [x] **T04: All 6 verification checks pass: ruff clean, mypy clean, 5008 tests (0 failures), no Docker Desktop in active paths, branding consistent** — Run full verification:
1. ruff check on all touched files
2. mypy on all touched source files
3. Focused pytest on guardrail, truthfulness, lifecycle, and provider choice tests
4. Full pytest suite (>= 4820 with zero regressions)
5. Verify via rg that no active user-facing string in commands/ contains 'Docker Desktop'
6. Verify branding consistency: rg 'Sandboxed Cod' src/scc_cli/ should show only 'Sandboxed Coding CLI'
  - Estimate: 10min
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
