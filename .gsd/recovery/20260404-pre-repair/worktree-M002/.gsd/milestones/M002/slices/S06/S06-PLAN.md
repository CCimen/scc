# S06: Restore milestone-exit contract gate

**Goal:** Prove the active M002 worktree satisfies the milestone-exit contract again and convert that proof into the milestone-validation artifact needed to close M002 without reopening provider-neutral launch work.
**Demo:** After this: After this slice, `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest --rootdir "$PWD" -q` all pass again in the active worktree, so M002 can be revalidated and sealed.

## Tasks
- [x] **T01: Reproduced the M002 exit gate from the active worktree and confirmed no source edits were required.** — Re-run the three milestone-exit commands from the active worktree root in the documented order: `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest --rootdir "$PWD" -q`. If every command already passes, do not churn code; capture the proof cleanly in the task summary and identify that no source edits were required. If any gate fails, make the smallest maintainability-first change set needed in the exact failing files, keep fixes local to the implicated seam, and rerun the full three-command contract before handoff.

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
  - Estimate: 45m
  - Files: pyproject.toml, src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/wizard_resume.py, src/scc_cli/application/support_bundle.py, tests/test_launch_flow_hotspots.py, tests/test_support_bundle.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
- [x] **T02: Wrote an evidence-backed M002 validation artifact with a `pass` verdict tied to the restored gate, slice delivery audit, and R001/D010 proof.** — Use the T01 gate proof plus the existing milestone roadmap, decisions, requirements, and slice summaries to validate M002 honestly. Run `gsd_validate_milestone` with a `pass` verdict only if the restored exit gate, roadmap success criteria, slice delivery audit, and R001/D010 maintainability evidence all line up; otherwise record `needs-attention` or `needs-remediation` with concrete rationale. Keep the validation artifact crisp and evidence-backed so milestone completion can follow immediately without re-reading the whole milestone history.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| T01 gate proof in `.gsd/milestones/M002/slices/S06/tasks/T01-SUMMARY.md` | do not issue a pass verdict; rerun the missing gate or mark validation incomplete | N/A | treat partial or contradictory proof as a validation blocker and say so explicitly |
| milestone planning artifacts under `.gsd/milestones/M002/` and `.gsd/*.md` | stop and name the missing artifact instead of inventing evidence | N/A | prefer `needs-attention` over a guessed pass if the source artifacts conflict |

## Negative Tests

- **Error paths**: missing T01 proof, missing roadmap context, or a failing gate command prevents a `pass` validation verdict.
- **Boundary conditions**: if the worktree is already green, validation still cites the exact commands and current worktree root rather than stale proof from an older slice.

## Steps

1. Read the T01 summary and the current milestone roadmap/requirements/decisions artifacts and map them to the milestone validation checklist.
2. Run `gsd_validate_milestone` for `M002` with a verdict that matches the evidence on disk, including the slice delivery audit and requirement coverage sections.
3. Confirm `.gsd/milestones/M002/M002-VALIDATION.md` exists and that its rationale cites the restored exit gate plus R001/D010 proof.

## Must-Haves

- [ ] The validation verdict is evidence-backed and references the restored `ruff`/`mypy`/`pytest` gate from the active worktree.
- [ ] The validation artifact audits slice delivery honestly instead of assuming the roadmap was delivered.
- [ ] Requirement coverage explicitly addresses R001 and its M002/S05 validation proof before milestone closure.
  - Estimate: 35m
  - Files: .gsd/milestones/M002/M002-CONTEXT.md, .gsd/milestones/M002/M002-ROADMAP.md, .gsd/REQUIREMENTS.md, .gsd/DECISIONS.md, .gsd/milestones/M002/slices/S05/S05-SUMMARY.md
  - Verify: test -f .gsd/milestones/M002/M002-VALIDATION.md && rg -n "pass|needs-attention|needs-remediation" .gsd/milestones/M002/M002-VALIDATION.md
