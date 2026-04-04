# S06: Restore milestone-exit contract gate — UAT

**Milestone:** M002
**Written:** 2026-04-03T22:17:27.782Z

**Milestone:** M002
**Written:** 2026-04-03

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S06 shipped no new runtime behavior; it restored milestone-closeout proof by rerunning the exact repo gate from the active worktree and writing the validation artifact required for milestone closure.

## Preconditions

- Work from `/Users/ccimen/dev/sccorj/scc-sync-1.7.3/.gsd/worktrees/M002`.
- The Python toolchain is available through `uv run`.
- T01 and T02 outputs exist under `.gsd/milestones/M002/slices/S06/tasks/`.

## Smoke Test

Run `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q` from the active worktree root. The smoke test passes if all three commands succeed without editing source files.

## Test Cases

### 1. Reproduce the M002 milestone-exit gate from the active worktree

1. From the active worktree root, run `uv run ruff check`.
2. Run `uv run mypy src/scc_cli`.
3. Run `uv run pytest --rootdir "$PWD" -q`.
4. **Expected:** Ruff reports `All checks passed!`, mypy reports `Success: no issues found in 242 source files`, and pytest exits 0 with the current green suite (`3281 passed, 23 skipped, 4 xfailed` in the verified run).

### 2. Confirm the milestone validation artifact exists and names a verdict

1. Run `test -f .gsd/milestones/M002/M002-VALIDATION.md`.
2. Run `rg -n "pass|needs-attention|needs-remediation" .gsd/milestones/M002/M002-VALIDATION.md`.
3. Open `.gsd/milestones/M002/M002-VALIDATION.md` and confirm it cites the restored `ruff` / `mypy` / `pytest` gate from the active M002 worktree.
4. **Expected:** The file exists, includes `verdict: pass`, and ties that verdict to the current worktree gate plus the S01-S06 delivery audit.

## Edge Cases

### Validation rerun without code churn

1. Re-run the full gate and validation-file check without changing any source files.
2. **Expected:** The worktree remains green and no opportunistic refactor or repair is needed to reproduce the milestone-closeout proof.

## Failure Signals

- Any of `uv run ruff check`, `uv run mypy src/scc_cli`, or `uv run pytest --rootdir "$PWD" -q` exits non-zero.
- `.gsd/milestones/M002/M002-VALIDATION.md` is missing or lacks a verdict line.
- The validation artifact cites stale or contradictory evidence instead of the current active-worktree gate.

## Not Proven By This UAT

- That `gsd_complete_milestone` has already been run for M002.
- That roadmap reassessment has already registered M003 as the next active milestone; this UAT only proves the closeout gate and validation artifact are ready for those steps.

## Notes for Tester

Use the active worktree root, not the synced repo root, when reproducing the gate. The authoritative closeout evidence is the current worktree gate plus `.gsd/milestones/M002/M002-VALIDATION.md`; earlier summaries are supporting context, not the primary proof.
