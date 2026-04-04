# M002 Context: Provider-Neutral Launch Adoption

## Milestone Intent
M002 exists to turn the M001 typed seams into the actual live architecture. M001 already proved the baseline, truthful network vocabulary, characterization safety net, and typed control-plane direction. M002 should not revisit those decisions; it should adopt them in the real launch path so later runtime and security work land on the correct abstraction boundary.

## Why This Is The Right Next Milestone
M001 completed successfully and explicitly called out two follow-ups: adopt `AgentProvider` / `AgentLaunchSpec` in the actual launch flow, and route the new `AuditEvent` shape to a persistent sink when the next architectural layers are ready. M002 is the right place to do the first part fully and the second part minimally but concretely. Do not jump straight to egress enforcement or runtime safety while the launch path still carries Claude-shaped assumptions.

## What M001 Already Gave You
- `scc-sync-1.7.3` is the only active implementation root.
- Truthful network vocabulary is already live: `open`, `web-egress-enforced`, `locked-down-web`.
- Characterization coverage exists around fragile launch/resume, config inheritance, and safety behavior.
- Typed contracts and the first provider-neutral seam already exist.
- Error-category and exit-code direction are aligned enough to support preflight validation work.
- The milestone exited on a clean passing verification gate.

## Locked Product Decisions For M002
These are already decided and should not be reopened during the milestone unless implementation reveals a hard contradiction:
- SCC is a governed runtime for coding agents, not a new coding agent.
- V1 scope is Claude Code plus Codex only.
- Hard enforcement belongs in SCC-controlled runtime layers, not in provider-native hooks/rules/plugins alone.
- Open Agent Skills are the only intended shared portability surface across providers.
- Provider-native hooks, rules, plugins, marketplaces, and config layouts remain adapter-owned.
- Provider-core destination sets are automatic and minimal for the selected provider only.
- Shared developer destinations such as GitHub/npm/PyPI are never implicitly enabled by selecting a provider.
- No backward-compatibility aliases for pre-M001 terminology should be reintroduced into core.

## In Scope
- Adopting `AgentProvider` and `AgentLaunchSpec` in the actual launch path.
- Extracting remaining Claude-specific launch/render/auth behavior into the Claude adapter.
- Adding Codex as a genuine second provider on the same seam.
- Implementing pre-launch validation for provider-core requirements and provider-owned artifacts.
- Routing launch/preflight `AuditEvent`s to one durable structured sink.
- Tightening diagnostics and targeted decomposition where needed to stabilize the new architecture.

## Out Of Scope
- Hard network topology enforcement, proxy sidecars, and final egress policy implementation.
- Podman support beyond preserving contracts that will allow it later.
- Broad command-governance work beyond whatever is incidentally touched by launch-path migration.
- Enterprise control-plane hosting, SSO, central audit export, or policy registry work.
- Pi/OpenCode integration.

## Canonical References To Load First
Read these before planning any slice work:
1. `PLAN.md`
2. `CONSTITUTION.md`
3. `.gsd/PROJECT.md`
4. `.gsd/DECISIONS.md`
5. `.gsd/KNOWLEDGE.md`
6. `.gsd/RUNTIME.md`
7. `M001-ROADMAP.md`
8. `M001-SUMMARY.md`
9. `M001-VALIDATION.md`
10. The latest approved SCC v1 clean-architecture plan

