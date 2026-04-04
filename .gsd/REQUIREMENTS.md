# Requirements

This file is the explicit capability and coverage contract for the project.

## Validated

### R001 — SCC changes must improve maintainability by keeping touched areas cohesive, testable, and easier to change, especially when work crosses oversized or high-churn files.
- Class: non-functional
- Status: validated
- Description: SCC changes must improve maintainability by keeping touched areas cohesive, testable, and easier to change, especially when work crosses oversized or high-churn files.
- Why it matters: Maintainability directly drives testability, consistency, and the long-term cost and safety of future provider/runtime changes.
- Source: user-feedback
- Primary owning slice: architecture
- Supporting slices: M002/S03, M002/S05
- Validation: Proof from M002/S05: `uv run pytest --rootdir "$PWD" ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q`, `uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q`, `uv run pytest --rootdir "$PWD" ./tests/test_launch_flow_hotspots.py ./tests/test_start_wizard_quick_resume_flow.py ./tests/test_start_wizard_workspace_quick_resume.py ./tests/test_start_cross_team_resume_prompt.py -q`, plus repo-wide `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest --rootdir "$PWD" -q` all passed.
- Notes: Validated by M002/S05: support-bundle generation now has one application-owned path, launch wizard resume subflows were extracted into typed helpers, and hotspot/root-sprawl guardrails now prevent regression. M005/S01 established the quantitative baseline (315 characterization tests, 63-defect catalog). M005/S02 completed all 15 HARD-FAIL/MANDATORY-SPLIT decompositions and 3 boundary violation repairs — zero files in src/scc_cli/ exceed 800 lines. M005/S03-S06 must advance R001 through the governed-artifact/team-pack typed model adoption (D-018–D-020, D017), not generic strict-typing cleanup — the provider-neutral bundle model and provider-native renderers are the organizing principle for remaining maintainability work.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | non-functional | validated | architecture | M002/S03, M002/S05 | Proof from M002/S05: `uv run pytest --rootdir "$PWD" ./tests/test_launch_audit_support.py ./tests/test_support_bundle.py -q`, `uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q`, `uv run pytest --rootdir "$PWD" ./tests/test_launch_flow_hotspots.py ./tests/test_start_wizard_quick_resume_flow.py ./tests/test_start_wizard_workspace_quick_resume.py ./tests/test_start_cross_team_resume_prompt.py -q`, plus repo-wide `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest --rootdir "$PWD" -q` all passed. |

## Coverage Summary

- Active requirements: 0
- Mapped to slices: 0
- Validated: 1 (R001)
- Unmapped active requirements: 0
