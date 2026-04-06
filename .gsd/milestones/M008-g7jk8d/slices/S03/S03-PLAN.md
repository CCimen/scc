# S03: Error quality, edge case hardening, and final verification

**Goal:** Edge cases don't produce confusing behavior. Error messages are truthful and actionable. Resume-after-drift is resilient. Setup is idempotent. Residual legacy code documented. Smoke checks verify cross-flow product behavior.
**Demo:** After this: Error messages give actionable SCC guidance. Edge cases (both providers connected, none connected, explicit --provider with missing auth, failed launch doesn't write workspace preference) handled correctly.

## Tasks
- [x] **T01: Added 17 tests verifying workspace provider persistence edge cases: failed launch guard, KEEP_EXISTING consistency, and ask+last-used preselection** — **Failed launch guard:**
1. Verify set_workspace_last_used_provider() is called ONLY after finalize_launch() succeeds in all five sites (via preflight module from S01). If finalize_launch raises, the preference must NOT be written.
2. Verify the KEEP_EXISTING conflict path also writes workspace preference consistently across flow.py start(), run_start_wizard_flow(), dashboard _handle_worktree_start(), and dashboard _handle_session_resume(). All four should behave the same.

**Ask + workspace_last_used preselection:**
3. Test: global preference='ask', workspace_last_used='codex' → chooser appears (ask suppresses auto-select), BUT codex is preselected as default.
4. Verify _resolve_prompt_default() in provider_choice.py correctly returns workspace_last_used when it's in connected_allowed and candidates.
5. Test: global preference='ask', workspace_last_used='codex', codex NOT connected → chooser appears, no preselection.
6. Test: global preference='ask', no workspace_last_used → chooser appears with no preselection.

**Write edge case tests:**
- Failed launch (finalize_launch raises) → workspace preference NOT updated
- Cancelled launch → workspace preference NOT updated
- Successful launch → workspace preference written
- KEEP_EXISTING via start → preference written
- KEEP_EXISTING via dashboard resume → preference written (same behavior)
  - Estimate: 30min
  - Files: tests/test_workspace_provider_persistence.py, tests/test_start_provider_choice.py
  - Verify: uv run pytest tests/test_workspace_provider_persistence.py tests/test_start_provider_choice.py -v
- [x] **T02: Added 22 resume-after-drift edge case tests and auth bootstrap exception wrapping in ensure_provider_auth** — **Resume-after-drift tests:**
1. Session exists with provider_id='codex', but Codex auth volume was deleted → resume triggers auth bootstrap (not silent switch to Claude)
2. Session exists with provider_id='codex', but Codex image was removed → resume triggers image auto-build in interactive mode, fails with build command in non-interactive
3. Session exists with provider_id='codex', explicit --provider claude → CLI flag overrides resume provider (intentional switch)
4. Session exists with provider_id='codex', codex no longer in allowed_providers → ProviderNotAllowedError
5. Session exists with provider_id=None (legacy) → falls back to claude at read boundary per D032
6. Explicit --provider codex with missing auth in non-interactive mode → typed error with actionable guidance, NOT a prompt or silent switch

**Auth bootstrap callback failure:**
7. Test: Codex auth bootstrap_auth() raises because browser callback port is unavailable → SCC catches and produces a clean ProviderNotReadyError with guidance ('run scc start interactively to complete browser sign-in'), not a raw socket/server error.
8. If the current code doesn't handle this, add a try/except in ensure_provider_auth or in the Codex adapter's bootstrap_auth() to wrap the failure.

All tests go through the shared preflight module from S01.
  - Estimate: 35min
  - Files: tests/test_resume_after_drift.py, src/scc_cli/commands/launch/auth_bootstrap.py
  - Verify: uv run pytest tests/test_resume_after_drift.py -v
- [ ] **T03: Setup idempotency and error message quality audit** — **Setup idempotency:**
1. Test: re-run scc setup when Claude is already connected but Codex is not → setup should detect Claude is present and only offer Codex sign-in, not start from scratch.
2. Verify _run_provider_onboarding() in setup.py checks collect_provider_readiness() and only shows connection prompts for providers whose status is not 'present'.
3. If the current code re-asks all questions, fix _prompt_provider_connections() to skip already-connected providers.
4. Test: re-run scc setup when both providers are connected → setup should skip provider connections entirely and only show preference prompt if needed.

**Error message quality audit:**
5. Review and improve error messages for:
   - ProviderNotReadyError (Docker missing, image missing, auth missing) — actionable?
   - InvalidProviderError (unknown provider) — lists valid options?
   - Non-interactive launch failures — tells user exact command to fix?
   - Doctor check failures — wraps Docker errors with SCC context?
6. For each weak message: fix the text, add a test asserting the improved message.
7. Ensure no raw Docker error leaks through when SCC can explain better.
  - Estimate: 30min
  - Files: src/scc_cli/setup.py, src/scc_cli/core/errors.py, tests/test_error_message_quality.py, tests/test_setup_idempotency.py
  - Verify: uv run pytest tests/test_error_message_quality.py tests/test_setup_idempotency.py -v && uv run ruff check
- [ ] **T04: Document residual legacy code, Docker-backed smoke checks, and final verification** — **Documentation:**
1. Add a brief comment block at the top of docker/core.py, docker/launch.py, docker/sandbox.py, adapters/docker_sandbox_runtime.py documenting these as the legacy Docker Desktop sandbox path — retained for users who have Docker Desktop with 'docker sandbox run' support, not active for OCI launches.
2. List all residual Docker Desktop code locations for the milestone summary.

**Docker-backed smoke checks (where Docker is available):**
3. If Docker is available in the test environment, run one smoke flow per provider:
   a. Delete the provider image → run through preflight → verify auto-build triggers (interactive)
   b. Verify non-interactive mode fails with the exact build command in the error
   c. Delete the auth volume → run through preflight → verify auth bootstrap triggers
   These are integration-level checks. If Docker is not available, document as manual verification items.

**Final verification gate:**
4. uv run ruff check — clean
5. uv run mypy src/scc_cli — clean
6. uv run pytest -q — >= 4820 passed, zero regressions
7. Summarize all findings ordered by severity, residual risks, and legacy code boundaries
8. If no major findings remain, state that explicitly with a brief change summary
  - Estimate: 25min
  - Files: src/scc_cli/docker/core.py, src/scc_cli/docker/launch.py, src/scc_cli/docker/sandbox.py, src/scc_cli/adapters/docker_sandbox_runtime.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
