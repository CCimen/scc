# S04: Typed control-plane contracts and shared error-audit seams

**Goal:** Define the typed core models and shared contracts that M001 is meant to establish, while keeping provider-specific behavior inside adapters and making outputs/errors more coherent.
**Demo:** After this: After this slice, the codebase has explicit typed contracts for the control-plane direction and aligned error/audit seams, with specs and decisions updated to match.

## Tasks
- [x] **T01: Added the M001 typed contract layer and a new provider-neutral AgentProvider protocol with focused contract tests.** — Introduce the M001 typed contract layer for the planned control-plane seams: RuntimeInfo, ProviderCapabilityProfile, AgentLaunchSpec, NetworkPolicyPlan, DestinationSet, EgressRule, SafetyPolicy, SafetyVerdict, and AuditEvent. Keep the first implementation thin and provider-neutral.
  - Estimate: 90m
  - Files: .gsd/milestones/M001/slices/S04/tasks/T01-PLAN.md, src/scc_cli/core/**, src/scc_cli/application/**, tests/**
  - Verify: uv run mypy src/scc_cli && uv run pytest -k "contract or typed or launch spec or runtime info or safety verdict or audit event"
- [x] **T02: Aligned SCCError categories and exit codes with JSON payload metadata, and added a shared audit-event mapping helper.** — Align SCCError categories, exit-code handling, and human/JSON output contracts around the typed direction established in T01. Introduce or tighten a shared audit event shape that network and safety work can later reuse.
  - Estimate: 75m
  - Files: .gsd/milestones/M001/slices/S04/tasks/T02-PLAN.md, src/scc_cli/core/errors.py, src/scc_cli/cli.py, src/scc_cli/commands/**, src/scc_cli/presentation/json/**, tests/**
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest -k "error or exit code or json or audit"
- [x] **T03: Recorded the S04 architectural decisions and revalidated the full M001 foundation on a clean passing gate after fixing two small slice-local issues.** — Update the structured project records to reflect the accepted M001 seams and verify the whole milestone workstream with the fixed gate. Record any new decision required to keep follow-on work from reintroducing compatibility aliases or provider leakage.
  - Estimate: 45m
  - Files: .gsd/milestones/M001/slices/S04/tasks/T03-PLAN.md, .gsd/DECISIONS.md, .gsd/REQUIREMENTS.md, specs/**
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
