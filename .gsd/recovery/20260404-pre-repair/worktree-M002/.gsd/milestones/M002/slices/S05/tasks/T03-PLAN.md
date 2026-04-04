---
estimated_steps: 26
estimated_files: 5
skills_used:
  - karpathy-guidelines
---

# T03: Extract quick-resume and workspace-resume wizard subflows into typed helpers

**Expected skills:** `karpathy-guidelines`.

`interactive_start` is still the largest launch-flow hotspot in the repo. Split its quick-resume and workspace-resume subflows into explicit helper functions/modules that receive typed context instead of closing over large chunks of mutable local state. Keep prompt behavior, back/cancel semantics, and team-selection precedence identical, then add a targeted hotspot guardrail test so the extraction becomes a durable maintainability win instead of a one-off cleanup.

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| `render_start_wizard_prompt(...)` answers | preserve BACK/CANCEL/SWITCH_TEAM semantics exactly and localize any regression through focused wizard characterization tests | N/A | reject impossible answer shapes in helper tests instead of silently taking the wrong branch |
| quick-resume context loading/filtering | fall back to new-session flow rather than resuming the wrong workspace/team | N/A | treat incomplete context records as non-matching and continue the wizard safely |
| selected-profile / team-override precedence | preserve the existing `--team` over `selected_profile` rule when helpers rebuild wizard state | N/A | keep mismatched team/workspace context from leaking across resets |

## Load Profile

- **Shared resources**: in-memory recent-context lists and wizard state only.
- **Per-operation cost**: linear filtering of recent contexts plus prompt rendering.
- **10x breakpoint**: very large recent-context lists make quick-resume sluggish, so extracted helpers must keep filtering bounded and side-effect free.

## Negative Tests

- **Malformed inputs**: empty recent-context lists, missing team values, and incomplete workspace context records.
- **Error paths**: cross-team resume rejected at confirmation, workspace quick-resume back-navigation, and team-switch resets.
- **Boundary conditions**: no contexts, single matching context, multiple teams with `show_all_teams`, and standalone mode with no team selection.

## Steps

1. Identify the nested quick-resume/workspace-resume helpers inside `interactive_start` and move them into one or more small module-level helpers with explicit typed inputs.
2. Update `flow.py` and `flow_types.py` so `interactive_start` delegates those branches instead of keeping large nested closures.
3. Add or extend focused wizard characterization tests plus one targeted hotspot guardrail test that measures the extracted maintainability boundary directly.
4. Run the focused wizard/guardrail tests and fix any behavior drift before handoff.

## Must-Haves

- [ ] `interactive_start` delegates quick-resume/workspace-resume logic to typed helpers rather than defining the full subflows inline.
- [ ] Existing quick-resume, cross-team resume, and workspace-resume behaviors stay green under focused characterization tests.
- [ ] A new targeted guardrail test fails if the extracted hotspot grows back past the agreed slice boundary.
- [ ] The extraction reduces local complexity without introducing new adapter imports or changing launch semantics.

## Inputs

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_types.py`
- `tests/test_start_wizard_quick_resume_flow.py`
- `tests/test_start_wizard_workspace_quick_resume.py`
- `tests/test_start_cross_team_resume_prompt.py`

## Expected Output

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_types.py`
- `src/scc_cli/commands/launch/wizard_resume.py`
- `tests/test_launch_flow_hotspots.py`
- `tests/test_start_wizard_quick_resume_flow.py`
- `tests/test_start_wizard_workspace_quick_resume.py`
- `tests/test_start_cross_team_resume_prompt.py`

## Verification

uv run pytest --rootdir "$PWD" ./tests/test_launch_flow_hotspots.py ./tests/test_start_wizard_quick_resume_flow.py ./tests/test_start_wizard_workspace_quick_resume.py ./tests/test_start_cross_team_resume_prompt.py -q
