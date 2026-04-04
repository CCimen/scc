---
estimated_steps: 17
estimated_files: 5
skills_used:
  - karpathy-guidelines
  - writing-clearly-and-concisely
---

# T02: Write the M002 milestone-validation artifact from the restored gate evidence

**Expected skills:** `karpathy-guidelines`, `writing-clearly-and-concisely`.

Use the T01 gate proof plus the existing milestone roadmap, decisions, requirements, and slice summaries to validate M002 honestly. Run `gsd_validate_milestone` with a `pass` verdict only if the restored exit gate, roadmap success criteria, slice delivery audit, and R001/D010 maintainability evidence all line up; otherwise record `needs-attention` or `needs-remediation` with concrete rationale. Keep the validation artifact crisp and evidence-backed so milestone completion can follow immediately without re-reading the whole milestone history.

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

## Inputs

- `.gsd/milestones/M002/M002-CONTEXT.md`
- `.gsd/milestones/M002/M002-ROADMAP.md`
- `.gsd/REQUIREMENTS.md`
- `.gsd/DECISIONS.md`
- `.gsd/milestones/M002/slices/S05/S05-SUMMARY.md`
- `.gsd/milestones/M002/slices/S06/tasks/T01-SUMMARY.md`

## Expected Output

- `.gsd/milestones/M002/M002-VALIDATION.md`
- `.gsd/milestones/M002/slices/S06/tasks/T02-SUMMARY.md`

## Verification

test -f .gsd/milestones/M002/M002-VALIDATION.md && rg -n "pass|needs-attention|needs-remediation" .gsd/milestones/M002/M002-VALIDATION.md

## Observability Impact

The validation artifact becomes the durable closeout surface: it must name the command proof, the verdict, and any remaining blocker clearly enough that milestone completion can proceed or stop without another exploratory pass.
