---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T01: Inventory repo truth and in-flight work

Inspect the working tree, active branch, uncommitted diff, and existing GSD artifacts. Classify what appears to be M001-related in-flight work versus unrelated or archival material, and capture the practical baseline for the repo before broader edits proceed.

## Inputs

- `CONSTITUTION.md`
- `PLAN.md`
- `.gsd/milestones/M001-ROADMAP.md`
- `git status`
- `git diff --stat`

## Expected Output

- `Updated understanding of the active working tree state.`
- `A task summary recording root, branch, dirty paths, and major M001 hotspots.`

## Verification

git status --short --branch && git diff --stat && rg -n "unrestricted|corp-proxy-only|isolated|AgentProvider|AgentLaunchSpec|RuntimeInfo|NetworkPolicyPlan|SafetyVerdict|AuditEvent" -S . --glob '!**/.venv/**'
