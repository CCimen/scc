# SCC v1 Clean Architecture Plan on `scc-sync-1.7.3`

## Summary
- Use `scc-sync-1.7.3` as the only implementation root. Keep the original dirty `scc` tree untouched as archive and rollback evidence.
- Optimize for a clean break, not backward compatibility. Migrate existing local configs, fixtures, docs, and tests once; carry no legacy compatibility aliases in core after that migration.
- Scope v1 to Claude Code and Codex only. SCC remains a governed runtime for coding agents, not a new agent, and it must not depend on Docker Desktop.
- Lock these product rules now: only org and delegated team policy may widen effective egress; project and user scopes may only narrow; the first cross-agent safety layer governs destructive git plus explicit network tools; enforced egress in v1 is HTTP/HTTPS only.
- Treat maintainability as a first-class outcome: each milestone should leave touched areas smaller, better bounded, easier to test, and easier to change than before.
- Success means Claude and Codex both launch from the same provider-neutral core on plain OCI runtimes, provider-core destinations are validated before launch, GitHub/npm/PyPI are optional named allowlist sets, open Agent Skills are the only intended cross-provider workflow portability layer, and hard enforcement lives in the runtime rather than in provider-specific hooks or plugin glue.

## Core Architecture And Interfaces
- Keep the system split into three layers only: control plane, runtime backend, and provider adapters. Control plane computes typed policy and launch plans, runtime backends materialize isolation and network controls, and provider adapters own provider-specific config, auth surfaces, skills, plugins, and UX integrations.
- Replace the current shallow runner boundary with `AgentProvider.prepare_launch(...) -> AgentLaunchSpec`. `AgentLaunchSpec` must contain provider launch argv/env/workdir, provider artifact locations, required provider-core destination set, and any provider-owned UX add-ons.
- Introduce these typed core models and remove raw dict-driven policy flow from application code: `RuntimeInfo`, `NetworkPolicyPlan`, `DestinationSet`, `EgressRule`, `SafetyPolicy`, `SafetyVerdict`, `AuditEvent`, and `ProviderCapabilityProfile`.
- Make auth adapter-owned, not core-owned. Claude and Codex adapters resolve their own credential modes and mounted auth artifacts; SCC core only reasons about provider capability and required files, never token formats.
- Rename network modes to truthful names and use them everywhere after the one-time migration: `open`, `web-egress-enforced`, and `locked-down-web`. Remove the old `unrestricted`, `corp-proxy-only`, and `isolated` vocabulary from core, docs, and tests.
- Define egress policy shape around typed normalized models: org owns the baseline mode, blocked CIDRs/hosts, named destination sets, and delegation rules; teams may widen only within org-delegated bounds; projects and users may only narrow the effective set or emit request metadata.
- Standardize on open Agent Skills where possible. Skills are the only intended cross-provider instruction and workflow portability layer.
- Treat plugins, hooks, rules, marketplaces, and native config surfaces as provider-native integrations. They are adapter-owned and must never become core assumptions or cross-provider contracts.
- Introduce a provider-neutral governed artifact model in core for approved skills, approved native integrations, provenance, pinning, and installation intent. Each adapter materializes that into native provider formats such as Claude skill assets, Codex `.codex-plugin/plugin.json`, local marketplace entries, hook wiring, or rules configuration.
- Split provider-owned artifacts cleanly. Claude owns `.claude` config and hook wiring. Codex owns `.codex` config plus any SCC-managed local Codex plugin bundle using the official `.codex-plugin/plugin.json` and repo marketplace model.

## Maintainability Doctrine
- Maintainability is not cleanup work deferred to the end; it is part of the acceptance criteria for every milestone and slice.
- When touching oversized or high-churn files, prefer behavior-preserving extraction into smaller typed modules with explicit names and focused responsibilities.
- Add characterization or contract tests before or alongside extractions so refactors reduce risk instead of relocating it.
- Keep composition roots explicit. New adapter wiring, provider selection, and runtime hookup should stay easy to inspect rather than being hidden behind clever indirection.
- Prefer simple, testable control flow over temporary convenience. A change that works but makes the next change harder is incomplete.

