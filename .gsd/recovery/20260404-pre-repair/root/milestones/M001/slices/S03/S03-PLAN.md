# S03: Characterization tests for fragile current behavior

**Goal:** Add characterization coverage around the current fragile behavior named in the roadmap before deeper architectural changes proceed.
**Demo:** After this: After this slice, launch/resume, config inheritance, and safety behavior are locked by tests so later refactors can move safely.

## Tasks
- [x] **T01: Tightened launch/resume characterization by adding missing tests for continue-session handoff and proxy-env behavior.** — Inspect existing launch and resume coverage, then add characterization tests for the current Claude launch/resume paths that M001 intends to preserve through later refactors. Focus on behavior that operators depend on, not incidental implementation details.
  - Estimate: 60m
  - Files: .gsd/milestones/M001/slices/S03/tasks/T01-PLAN.md, tests/**, src/scc_cli/commands/launch/**, src/scc_cli/docker/**
  - Verify: uv run pytest -k "launch or resume or start"
- [x] **T02: Locked the truthful policy-ordering and block-reason contract with focused config-policy characterization tests.** — Add characterization tests for config inheritance and network-policy merge behavior so later typing work cannot silently change org/team widening or project/user narrowing rules.
  - Estimate: 60m
  - Files: .gsd/milestones/M001/slices/S03/tasks/T02-PLAN.md, tests/test_config_inheritance.py, tests/test_effective_config.py, src/scc_cli/application/**
  - Verify: uv run pytest tests/test_config_inheritance.py tests/test_effective_config.py
- [x] **T03: Locked the current safety-net baseline with a launch-boundary test proving fail-closed default policy injection.** — Inspect the current safety-net coverage and add characterization tests around the current destructive-git and explicit-network-tool protections that M001 names as the first cross-agent safety layer.
  - Estimate: 60m
  - Files: .gsd/milestones/M001/slices/S03/tasks/T03-PLAN.md, tests/**, src/scc_cli/**
  - Verify: uv run pytest -k "safety or git or network tool or curl or ssh"
