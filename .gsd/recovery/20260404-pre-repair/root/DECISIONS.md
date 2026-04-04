# DECISIONS.md

This file is append-only. Record new decisions as new entries.

---

## D-001 — Product identity
SCC means **Sandboxed Coding CLI**.

Status: accepted

---

## D-002 — Product center
SCC is a governed runtime for coding agents, not a new coding agent.

Status: accepted

---

## D-003 — Implementation root
All architecture work happens in `scc-sync-1.7.3`. The dirty `scc` tree is archival only.

Status: accepted

---

## D-004 — Backward compatibility stance
There are no active users, so core code will not carry long-term backward-compatibility aliases after the one-time migration.

Status: accepted

---

## D-005 — First-class providers
V1 supports Claude Code and Codex only. Other providers remain out of scope until the new core is stable.

Status: accepted

---

## D-006 — Runtime strategy
Portable OCI comes first. Docker Desktop is optional and not foundational.

Status: accepted

---

## D-007 — Network widening policy
Only org policy and delegated team policy may widen effective egress. Projects and users may only narrow.

Status: accepted

---

## D-008 — Enforced network scope
V1 enforced egress is HTTP/HTTPS-focused only.

Status: accepted

---

## D-009 — Runtime safety scope
The first cross-agent safety layer governs destructive git plus explicit network tools.

Status: accepted

---

## D-010 — Skills portability
Open Agent Skills are the only intended shared portability surface.

Status: accepted

---

## Decisions Table

