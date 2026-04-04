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

## D-017 — M004 safety architecture must stay narrow and truthful
For M004/S02–S05: wrapper scope is exactly 7 tools (destructive git + 6 explicit network tools). Wrappers are defense-in-depth, UX, and audit — never claim they are the primary enforcement plane. Topology + proxy policy remain the hard network control. Provider-native integrations are adapter-owned and additive only. One active team context per session. M004 maintainability stays local to touched files. Supersedes no prior decision but constrains D-009 scope for M004 implementation.

Status: accepted

---

## D-018 — Governed artifacts are canonical; plugins, rules, hooks, and instruction files are render targets
SCC should keep one provider-neutral governed-artifact catalog plus bundle model for org/team/project/user policy. Open Agent Skills are the primary shared workflow surface. MCP definitions remain provider-neutral where possible. Provider-native hooks, marketplace entries, `.codex-plugin/plugin.json`, `.mcp.json`, `.app.json`, `.codex/rules/*.rules`, `.codex/hooks.json`, `AGENTS.md`, `CLAUDE.md`, and similar files are adapter-owned render targets, not the canonical policy model. Teams should enable approved bundles once and switch providers without maintaining dual team configs. When a provider lacks a native surface, SCC applies the shared parts and reports skipped native bindings truthfully instead of inventing fake parity.

Status: accepted

---

## D-019 — Claude and Codex native plugin surfaces are intentionally asymmetric
SCC must not model Claude and Codex as if they share one plugin schema. Claude plugins may carry skills, agents, hooks, MCP servers, LSP config, and plugin settings. Codex plugins bundle skills, apps, and MCP, while rules, hooks, `config.toml`, marketplace catalogs, and `AGENTS.md` layering remain separate native surfaces. Functional parity means one approved SCC bundle produces the closest truthful native projection per provider. It does not mean one physical plugin directory can or should be reused unchanged across providers.

Status: accepted

---

