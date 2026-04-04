---
id: T03
parent: S05
milestone: M002
key_files:
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_types.py
  - src/scc_cli/commands/launch/wizard_resume.py
  - tests/test_launch_flow_hotspots.py
  - tests/test_start_wizard_quick_resume_flow.py
  - tests/test_start_wizard_workspace_quick_resume.py
  - tests/test_start_cross_team_resume_prompt.py
  - tests/test_quick_resume_behavior.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - D009: keep quick-resume and workspace-resume orchestration in `src/scc_cli/commands/launch/wizard_resume.py` behind explicit `WizardResumeContext` inputs and a hotspot guardrail test.
  - Record the worktree verification runner gotcha in `.gsd/KNOWLEDGE.md` so future tasks use direct worktree `bash` for path-sensitive checks.
duration: 
verification_result: passed
completed_at: 2026-04-03T21:36:16.260Z
blocker_discovered: false
---

# T03: Extracted launch-wizard quick-resume and workspace-resume flows into typed helpers with hotspot guardrails.

**Extracted launch-wizard quick-resume and workspace-resume flows into typed helpers with hotspot guardrails.**

## What Happened

Extracted the top-level quick-resume and workspace-resume branches out of `interactive_start` into a new `src/scc_cli/commands/launch/wizard_resume.py` helper module. Added typed resume context/result aliases in `flow_types.py`, updated `flow.py` to delegate those branches instead of keeping nested closures, and preserved existing `--team` over `selected_profile` precedence plus back/cancel/new-session/team-switch behavior. Added `tests/test_launch_flow_hotspots.py` to guard the seam mechanically and updated the existing quick-resume/cross-team characterization tests to patch the extracted helper module’s recent-context loader.

## Verification

Focused quick-resume/workspace-resume characterization tests passed after the extraction, `uv run mypy src/scc_cli` passed, and the full `uv run pytest --rootdir "$PWD" -q` suite passed from the worktree checkout. Direct worktree `uv run ruff check` was used as the authoritative lint signal; path-sensitive background/parallel runner variants that resolved against the synced repo root were discarded and documented in `.gsd/KNOWLEDGE.md`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir "$PWD" "$PWD/tests/test_launch_flow_hotspots.py" "$PWD/tests/test_start_wizard_quick_resume_flow.py" "$PWD/tests/test_start_wizard_workspace_quick_resume.py" "$PWD/tests/test_start_cross_team_resume_prompt.py" -q` | 0 | ✅ pass | 1040ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 39900ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 41000ms |

## Deviations

None.

## Known Issues

No product/runtime issues found. Some parallel/background verification runners can resolve against the synced repo root instead of the active worktree and produce false negatives for worktree-local files.

## Files Created/Modified

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_types.py`
- `src/scc_cli/commands/launch/wizard_resume.py`
- `tests/test_launch_flow_hotspots.py`
- `tests/test_start_wizard_quick_resume_flow.py`
- `tests/test_start_wizard_workspace_quick_resume.py`
- `tests/test_start_cross_team_resume_prompt.py`
- `tests/test_quick_resume_behavior.py`
- `.gsd/KNOWLEDGE.md`
