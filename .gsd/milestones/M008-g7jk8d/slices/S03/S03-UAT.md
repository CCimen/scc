# S03: Error quality, edge case hardening, and final verification — UAT

**Milestone:** M008-g7jk8d
**Written:** 2026-04-06T14:00:12.946Z

## UAT: S03 — Error quality, edge case hardening, and final verification

### Preconditions
- SCC installed and configured with `uv sync`
- At least one provider (Claude or Codex) configured
- Test suite baseline from S02 (5008 tests passing)

---

### TC-01: Failed launch does not persist workspace preference
**Steps:**
1. Run `uv run pytest tests/test_workspace_provider_persistence.py::TestFailedLaunchGuard -v`
2. Verify all tests pass — confirms `set_workspace_last_used_provider()` is NOT called when `finalize_launch()` raises
3. Verify call ordering test proves preference write happens AFTER successful launch

**Expected:** 3 tests pass. Failed and cancelled launches do not write workspace provider preference.

---

### TC-02: KEEP_EXISTING path writes workspace preference consistently
**Steps:**
1. Run `uv run pytest tests/test_workspace_provider_persistence.py::TestKeepExistingConsistency -v`
2. Verify KEEP_EXISTING conflict resolution path writes workspace preference via both flow.py start and dashboard resume

**Expected:** 2 tests pass. Both paths write workspace preference identically.

---

### TC-03: Ask mode with workspace_last_used preselection
**Steps:**
1. Run `uv run pytest tests/test_workspace_provider_persistence.py::TestAskPreselection -v`
2. Verify: ask mode with workspace_last_used='codex' when codex is connected → codex preselected as default
3. Verify: ask mode with workspace_last_used='codex' when codex NOT connected → no preselection
4. Verify: ask mode with no workspace_last_used → no preselection

**Expected:** 5 tests pass covering all preselection combinations.

---

### TC-04: Resume after auth volume deletion
**Steps:**
1. Run `uv run pytest tests/test_resume_after_drift.py::TestResumeWithDeletedAuth -v`
2. Verify session with provider_id='codex' stays on codex when auth is missing — triggers auth bootstrap, does not silently switch to Claude

**Expected:** 2 tests pass. Provider identity preserved during resume.

---

### TC-05: Resume after image removal
**Steps:**
1. Run `uv run pytest tests/test_resume_after_drift.py::TestResumeWithRemovedImage -v`
2. Verify interactive mode triggers auto-build
3. Verify non-interactive mode fails with exact `scc provider build-image codex` command in error

**Expected:** 2 tests pass. Image missing produces actionable guidance.

---

### TC-06: Explicit --provider override during resume
**Steps:**
1. Run `uv run pytest tests/test_resume_after_drift.py::TestExplicitProviderOverride -v`
2. Verify explicit --provider claude overrides resume's saved provider_id='codex'

**Expected:** 1 test passes. CLI flag takes precedence over session record.

---

### TC-07: Provider blocked by team policy during resume
**Steps:**
1. Run `uv run pytest tests/test_resume_after_drift.py::TestProviderBlockedByPolicy -v`
2. Verify ProviderNotAllowedError raised when saved provider is no longer in allowed_providers

**Expected:** 1 test passes with correct error type.

---

### TC-08: Legacy session with None provider_id
**Steps:**
1. Run `uv run pytest tests/test_resume_after_drift.py::TestLegacyNoneProviderId -v`
2. Verify session with provider_id=None falls back to claude per D032

**Expected:** 2 tests pass. Legacy sessions handled gracefully.

---

### TC-09: Auth bootstrap exception wrapping
**Steps:**
1. Run `uv run pytest tests/test_resume_after_drift.py::TestAuthBootstrapExceptionWrapping -v`
2. Verify OSError, FileNotFoundError, TimeoutExpired from bootstrap_auth() are wrapped in ProviderNotReadyError
3. Verify already-typed ProviderNotReadyError passes through unchanged (no double-wrapping)

**Expected:** 5 tests pass. Raw exceptions become actionable domain errors.

---

### TC-10: Setup idempotency — re-run with connected providers
**Steps:**
1. Run `uv run pytest tests/test_setup_idempotency.py -v`
2. Verify: re-run when Claude connected, Codex not → only Codex prompt appears
3. Verify: re-run when both connected → provider connection skipped entirely
4. Verify: re-run when none connected → both prompts appear

**Expected:** 16 tests pass. Setup detects existing state correctly.

---

### TC-11: Error message quality — all typed errors
**Steps:**
1. Run `uv run pytest tests/test_error_message_quality.py -v`
2. Verify ProviderNotReadyError messages include 'scc' command guidance
3. Verify InvalidProviderError lists valid provider options
4. Verify ProviderImageMissingError includes exact build command
5. Verify SandboxLaunchError includes stderr context
6. Verify doctor check failures wrap Docker errors with SCC context
7. Verify exit code consistency across error hierarchy

**Expected:** 51 tests pass. All error messages are actionable with SCC-specific guidance.

---

### TC-12: Full regression gate
**Steps:**
1. Run `uv run ruff check`
2. Run `uv run mypy src/scc_cli`
3. Run `uv run pytest -q`

**Expected:**
- ruff: 0 errors
- mypy: 303 files, 0 issues
- pytest: ≥5114 passed, 23 skipped, 2 xfailed, 0 failures
