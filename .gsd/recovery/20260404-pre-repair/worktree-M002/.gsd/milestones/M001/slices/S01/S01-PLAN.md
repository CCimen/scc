# S01: Baseline truth and implementation-root freeze

**Goal:** Establish the actual starting point for M001 so later migration and typing work is grounded in repo truth instead of assumptions.
**Demo:** After this: After this slice, the repo has an explicit M001 execution baseline: active root confirmed, working-tree state inventoried, and the standard verification gate recorded.

## Tasks
- [x] **T01: Planned M001 into executable slices and captured the real repo baseline, including the active dirty worktree and legacy-vocabulary hotspots.** — Inspect the working tree, active branch, uncommitted diff, and existing GSD artifacts. Classify what appears to be M001-related in-flight work versus unrelated or archival material, and capture the practical baseline for the repo before broader edits proceed.
  - Estimate: 30m
  - Files: .gsd/milestones/M001/slices/S01/tasks/T01-PLAN.md, README.md, src/scc_cli/**, tests/**
  - Verify: git status --short --branch && git diff --stat && rg -n "unrestricted|corp-proxy-only|isolated|AgentProvider|AgentLaunchSpec|RuntimeInfo|NetworkPolicyPlan|SafetyVerdict|AuditEvent" -S . --glob '!**/.venv/**'
- [x] **T02: Captured the verification baseline and confirmed that the current M001 working tree already passes ruff, mypy, and pytest.** — Run the required verification gate against the current repo state to determine the real M001 baseline. Capture whether each command passes or fails, including the first meaningful failure surface if the gate is not yet green.
  - Estimate: 45m
  - Files: .gsd/milestones/M001/slices/S01/tasks/T02-PLAN.md
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [x] **T03: Confirmed that the shell root, git toplevel, and active written guidance all point to scc-sync-1.7.3 as the only implementation root.** — Confirm that active references, milestone artifacts, and execution guidance all point to scc-sync-1.7.3 as the implementation root, with the dirty scc tree treated as archival/rollback evidence only. Tighten any stale local guidance discovered during the inventory.
  - Estimate: 30m
  - Files: .gsd/milestones/M001/slices/S01/tasks/T03-PLAN.md, AGENTS.md, .gsd/PROJECT.md, .gsd/RUNTIME.md
  - Verify: rg -n "scc-sync-1.7.3|dirty `scc` tree|archival|rollback evidence" . --glob 'AGENTS.md' --glob '.gsd/**' --glob 'README.md' --glob 'PLAN.md'
