# S02: Setup three-tier consistency and final verification

**Goal:** Make _render_provider_status use _three_tier_status() so setup shows consistent three-tier readiness in both the onboarding status panel and the completion summary.
**Demo:** After this: setup.py _render_provider_status shows launch-ready/auth cache present/image available/sign-in needed. Same as show_setup_complete.

## Tasks
- [x] **T01: Replaced inline two-tier status in _render_provider_status with _three_tier_status() and added provider preference hints to setup completion next-steps** — Steps:
1. In setup.py _render_provider_status(), replace the inline two-tier status logic with _three_tier_status(provider_id, state).
2. Update any tests that assert on the old two-tier wording in _render_provider_status output.
3. Add provider preference hint to setup completion: show 'scc provider show' / 'scc provider set ask|claude|codex' in the next-steps section (reviewer item #5 — small, high UX value).
4. Run full exit gate: ruff, mypy, pytest.
  - Estimate: 15min
  - Files: src/scc_cli/setup.py, tests/test_cli_setup.py, tests/test_auth_vocabulary_guardrail.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
