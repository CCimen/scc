---
estimated_steps: 5
estimated_files: 3
skills_used: []
---

# T01: Update _render_provider_status to use three-tier readiness and final verification

Steps:
1. In setup.py _render_provider_status(), replace the inline two-tier status logic with _three_tier_status(provider_id, state).
2. Update any tests that assert on the old two-tier wording in _render_provider_status output.
3. Add provider preference hint to setup completion: show 'scc provider show' / 'scc provider set ask|claude|codex' in the next-steps section (reviewer item #5 — small, high UX value).
4. Run full exit gate: ruff, mypy, pytest.

## Inputs

- `src/scc_cli/setup.py — _render_provider_status with two-tier, _three_tier_status helper`

## Expected Output

- `_render_provider_status using _three_tier_status`
- `Provider preference hint in setup completion next-steps`
- `Full suite green`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest -q