## D-020 — One team pack source, generated native distributions
The preferred DX and maintainability model is one approved SCC bundle source per team pack, not one provider marketplace as the canonical input. Team policy should reference approved bundle IDs. SCC should fetch the pinned bundle source, then render the required Claude or Codex native outputs locally. If the organization wants direct native installation outside SCC, generated Claude/Codex marketplace artifacts may be published as build outputs from the same source repository.

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
| D012 | M003/S01 | architecture | How runtime detection should be structured and consumed in M003 and beyond | Introduce a RuntimeProbe protocol with a single probe() -> RuntimeInfo method. DockerRuntimeProbe is the sole adapter calling docker/core helpers. DockerSandboxRuntime accepts a RuntimeProbe in __init__ and its ensure_available() inspects RuntimeInfo fields instead of calling docker.check_docker_available() directly. Bootstrap shares one probe instance between sandbox_runtime and runtime_probe fields. A tokenizer-based guardrail test prevents future direct check_docker_available() calls outside the adapter layer. | This replaces name-only heuristics with typed capability detection, keeps docker-specific knowledge in one adapter boundary, and establishes the RuntimeInfo-driven pattern that S02 (OCI backend) and S03 (egress topology) depend on for portable runtime selection. | Yes | agent |
| D013 | M003/S02 | architecture | How the OCI sandbox backend is introduced alongside the existing Docker Desktop sandbox path | Add OciSandboxRuntime as a parallel SandboxRuntime adapter (not a replacement). Bootstrap selects between DockerSandboxRuntime and OciSandboxRuntime based on RuntimeInfo.preferred_backend from the probe. Docker Desktop sandbox path remains the default when sandbox is available. OCI backend uses docker create/start/exec with explicit volume mounts for credential persistence. Image selection is driven by preferred_backend: SANDBOX_IMAGE for docker-sandbox, SCC_CLAUDE_IMAGE_REF for oci. | Constitution §3 prohibits Docker Desktop as a hard dependency. The OCI backend makes SCC work on Docker Engine, OrbStack, and Colima without changing the existing Desktop path. Parallel adapters behind the same protocol keeps risk contained — the Desktop path is untouched. Bootstrap-level selection via probe results means no runtime surprise for users. Credential handling differs fundamentally between backends (symlink pattern vs volume mount), so sharing a single adapter would create accidental coupling. | Yes | agent |
| D014 | M003/S03 | architecture | How web-egress enforcement is implemented in the OCI adapter | Build a NetworkTopologyManager adapter that creates internal-only Docker networks and a Squid proxy sidecar as the sole external bridge. The OCI adapter orchestrates topology: for web-egress-enforced, it creates the internal network, starts the proxy with compiled ACLs, and attaches the agent container to the internal network only. For locked-down-web, the agent gets --network=none. ACL compilation is a pure function in core/egress_policy.py that converts NetworkPolicyPlan into Squid ACL config. Default deny rules cover IP literals, loopback, private CIDRs, link-local, and metadata endpoints. The Docker Desktop sandbox path (DockerSandboxRuntime) is unchanged — Desktop has its own network isolation. | Constitution §4 requires security language to match actual enforcement — the existing code only set proxy env vars without any topology isolation. Squid is mature, handles HTTPS CONNECT natively, and has well-understood ACL semantics for host + IP/CIDR matching. Separating ACL compilation (pure logic) from topology management (subprocess calls) from adapter integration (OciSandboxRuntime) keeps each piece testable in isolation. The internal-only Docker network is the hard enforcement boundary — even if the agent ignores proxy env vars, it physically cannot reach external networks without going through the proxy. | Yes | agent |
| D015 | M003/S04/T03 | governance | How the enterprise egress model is articulated and verified for the remainder of M003 | Keep the enterprise egress model explicit throughout M003: web-egress-enforced is the normal cloud-provider enterprise mode; locked-down-web is an intentional no-web / no-cloud-launch posture unless a future local-model path exists. Org owns baseline mode, hard deny overlays, named destination sets, and delegation. Teams may widen only within delegated bounds. Project/user scopes may narrow only. Every workspace/session has exactly one active team context; users switch context between teams — do not implicitly union team allowlists. Diagnostics must show active team context, effective destination sets, runtime backend, network mode, and clear blocked reasons. Topology plus proxy policy remain the hard control; wrappers are defense-in-depth, UX, and audit only. Reinforces and extends D015. | User override during M003/S04/T03 to ensure the governance model is unambiguous in all remaining planning documents, verification criteria, and documentation. D015 established the governance composition rules; this decision makes mode semantics (web-egress-enforced vs locked-down-web), diagnostic surface requirements, and the single-team-context invariant fully explicit so S05 verification and docs truthfulness work against a clear contract. | Yes | human |
| D016 | M004/S01 | architecture | How S01 handles SafetyPolicy.rules typing and rule-enablement checking | Keep `SafetyPolicy.rules` as `dict[str, Any]` (existing frozen dataclass). Add standalone `_matched_rule_to_policy_key()` mapping function in `core/safety_engine.py` and use `policy.rules.get(key, True)` for fail-closed rule enablement checking. Do not add a `SafetyRule` typed model in M004/S01. | SafetyPolicy is an existing frozen dataclass used across test_core_contracts.py and other test code. Changing `rules` to a stricter type would break existing tests and require migration. A standalone mapping function achieves the same fail-closed semantics without breaking the contract surface. A typed SafetyRule model can be introduced in a later slice if needed. | Yes | agent |
| D017 | M005/S02/T06 | roadmap | How M005/S03-S06 should be scoped after S02 decomposition completes | Replan S03-S06 to explicitly incorporate the governed-artifact/team-pack architecture. S03 must land typed GovernedArtifact/ArtifactBundle/ArtifactRenderPlan models and typed config flow — not generic strict-typing cleanup. S04 must harden fetch/render/merge/install failure handling for the provider-native renderer pipeline. S06 must validate docs/diagnostics truthfulness for the team-pack model. Generic strict-typing and error-handling work is still in scope but subordinate to the team-pack architecture. One approved SCC team-pack source is canonical; team config references bundle IDs not raw marketplace URLs; split provider-neutral planning from provider-native renderers; Claude and Codex native surfaces are asymmetric; do not bolt Codex onto the Claude-shaped marketplace pipeline; render per-provider native outputs from the same bundle plan; do not require dual team configs. | User overrides during M005/S02/T06 directed that S03-S06 must not proceed as generic quality cleanup. The governed-artifact/team-pack architecture from D018-D020, specs/03-provider-boundary.md, and specs/06-governed-artifacts.md must be the organizing principle for remaining M005 work. This ensures the architecture quality milestone actually delivers the provider-neutral bundle model instead of treating it as optional future work. | Yes | human |
| D018 | M005/S03 | architecture | Whether to include wizard cast() cleanup (23 casts across wizard.py and flow_interactive.py) in S03 | Defer wizard cast cleanup to future work. S03 focuses on the governed-artifact model hierarchy and NormalizedOrgConfig adoption. The wizard cast pattern is type-unsafe but functionally correct — it does not block the typed config flow, and refactoring the wizard state machine is a significant effort with high blast radius touching all wizard tests. | D017 scopes S03 to the governed-artifact/team-pack typed model adoption and config flow typing. The wizard casts are a separate concern (interaction dispatch, not config models) and the refactor risk is high relative to the benefit. The cast pattern works; it just loses generic type parameters. | Yes — can be added to S06 or a future milestone | agent |
| D019 | M005/S03/T05 — before execution | roadmap | How to handle S03 completion and S04-S06 replanning for governed-artifact/team-pack architecture | Close S03 with T01-T04 complete (governed-artifact types + NormalizedOrgConfig adoption). Drop T05 (safety_policy_loader typing — already under target at 382 dict[str,Any] refs; the small conversion can be folded into future work). Replan S04 as provider-neutral artifact planning pipeline + provider-native renderers with hardened failure handling. Replan S05 as coverage on governed-artifact/team-pack planning and renderer seams. Replan S06 as diagnostics/docs truthfulness for the team-pack model and rendered native surfaces. | User override: S03-S06 must be replanned around the governed-artifact/team-pack architecture (D017-D020, specs/03, specs/06) before any further generic implementation. The T05 safety_policy_loader typing is acceptable cleanup but not architecturally significant — the slice already met its dict[str,Any] reduction target (382 < 390). The real remaining work is building the provider-neutral bundle planning pipeline and provider-native renderers, not more incremental typing conversions. S04-S06 as currently planned are generic quality cleanup that do not incorporate the team-pack architecture. | No — user directed | collaborative |
