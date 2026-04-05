---
id: T02
parent: S03
milestone: M006-d622bc
key_files:
  - src/scc_cli/commands/launch/render.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/sandbox.py
  - src/scc_cli/doctor/render.py
  - tests/test_provider_branding.py
key_decisions:
  - Doctor render uses deferred import for get_provider_display_name to avoid top-level cross-module coupling
  - sandbox.py receives display_name string rather than provider_id to keep it decoupled from provider_resolution
duration: 
verification_result: passed
completed_at: 2026-04-05T00:16:49.376Z
blocker_discovered: false
---

# T02: Added display_name parameter to show_launch_panel(), show_launch_context_panel(), and render_doctor_results(); threaded resolved provider at all call sites

**Added display_name parameter to show_launch_panel(), show_launch_context_panel(), and render_doctor_results(); threaded resolved provider at all call sites**

## What Happened

Added display_name/provider_id parameters to the three render functions with backward-compatible defaults. Threaded get_provider_display_name() at all launch flow call sites (flow.py, flow_interactive.py, sandbox.py). Doctor render uses deferred import. 7 new tests verify panel titles and doctor summary adapt to different providers.

## Verification

17 tests pass in test_provider_branding.py. Ruff check clean on all 5 source files. Mypy clean on all 5 source files. Slice-level ruff/mypy on provider_resolution, branding, theme also clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_branding.py -v --no-cov` | 0 | ✅ pass | 140ms |
| 2 | `uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py` | 0 | ✅ pass | 300ms |
| 3 | `uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/commands/launch/flow.py src/scc_cli/commands/launch/flow_interactive.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/doctor/render.py` | 0 | ✅ pass | 500ms |

## Deviations

sandbox.py receives display_name as string rather than provider_id to avoid widening the function's dependency surface. Doctor render call sites in admin.py and settings.py not modified — default falls back to claude.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/render.py`
- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/commands/launch/sandbox.py`
- `src/scc_cli/doctor/render.py`
- `tests/test_provider_branding.py`
