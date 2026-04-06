---
id: T01
parent: S02
milestone: M009-xwi4bt
key_files:
  - src/scc_cli/setup.py
key_decisions:
  - Reused existing _three_tier_status() helper in _render_provider_status rather than duplicating logic
duration: 
verification_result: passed
completed_at: 2026-04-06T17:05:13.013Z
blocker_discovered: false
---

# T01: Replaced inline two-tier status in _render_provider_status with _three_tier_status() and added provider preference hints to setup completion next-steps

**Replaced inline two-tier status in _render_provider_status with _three_tier_status() and added provider preference hints to setup completion next-steps**

## What Happened

_render_provider_status() had inline two-tier logic ("auth cache present" / "sign-in needed") while show_setup_complete() already used the four-state _three_tier_status() helper. Replaced the inline logic with a call to _three_tier_status(provider_id, state) so both surfaces show consistent readiness vocabulary. Added scc provider show and scc provider set hints to the Get started next-steps block in show_setup_complete().

## Verification

Full exit gate green: uv run ruff check (0 issues), uv run mypy src/scc_cli (0 issues in 303 files), uv run pytest -q (5117 passed, 23 skipped, 2 xfailed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 11800ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8100ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 78600ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/setup.py`