## Implementation Milestones
1. **Milestone 0 — Baseline Freeze And Migration Root**. Declare `scc-sync-1.7.3` the only writable repo, normalize Beads there only, migrate current local configs/docs/tests to the new network vocabulary, remove stale compatibility assumptions, and require a fully green baseline before architecture work continues.
2. **Milestone 1 — Typed Control Plane Foundation**. Finish the typed config migration, replace remaining `dict[str, Any]` policy/config flow with normalized models, align `SCCError` and exit-code mapping, and add a single typed audit event pipeline that network and safety work will reuse.
3. **Milestone 2 — Provider-Neutral Launch Boundary**. Replace the current runner/launch flow with `AgentProvider`, `AgentLaunchSpec`, and provider-owned artifact rendering. Claude is migrated first on the new boundary, Codex is added second on the same boundary with no Claude-specific fallbacks in core. Provider-core destination bundles are implicit from provider selection and must be validated before runtime startup. Shared dev sets such as `github-core`, `npm-public`, and `pypi-public` remain explicit org/team policy choices. Open Agent Skills are governed in core; native plugin and hook materialization stays inside adapters.
4. **Milestone 3 — Portable Runtime And Enforced Web Egress**. Replace name-based runtime detection with capability-based `RuntimeInfo`. Build SCC-owned images `scc-base`, `scc-agent-claude`, `scc-agent-codex`, and `scc-egress-proxy`. Ship a plain OCI backend first that works with Docker Engine, OrbStack, and Colima-style Docker CLIs, then add Podman on the same contracts. In enforced modes, the agent container sits only on an internal network, the proxy is the only component with both internal and external attachment, host networking is forbidden, IP literals are denied, loopback/private/link-local/metadata endpoints are denied by default, and proxy ACLs must check both requested host and resolved IP/CIDR.
5. **Milestone 4 — Cross-Agent Runtime Safety**. Split the current safety-net implementation into a shared `SafetyEngine.evaluate(...) -> SafetyVerdict` plus provider UX adapters. The hard baseline lives in runtime wrappers shipped in `scc-base`; Claude hooks and Codex-native integrations are additive UX and audit surfaces only. V1 command families are destructive git plus explicit network tools: `curl`, `wget`, `ssh`, `scp`, `sftp`, and remote `rsync`. Package managers and cloud/admin tools stay out of the first safety scope. In enforced web-egress modes, network-tool wrappers are defense-in-depth and better UX; topology and proxy policy remain the hard control.
6. **Milestone 5 — Decomposition, Guardrails, And Hardening**. After characterization tests exist, split the large launch and flow orchestrators, re-enable file/function size guardrails by removing the current `xfail` posture, surface runtime/provider/network/safety status in diagnostics, and update docs so the security claims match the implemented behavior exactly. If a slice already touches an oversized or high-churn file before Milestone 5, do the smallest maintainability extraction needed in that slice instead of deferring obvious cleanup.

## Test Plan
- Start with characterization tests for current Claude launch behavior, current safety-net git protections, and current config inheritance so the refactor preserves intended behavior where it still matters.
- Add contract tests for `AgentProvider`, `AgentLaunchSpec`, `RuntimeInfo`, and `NetworkPolicyPlan` so Claude and Codex share the same core guarantees and runtime backends can be swapped without changing application logic.
- Add policy merge tests that prove org/team widening and project/user narrowing work exactly one way, including blocked attempts that emit structured audit events and suggested request artifacts.
- Add integration tests for the main operator flows: Claude with only `anthropic-core`, Claude with `github-core` and `npm-public`, Codex with only `openai-core`, blocked access to private CIDRs and metadata endpoints, and clear pre-launch failure when a selected provider’s required core destinations are not permitted.
- Add tests for governed artifact handling: approved open skills flow through both providers, while provider-native plugins/hooks/rules are rendered only by the relevant adapter and never leak into core contracts.
- Add safety tests that cover destructive git, explicit network tools, fail-closed behavior when safety policy cannot load, and the shared verdict engine reached through both Claude and Codex integration paths.
- Keep the exit gate fixed for every milestone in `scc-sync-1.7.3`: `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pytest`, plus the safety-net plugin test suite when that package is touched.

## Assumptions And Defaults
- No active users means no long-term backward compatibility burden is accepted in core. One migration pass is cheaper and cleaner than carrying aliases forever.
- Provider-core destination sets are automatic and minimal for the selected provider only. GitHub, npm, PyPI, and other dev destinations are never implicitly enabled by choosing Claude or Codex.
- Open Agent Skills are the only intended shared portability surface. Plugins, hooks, rules, and marketplaces remain provider-native adapter integrations.
- Codex rules and plugin features are optional provider UX integrations, not the hard safety boundary. The hard boundary is SCC-owned runtime wrappers plus network topology and proxy enforcement.
- V1 network enforcement is HTTP/HTTPS-focused only, with no TLS interception and no generic arbitrary TCP/UDP policy surface yet.
- The first release target is plain OCI portability with SCC-owned images and no Docker Desktop dependency. Podman follows on the same contracts once the Claude/Codex vertical slice is stable.
