# S01: Unify all launch paths on shared preflight and fix auth bootstrap gap

**Goal:** Eliminate the last two launch sites (flow.py, flow_interactive.py) that bypass the shared preflight readiness path. Fix the auth bootstrap gap where ensure_launch_ready shows the notice but never calls bootstrap_auth(). Centralize auth messaging so it lives in exactly one module.
**Demo:** After this: All five launch sites call collect_launch_readiness + ensure_launch_ready. ensure_launch_ready actually calls bootstrap_auth(). auth_bootstrap.py eliminated or trivial. Auth messaging in one place.

## Tasks
- [x] **T01: ensure_launch_ready() now calls provider.bootstrap_auth() after showing the auth notice, closing the silent auth gap in dashboard and worktree launch paths** — The current ensure_launch_ready() in preflight.py shows the auth bootstrap notice via show_notice() but never calls provider.bootstrap_auth(). This means dashboard and worktree paths that use ensure_launch_ready have a silent auth gap — the notice appears but the browser sign-in never triggers.

Steps:
1. Add an `adapters` parameter to ensure_launch_ready() so it can access the provider adapter.
2. In _ensure_auth(), after showing the notice in interactive mode, call the provider adapter's bootstrap_auth() method (same as auth_bootstrap.py does).
3. Wrap the bootstrap_auth() call with the same exception handling as auth_bootstrap.py: ProviderNotReadyError passes through, other exceptions get wrapped.
4. Update all existing callers (worktree_commands.py, orchestrator_handlers.py) to pass adapters.
5. Add a test proving bootstrap_auth() is called when auth is missing.
6. Update existing ensure_launch_ready tests for the new parameter.
  - Estimate: 25min
  - Files: src/scc_cli/commands/launch/preflight.py, src/scc_cli/commands/worktree/worktree_commands.py, src/scc_cli/ui/dashboard/orchestrator_handlers.py, tests/test_launch_preflight.py
  - Verify: uv run pytest tests/test_launch_preflight.py -v && uv run pytest tests/test_launch_preflight_guardrail.py -v && uv run ruff check
- [ ] **T02: Migrate flow.py and flow_interactive.py to shared preflight readiness path** — Replace the inline ensure_provider_image + ensure_provider_auth calls in flow.py start() and flow_interactive.py run_start_wizard_flow() with collect_launch_readiness() + ensure_launch_ready() from preflight.py.

Key ordering constraint (D048): flow.py calls ensure_provider_image/auth AFTER prepare_live_start_plan and conflict_resolution. But the actual dependency is thin — ensure_provider_auth only uses plan.resume (to skip on resume) and dependencies.agent_provider (for auth_check/bootstrap_auth). For non-resume fresh starts, we can call collect_launch_readiness + ensure_launch_ready BEFORE plan construction, same as worktree/dashboard. For resume, the readiness check should skip auth bootstrap since auth is already present from the original session.

Steps:
1. In flow.py start(), move the readiness check to after provider resolution but before plan construction. Remove the ensure_provider_image and ensure_provider_auth calls after conflict resolution.
2. For the resume path: collect_launch_readiness still runs (to check image), but the resume flag means auth bootstrap is unnecessary — the session already authenticated. Add a `resume` parameter to ensure_launch_ready or handle this in the readiness model.
3. Same migration in flow_interactive.py run_start_wizard_flow().
4. Remove the ensure_provider_image and ensure_provider_auth imports from flow.py and flow_interactive.py.
5. Fix all affected tests.
6. Add flow.py and flow_interactive.py to the anti-drift guardrail if they aren't already there for the image/auth functions.
  - Estimate: 30min
  - Files: src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/flow_interactive.py, src/scc_cli/commands/launch/preflight.py, tests/test_launch_preflight_guardrail.py, tests/test_start_dryrun.py, tests/test_integration.py
  - Verify: uv run pytest tests/test_launch_preflight_guardrail.py tests/test_start_dryrun.py tests/test_integration.py -v && grep -rn ensure_provider_image src/scc_cli/commands/launch/flow.py && grep -rn ensure_provider_auth src/scc_cli/commands/launch/flow.py
- [ ] **T03: Centralize auth messaging and eliminate auth_bootstrap.py duplication** — After T01 and T02, auth_bootstrap.py's ensure_provider_auth is no longer called by any launch site. The auth messaging (non-interactive error text, interactive notice text) is duplicated between auth_bootstrap.py and preflight.py._ensure_auth.

Steps:
1. Verify no callers of ensure_provider_auth remain outside tests: grep -rn 'ensure_provider_auth' src/scc_cli/ should return only the definition and test imports.
2. If no callers remain, delete auth_bootstrap.py or reduce it to a deprecated redirect.
3. If callers remain (e.g. some edge path), make auth_bootstrap.ensure_provider_auth delegate to preflight._ensure_auth.
4. Ensure the canonical auth messaging (error text, notice text) lives only in preflight.py._ensure_auth.
5. Update import boundary tests and allowlists if auth_bootstrap.py is deleted.
6. Run targeted tests and full suite.
  - Estimate: 15min
  - Files: src/scc_cli/commands/launch/auth_bootstrap.py, src/scc_cli/commands/launch/preflight.py, tests/test_launch_preflight.py, tests/test_import_boundaries.py
  - Verify: grep -rn 'from.*auth_bootstrap' src/scc_cli/ | grep -v __pycache__ && uv run pytest -q