| # | When | Scope | Decision | Choice | Rationale | Revisable? | Made By |
|---|------|-------|----------|--------|-----------|------------|---------|
| D001 | M001/S04 | architecture | How M001 introduces the provider-neutral typed seams for launch, runtime, network, safety, and audit planning. | Add a thin typed contract layer in `src/scc_cli/core/contracts.py` and a new `AgentProvider` protocol in `src/scc_cli/ports/agent_provider.py`, without migrating the whole launch flow to them in M001. | This establishes the explicit provider-neutral contract surface promised by the milestone while avoiding a destabilizing mid-milestone rewrite of the current Claude-shaped execution path. It gives later milestones concrete typed seams to adopt incrementally instead of keeping the architecture only in plan documents. | Yes | agent |
| D002 | M001/S04 | architecture | How M001 aligns error categories, exit-code mapping, JSON error metadata, and the shared audit-event direction. | Treat `SCCError` subclasses as the canonical source of exit code and category truth, add a stable `ErrorCategory` enum, include `error_category` and `exit_code` in JSON error payloads, and expose `to_audit_event()` as the first shared audit-event mapping helper. | The repo previously relied on mapper special-cases to correct stale exception defaults, which hid drift between exception classes and the published exit-code contract. Making the exception hierarchy authoritative and surfacing category metadata in JSON removes that ambiguity and gives later network and safety work a shared audit-event shape to reuse. | Yes | agent |
| D003 | M002 cross-cutting | architecture | How SCC should prioritize maintainability during milestone planning and implementation. | Treat maintainability as a standing architectural constraint: when touching large or fragile areas, prefer smaller typed modules, explicit seams, composition-root boundaries, and characterization tests before or alongside extraction work. | The user explicitly prioritized maintainability, clean architecture, and clean code. Making this a first-class architectural rule improves testability, consistency, and change safety while reinforcing existing typed-contract and adapter-boundary decisions. | Yes | collaborative |
| D004 | Post-S03 planning guidance for all remaining M002 work | architecture | How maintainability, clean architecture, and PEP 8 discipline should guide all future milestone and slice work. **Superseded in part by D011 for post-M002 milestone sequencing and maintainability staging.** | Apply PEP 8 style, clean architecture boundaries, maintainability-first decomposition, and robust error handling as default implementation policy across all phases; when touching large or high-churn files, prefer small typed extractions and clearer module boundaries even if it requires additional scoped work. **D011 narrows the post-M002 plan so repo-wide decomposition, guardrail restoration, xfail removal, and other broad hardening work stay in M005, while M003/M004 remain limited to slice-local extractions.** | The user explicitly wants cleaner, more maintainable code over minimal-change delivery. Reinforcing maintainability as a standing execution rule aligns with R001 and D003, reduces future change risk, improves testability and readability, and encourages reliable error handling plus smaller, easier-to-understand modules instead of further monolith growth. | Yes | human |
| D005 | M002/S03 | provider | How Codex should be represented on the shared AgentProvider seam in M002 | Model Codex as a file-configured provider with argv `('codex',)`, required destination set `openai-core`, artifact-path-owned settings, and no resume, skills, or native integrations until those capabilities are actually implemented. | This keeps ProviderCapabilityProfile honest, avoids leaking Codex-specific fields into shared launch contracts, and proves the launch seam supports a second real provider without reintroducing Claude-shaped core assumptions. | Yes | agent |
| D006 | M002/S04 planning | architecture | How S04 should scope pre-launch validation and the first durable audit sink | Implement S04 preflight as provider-neutral validation over the current launch contracts (`AgentLaunchSpec.required_destination_sets`, selected network policy, and launch-plan readiness) and persist launch/preflight `AuditEvent` records to one local append-only JSONL sink behind a dedicated port/adapter reused by every live start path. | Current SCC code already exposes the provider requirement names and effective network policy needed for an honest early gate, but it does not yet model a full destination-allowlist control plane or enterprise audit export. A local JSONL sink satisfies the milestone’s structured and durable audit requirement without inventing a second event schema, while keeping the implementation small, testable, and extendable for later milestones. | Yes | agent |
| D007 | M002/S04 | architecture | How live launch entrypoints should consume preflight validation and durable audit wiring in M002/S04 | Route both `scc start` and worktree auto-start through the shared `src/scc_cli/commands/launch/dependencies.py` builder sourced from `bootstrap.py`, and require both paths to finish through `finalize_launch(...)` rather than constructing `StartSessionDependencies` inline or calling `start_session(...)` directly. | S04 introduced a provider-neutral preflight gate and durable `AuditEvent` sink that only stay honest if every live launch path uses the same composition-root wiring and the same boundary. Centralizing the dependency builder keeps `bootstrap.py` as the sole adapter import boundary, reduces duplicated launch wiring, preserves team-context propagation for worktree auto-start, and guarantees blocked launches and audit persistence failures fail closed before runtime startup in both entrypoints. | Yes | agent |
| D008 | M002/S05 planning | architecture | How S05 should expose durable launch diagnostics while reducing duplicated support-bundle logic | Add an application-owned launch-audit reader surfaced via `scc support launch-audit`, include redacted recent launch audit context in support bundles, and route support-bundle generation through the application layer instead of the legacy top-level helper. | S04 created a durable local launch audit sink but no bounded operator-facing inspection surface. Leaving diagnostics split between the new application support-bundle use case and the legacy top-level `support_bundle.py` helper would preserve root sprawl and allow redaction or manifest behavior to drift. A single application-owned diagnostics path gives maintainers one source of truth, keeps audit inspection redaction-aware and bounded, and advances R001 by shrinking duplicated launch/support code. | Yes | agent |
| D009 | M002/S05/T03 | architecture | Where the interactive launch wizard should keep quick-resume and workspace-resume orchestration after S05/T03 | Keep top-level quick-resume and workspace-resume subflows in `src/scc_cli/commands/launch/wizard_resume.py`, pass explicit `WizardResumeContext` inputs from `interactive_start`, and guard the boundary with `tests/test_launch_flow_hotspots.py` so nested resume helpers do not grow back into `flow.py`. | `interactive_start` was the largest remaining launch-flow hotspot. Moving the resume branches into a focused command-layer helper module reduces local complexity without changing launch semantics, while explicit typed context preserves the existing `--team` over `selected_profile` precedence and makes malformed answer handling testable. The hotspot guardrail makes the maintainability gain durable instead of depending on convention. | Yes | agent |
| D010 | M002/S05 | requirement | R001 | validated | M002/S05 reduced two active maintainability hotspots in touched launch/support code by moving quick-resume and workspace-resume orchestration into typed helpers (`wizard_resume.py`), converging CLI and settings support-bundle generation on one application-owned implementation, removing the legacy root helper, and adding focused characterization/guardrail coverage (`test_launch_flow_hotspots.py`, support/settings/root-sprawl tests). Slice verification and repo-wide gates passed in the worktree (`uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pytest --rootdir "$PWD" -q`). | Yes | agent |
| D011 | M002/S05 override follow-through | roadmap | How milestone sequencing and maintainability staging should proceed after M002 closes | Keep the milestone order `M002 -> M003 -> M004 -> M005`; do not start M005 next. Register or confirm M003 and M004 from `PLAN.md`, run M003 before M004, keep M005 as the final quality-bar milestone, and limit M003/M004 maintainability work to local extractions that directly enable the active slice while reserving repo-wide decomposition, typed-config migration, guardrail restoration, xfail removal, and the broad coverage campaign for M005. | The override changes execution order and the definition of what post-M002 maintainability work is allowed to pull forward. Recording it as an architectural roadmap decision keeps project, requirements, and milestone handoff documents aligned and prevents closeout or reassessment work from incorrectly promoting M005 ahead of the runtime and safety milestones. | Yes | human |