Then inspect the key M001 code surfaces first:
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/ports/agent_provider.py`
- `src/scc_cli/core/errors.py`
- `src/scc_cli/core/error_mapping.py`
- `src/scc_cli/json_command.py`
- The real launch/orchestration entry points currently shaping provider behavior

## Architectural Rules
### 1. Core owns plans, adapters own provider shape
Core computes and consumes typed plans. Adapters own provider-specific filesystem layout, auth materialization, hook/rule/plugin integration, and provider UX surfaces.

### 2. No provider leakage back into core
A helper extracted into core that still knows about `.claude`, `.codex`, Claude-only defaults, or Codex-only filesystem assumptions is not a valid abstraction.

### 3. Adopt one seam end-to-end
Do not leave `AgentProvider` and `AgentLaunchSpec` as partial side paths. M002 is successful only if the real launch path goes through them.

### 4. Audit shape stays unified
The `AuditEvent` model introduced in M001 must remain the canonical event shape. M002 may add a durable sink, but it must not invent parallel event payload families.

### 5. Keep future runtime work in mind
M002 should not embed runtime-engine assumptions that make M003 harder. Provider launch planning should state requirements, not hardcode future Docker-specific enforcement behavior.

## Expected Shape Of The Solution
### Provider seam
The live launch flow should look roughly like:
1. Resolve effective SCC config.
2. Resolve selected provider.
3. Ask the provider adapter for a typed launch plan.
4. Validate provider-core requirements before runtime startup.
5. Emit audit/preflight events.
6. Hand the typed plan to runtime execution.

### Claude adapter
The Claude adapter should own:
- `.claude` artifact layout
- Claude hook wiring
- Claude auth artifact expectations
- Claude provider-core destinations
- Claude-specific UX affordances that improve messaging but do not define hard enforcement

### Codex adapter
The Codex adapter should own:
- `.codex` artifact layout
- Codex auth artifact expectations
- Codex provider-core destinations
- Any optional Codex-native UX affordances such as rules or plugin materialization, but only as adapter-local behavior

### Audit sink
The first durable sink can be modest. It does not need to be the final enterprise audit architecture. It does need to be:
- structured
- durable
- reused by all M002 launch/preflight events
- easy for M003/M004 to extend

A local structured log or append-only event file is acceptable if it is clearly treated as the milestone’s canonical sink.

## Risks And Mitigations
### Risk: partial seam adoption
**Problem:** `AgentProvider` exists but core still reaches around it in important launch branches.
**Mitigation:** treat S01 as incomplete until the real path uses the seam end-to-end; add tests that prove the seam is executed.

### Risk: Claude migration succeeds by leaving Codex under-specified
**Problem:** the abstraction looks clean only because it still matches Claude better than Codex.
**Mitigation:** add Codex in the same milestone, not later, so the seam is exercised by two genuinely different providers.

### Risk: audit work forks into ad hoc logs
**Problem:** launch/preflight code adds bespoke logs before the real sink exists.
**Mitigation:** require one canonical durable sink in S04 and route all new launch/preflight events through it.

### Risk: decomposition work expands uncontrollably
**Problem:** M002 turns into a general cleanup milestone.
**Mitigation:** only decompose files/functions that block provider-neutral launch adoption, diagnostics, or testability.

### Risk: maintainability is deferred while oversized launch files keep growing
**Problem:** provider work lands, but central orchestrators become harder to change and reason about.
**Mitigation:** when a slice touches a large or fragile launch surface, plan the smallest safe extraction or helper split in the same slice, backed by characterization tests.

### Risk: preflight validation becomes runtime-policy creep
**Problem:** M002 starts implementing M003 network enforcement by accident.
**Mitigation:** keep M002 preflight limited to validation of declared provider-core requirements and artifact readiness; do not implement proxy topology here.

## Verification Expectations
### Contract verification
- `AgentProvider` contracts are exercised for both Claude and Codex.
- `AgentLaunchSpec` contains enough typed data for core execution without provider-shaped fallback access.
- Error and JSON output remain aligned with the M001 hierarchy.

### Integration verification
- Claude launches through the new seam and retains current expected behavior.
- Codex launches through the same seam.
- Pre-launch failures happen before runtime start and produce clear output.
- Audit events emit through one stable sink.

### Operational verification
- Diagnostics can identify selected provider and relevant launch-plan facts.
- The repo remains green on the fixed gate.

## Slice Planning Guidance For GSD
- Keep slices vertically meaningful and demoable.
- Prefer 3-6 tasks per slice; if a slice decomposes beyond that, re-evaluate the slice boundary.
- Every task must have mechanically checkable must-haves.
- Do not combine provider extraction, Codex onboarding, and audit persistence into one task.
- Preserve the M001 characterization discipline: when moving fragile paths, strengthen tests first or immediately alongside the change.
- If a task touches a large orchestration file, include the smallest maintainability extraction needed to improve readability, ownership, or testability in the same slice plan.

## Parallel And Worktree Guidance
Do not run this milestone in GSD parallel mode. GSD’s parallel orchestration is opt-in and uses isolated worktrees with dependency checks and file-overlap warnings, which is useful later, but M002 is still the wrong milestone for parallel execution because it deliberately concentrates change in the most overlap-heavy part of the codebase: core launch flow, provider adapters, and diagnostics.

## Milestone Exit Contract
The milestone is not complete until all of the following are true:
- The live path goes through `AgentProvider.prepare_launch(...)`.
- Claude-specific launch behavior is adapter-owned.
- Codex is first-class on the same seam.
- Provider-core preflight validation fails early and clearly.
- `AuditEvent` is persisted through one stable structured sink.
- `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest` pass.

## Hand-off Note
If implementation discovers that a required provider-neutral abstraction is missing from M001, add it only if it directly enables end-to-end seam adoption. Do not reopen the milestone into a generic framework rewrite.
