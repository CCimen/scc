---
estimated_steps: 13
estimated_files: 4
skills_used: []
---

# T03: Setup idempotency and error message quality audit

**Setup idempotency:**
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

## Inputs

- `src/scc_cli/commands/launch/provider_choice.py`

## Expected Output

- `tests/test_error_message_quality.py`
- `tests/test_setup_idempotency.py`

## Verification

uv run pytest tests/test_error_message_quality.py tests/test_setup_idempotency.py -v && uv run ruff check
