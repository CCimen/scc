---
estimated_steps: 17
estimated_files: 6
skills_used:
  - karpathy-guidelines
---

# T01: Reproduce the M002 exit gate and only fix directly implicated drift

**Expected skills:** `karpathy-guidelines`.

Re-run the three milestone-exit commands from the active worktree root in the documented order: `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest --rootdir "$PWD" -q`. If every command already passes, do not churn code; capture the proof cleanly in the task summary and identify that no source edits were required. If any gate fails, make the smallest maintainability-first change set needed in the exact failing files, keep fixes local to the implicated seam, and rerun the full three-command contract before handoff.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| repo toolchain invoked through `uv run` | stop on the first failing command, localize the failing files, and fix only that drift before re-running the full gate | re-run the same command once to confirm a real timeout before widening the investigation | treat unexpected tool output as a gate failure and capture the raw command/stderr in the task summary |
| recently touched launch/support seams | keep changes inside the files directly named by the failing gate instead of broad cleanup | N/A | use the focused tests named by the failure only to localize the bug, then return to the full three-command gate |

## Negative Tests

- **Error paths**: at least one failing gate is reproduced exactly before changing code, unless the gate is already green in the fresh task context.
- **Boundary conditions**: a green worktree results in no opportunistic refactors; a red worktree is not considered fixed until all three exit-gate commands pass again.

## Steps

1. Run the three milestone-exit commands from `.gsd/worktrees/M002` and record which one fails first, if any.
2. If a command fails, inspect only the files named by that failure and land the smallest maintainable fix set needed to clear it.
3. Re-run the full three-command gate, not just the previously failing command, and capture the final command results for handoff.

## Must-Haves

- [ ] The exact milestone-exit contract is reproduced from the active worktree root.
- [ ] Any fix stays local to the failing files and does not reopen already-stable launch/provider seams without evidence.
- [ ] The task summary records the final gate commands and whether code changes were or were not required.

## Inputs

- `pyproject.toml`
- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/wizard_resume.py`
- `src/scc_cli/application/support_bundle.py`
- `tests/test_launch_flow_hotspots.py`
- `tests/test_support_bundle.py`

## Expected Output

- `.gsd/milestones/M002/slices/S06/tasks/T01-SUMMARY.md`
- `pyproject.toml`
- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/wizard_resume.py`
- `src/scc_cli/application/support_bundle.py`
- `tests/test_launch_flow_hotspots.py`
- `tests/test_support_bundle.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q

## Observability Impact

Capture the exact pass/fail command outputs in the task summary so a future agent can see which gate regressed and whether source edits were actually necessary.
