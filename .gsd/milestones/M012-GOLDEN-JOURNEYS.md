# M012 - Golden E2E Journeys, Claim Lock, And Pilot Readiness

## Purpose

Prove SCC's real organizational adoption journey end-to-end before adding
another runtime mode or enterprise feature layer.

M011 made the architecture easier to explain and change. M012 turns that
architecture into executable product proof:

```text
setup -> team/work context -> effective config explain -> governed materialization
-> Claude/Codex launch plan/start -> network/safety behavior -> audit/support artifacts
-> docs truth
```

M012 is not a product-feature milestone. It is a verification, claim-lock, and
pilot-readiness milestone for the v1 governed-runtime story.

Artifact consolidation note: the requested `M012-ROADMAP.md`,
`M012-CONTEXT.md`, `GOLDEN_JOURNEYS.md`, and `DOCS_CLAIM_MAP.md` content lives
as sections in this single milestone file. D054 keeps M012 planning in one
canonical file to avoid root-level planning sprawl and a drift-prone duplicate
docs claim source.

## Non-goals

- Do not implement devcontainer integration.
- Do not implement SSO.
- Do not implement SCIM.
- Do not implement SBOM or a compliance bundle.
- Do not create a project registry.
- Do not create an enterprise dashboard.
- Do not add new providers.
- Do not add broad compatibility paths for pre-production behavior.
- Do not add docs claims without a linked implementation owner plus test,
  diagnostic, or explicit manual-smoke status.

## M012-CONTEXT.md

SCC's v1 product model remains:

- project identity is the current repository/worktree `WorkContext`;
- one active team context applies to a session;
- org/team/project configuration flows through existing effective-config owners;
- projects may tighten inherited `network_policy`, but may not loosen it;
- Claude Code and Codex are the shipped providers;
- OCI is the provider-neutral runtime path;
- provider-native plugins, hooks, rules, and config files are adapter-owned render
  targets, not the hard enforcement plane;
- runtime wrappers, network topology, safety engine, and audit are SCC-owned.

The main M012 risk is duplication: building a new E2E framework, a second docs
truth source, or root-level planning sprawl would make SCC harder to maintain.
Use existing owners first:

- `tests/e2e/test_cli_journeys.py` for fast CLI journeys;
- `tests/fakes/` for in-memory adapters;
- `tests/test_docs_truthfulness.py` for docs-as-contract guardrails;
- `tests/test_config_explain.py` and `tests/test_effective_context_project_policy.py`
  for config explain and project-policy behavior;
- `tests/test_launch_preflight.py`, `tests/test_launch_preflight_guardrail.py`,
  and launch-flow characterization tests for provider launch parity;
- `tests/test_oci_egress_integration.py` and `tests/test_oci_sandbox_runtime.py`
  for network enforcement;
- safety engine tests plus provider safety adapter tests for command blocking;
- support/audit tests for operator evidence.

## M012-ROADMAP.md

| Slice | Status | Name | Scope | Done when |
| --- | --- | --- | --- | --- |
| S01 | Done | Planning, register, and claim inventory | This file, D054, `.gsd/PROJECT.md`, `AGENTS.md` | M012 has one canonical plan and no root planning sprawl. |
| S02 | Done | Fast setup/provider journey coverage | Reuse `tests/e2e/test_cli_journeys.py` for J01/J02 and add Codex dry-run parity | J01 and J02 run in normal CI without Docker; Claude and Codex dry-run contracts are asserted. |
| S03 | Done | WorkContext switching journey | Extend existing workspace/provider/session tests before adding helpers | J03 proves repo/worktree identity, provider/session separation, and quick-resume behavior. |
| S04 | Done | Governance decision trace journey | Extend config explain/effective-config tests and only then docs | J04 proves text/JSON parity for allowed, blocked, denied, and ignored policy changes. |
| S05 | Done | Provider launch plan parity | Reuse launch preflight/completion tests and fakes | J05 proves Claude/Codex dry-run, shared launch readiness across start, wizard, worktree start, dashboard start/resume, and adapter-owned provider artifacts. |
| S06 | Done | Network enforcement journey | Fake-runtime CI checks plus opt-in real-runtime smoke marker | J06 proves SCC proxy env determinism, deny defaults, provider-core allow behavior, and locked-down-web scope. |
| S07 | Done | Safety engine journey | Reuse safety engine and provider adapter tests | J07 proves destructive git, explicit network tools, fail-closed policy behavior, and Claude/Codex wrapper baseline. |
| S08 | Done | Audit/support journey | Reuse launch/safety/support bundle owners | J08 proves support bundle, launch audit, safety audit, provider/runtime/policy/work-context evidence. |
| S09 | Done | Docs claim lock and pilot docs | Claim assertions in `test_docs_truthfulness.py`; docs updates in `../scc-cli-docs` | J09 claim map statuses are true/partial/future/remove, Config Inheritance is enterprise-reviewable, and Enterprise Pilot is executable. |

## GOLDEN_JOURNEYS.md

Each journey must define fixture inputs, command or use-case calls, expected
state/output, expected audit/support evidence, docs claims covered, and test
level.

### J01 - Standalone Developer Setup

Persona: solo developer or evaluator.

Flow:

```bash
scc setup --standalone --non-interactive
scc doctor --provider claude
scc doctor --provider codex
scc start <repo> --standalone --dry-run --json --non-interactive --provider claude
scc start <repo> --standalone --dry-run --json --non-interactive --provider codex
```

Expected proof:

- setup works without org config;
- provider readiness is visible;
- Claude and Codex dry-run contracts are stable;
- no Docker daemon is required in normal CI;
- no launch audit file is written for dry-run-only standalone start.

Existing owner to reuse:

- `tests/e2e/test_cli_journeys.py` already covers standalone setup and Claude
  dry-run; extend it for Codex rather than creating a new harness.

### J02 - Org Onboarding And Team Switch

Persona: developer joining an organization.

Flow:

```bash
scc setup --org <org-source> --team <team> --non-interactive
scc team list --json
scc team switch <team> --json
scc config explain --json
```

Expected proof:

- organization source fetch/caching works through fixtures;
- team list/switch output is stable;
- selected team is persisted through the canonical config owner;
- config explain JSON and selected text assertions agree.

Existing owner to reuse:

- `tests/e2e/test_cli_journeys.py` already covers org setup, team list/switch,
  project validation, and config explain JSON.

### J03 - WorkContext Switch Across Repos And Worktrees

Persona: developer switching between projects.

Flow:

```bash
cd repo-a
scc start --dry-run --json --provider claude
cd repo-b
scc start --dry-run --json --provider codex
scc quick-resume
```

Expected proof:

- v1 project identity is repo/worktree `WorkContext`;
- provider/session separation is visible in local state and JSON output;
- quick resume filters by workspace/provider/team as documented;
- no project registry exists or is implied.

Existing owners to reuse:

- `contexts.py` tests;
- workspace provider persistence tests;
- quick-resume tests;
- e2e CLI journey owner for the product-level path.

### J04 - Governance Decision Trace

Persona: team lead or security reviewer.

Fixture:

- org default plugin and MCP;
- team plugin and MCP addition;
- project plugin and MCP addition;
- org-blocked plugin/MCP;
- denied project delegation;
- project attempt to widen `network_policy`.

Flow:

```bash
scc config explain --json
scc config explain --field denied
scc config explain --field network
```

Expected proof:

- inherited additions are visible;
- blocked items are visible;
- denied additions are visible;
- ignored project network-policy widening is visible;
- text and JSON surfaces tell the same story.

Existing owners to reuse:

- `tests/test_config_explain.py`;
- `tests/test_effective_context_project_policy.py`;
- `tests/test_config_inheritance.py`;
- e2e journey assertions after lower-level behavior is already locked.

### J05 - Provider Launch Plan Parity

Persona: platform engineer.

Flow:

```bash
scc start <repo> --dry-run --json --non-interactive --provider claude
scc start <repo> --dry-run --json --non-interactive --provider codex
```

Expected proof:

- provider-neutral launch path stays shared;
- provider-specific artifacts remain adapter-owned;
- provider-core destination sets are represented before launch;
- all five launch entrypoints continue using shared preflight/readiness owners:
  start command, wizard, worktree start, dashboard start, dashboard resume.

Existing owners to reuse:

- `commands/launch/preflight.py`;
- `commands/launch/completion.py`;
- `commands/launch/resolved_workspace.py`;
- `commands/launch/worktree_autostart.py`;
- launch preflight guardrail tests.

### J06 - Network Enforcement Journey

Persona: security reviewer.

Flow:

```bash
scc start <repo> --network-policy web-egress-enforced
# allowed provider-core destination succeeds
# private CIDR / link-local / metadata / IP literal blocked
# host proxy env cannot override SCC proxy
```

Expected proof:

- `web-egress-enforced` proxy env is SCC-owned and deterministic;
- private/link-local/metadata/IP-literal deny defaults are covered;
- provider-core destinations can pass when allowed;
- `locked-down-web` uses `--network=none`, or is clearly scoped to optional
  real-runtime smoke where fake tests cannot prove topology.

Existing owners to reuse:

- `tests/test_oci_egress_integration.py`;
- `tests/test_oci_sandbox_runtime.py`;
- `tests/test_egress_policy.py`;
- optional smoke marker for real Docker/OCI only.

### J07 - Safety Engine Journey

Persona: security reviewer or developer.

Flow:

```bash
git push --force
git reset --hard
curl https://example.com
ssh host
```

Expected proof:

- destructive git is blocked;
- explicit network tools are handled;
- policy parse/load failures fail closed;
- Claude and Codex adapters share the same baseline safety engine.

Existing owners to reuse:

- `tests/test_safety_engine.py`;
- `tests/test_git_safety_rules.py`;
- `tests/test_network_tool_rules.py`;
- provider safety adapter tests;
- safety audit tests.

### J08 - Audit And Support Journey

Persona: support engineer or pilot reviewer.

Flow:

```bash
scc support bundle
scc support launch-audit
scc support safety-audit
```

Expected proof:

- support bundle exists and is bounded/redacted;
- launch audit contains provider/runtime/policy/work-context evidence;
- safety audit contains policy/verdict evidence;
- dry-run vs real-start behavior is explicit.

Existing owners to reuse:

- support bundle tests;
- launch audit tests;
- safety audit tests;
- local audit event sink tests.

### J09 - Docs-As-Contract Journey

Persona: maintainer, security reviewer, pilot reviewer.

Flow:

- every security/network/provider/audit claim in selected docs has:
  - docs location;
  - implementation owner;
  - test or diagnostic;
  - status: `true`, `partial`, `future`, or `remove`.

Expected proof:

- unsupported future features are not documented as shipped;
- stale security and inheritance claims fail a test or are marked for removal;
- docs claim map is not a second root-level source of truth.

Existing owner to reuse:

- add executable assertions to `tests/test_docs_truthfulness.py`;
- keep the human claim inventory in this file until executable checks replace it.

## DOCS_CLAIM_MAP.md

This is the initial M012 claim inventory. It is deliberately stored in this
milestone file instead of a root-level `DOCS_CLAIM_MAP.md`; executable truth
checks belong in `tests/test_docs_truthfulness.py`.

| Claim | Docs location | Implementation owner | Current proof | Status | M012 action |
| --- | --- | --- | --- | --- | --- |
| SCC is a provider-neutral governed runtime with Claude and Codex as shipped providers. | `architecture/overview.mdx` | provider registry, provider adapters, launch dependencies | provider tests, registry tests, dry-run JSON | true | Link to J01/J05 once tests are named. |
| All five launch paths use shared preflight. | `architecture/overview.mdx` | `commands/launch/preflight.py` plus launch routing helpers | launch preflight guardrails | true | J05 should make this product-level and keep guardrails. |
| Container isolation and network egress are separate controls. | `architecture/security-model.mdx`, `architecture/overview.mdx` | OCI runtime, egress topology, network policy core | OCI/network tests | true | Keep wording tied to HTTP/HTTPS IPv4 scope. |
| `web-egress-enforced` uses internal-only agent network plus Squid sidecar. | `architecture/security-model.mdx` | `adapters/egress_topology.py`, `adapters/oci_sandbox_runtime.py` | OCI egress integration tests | true | J06 should add journey-level claim coverage. |
| Host proxy env cannot override SCC proxy in enforced mode. | security docs should mention only if useful | `adapters/oci_sandbox_runtime.py` | `test_oci_egress_integration.py` | true | Decide whether this is docs-worthy or test-only. |
| `locked-down-web` uses no external network. | `architecture/security-model.mdx` | `OciSandboxRuntime` network args | OCI sandbox runtime tests | partial | J06 should decide fake assertion vs optional real smoke note. |
| Raw TCP/UDP beyond HTTP(S) is not filtered by v1 proxy. | `architecture/security-model.mdx` | network policy docs/source scope | docs truth guardrails | true | Keep as explicit limitation. |
| Security blocks cannot be overridden directly but can be overridden by audited, time-bounded policy exceptions. | `architecture/security-model.mdx`, `architecture/config-inheritance.mdx` | exception application/evaluation owners | evaluation tests | true | Config Inheritance must use the same wording. |
| Projects can tighten inherited `network_policy` but cannot loosen it. | `architecture/config-inheritance.mdx`, `enterprise-pilot.mdx` | effective-config project policy owner | project-policy tests, config explain tests | true | Rewrite Config Inheritance with examples and ignored widening output. |
| `scc config explain` shows effective config and ignored policy changes. | `architecture/config-inheritance.mdx`, `enterprise-pilot.mdx` | config explain command/presentation | config explain tests, e2e journey | true | Add text/JSON parity journey assertions. |
| Support bundle, launch audit, and safety audit provide pilot evidence. | `enterprise-pilot.mdx`, support docs | support/audit application owners | support/audit tests | partial | J08 should verify required fields and docs should show exact commands. |
| Enterprise pilot blueprint can be followed by a small organization. | `enterprise-pilot.mdx` | docs plus existing CLI commands | docs deploy only today | partial | S09 should add runnable sample org/team/project config and expected commands. |
| Devcontainer integration, SSO, SCIM, SBOM, project registry, and enterprise dashboard are not shipped v1 controls. | `enterprise-pilot.mdx` | roadmap/non-goal docs | docs text only | true | Keep as explicit non-goals; do not add implementation in M012. |

## Recommended PR Slicing

Prefer one PR per slice unless a slice is docs-only and tightly coupled to a
source behavior change.

1. **PR 1 - M012 planning and register alignment**
   - this milestone file;
   - D054;
   - `.gsd/PROJECT.md` and `AGENTS.md` updates.
2. **PR 2 - Fast setup/provider golden journeys**
   - extend `tests/e2e/test_cli_journeys.py`;
   - prove J01/J02 and Claude/Codex dry-run parity.
3. **PR 3 - WorkContext and launch parity journeys**
   - J03/J05;
   - reuse launch preflight and workspace/provider persistence tests.
4. **PR 4 - Governance trace and Config Inheritance docs**
   - J04;
   - rewrite `architecture/config-inheritance.mdx`;
   - add docs truth assertions for inheritance claims.
5. **PR 5 - Network and safety journeys**
   - J06/J07 fake-runtime CI tests;
   - optional real-runtime smoke marker;
   - no Docker requirement in normal CI.
6. **PR 6 - Audit/support and pilot blueprint**
   - J08/J09;
   - support/audit field assertions;
   - executable Enterprise Pilot examples and claim-lock guardrails.

## Exact First Implementation Slice

After S01 lands, implement **S02 - Fast setup/provider golden journeys**.

Problem:

- J01/J02 already exist partly, but the journey is not named, Codex dry-run is
  missing from the E2E product path, and the tests do not yet make the product
  contract obvious to reviewers.

Why it matters:

- A municipality, agency, or company will first ask whether a developer can set
  up SCC, select an org/team, explain effective config, and preview Claude/Codex
  launches without needing Docker in CI.

Current owner:

- `tests/e2e/test_cli_journeys.py`

Proposed canonical owner:

- Same file. Do not add a new E2E framework.

Reuse:

- existing `CliRunner`;
- existing `_run_scc_subprocess`;
- existing `e2e_config_paths` fixture;
- existing org fixture pattern in `_enterprise_org_config`;
- existing fake adapters only if a full start path needs them beyond dry-run.

Move/merge/delete:

- Rename or split current tests only when it makes the journey names clear.
- Add Codex dry-run assertions beside the existing Claude dry-run assertions.
- Do not create `tests/e2e/helpers.py` unless duplication becomes real.

Acceptance criteria:

- J01 standalone setup proves `setup --standalone`, project init, provider doctor
  or readiness-equivalent output, and Claude/Codex dry-run JSON.
- J02 org onboarding proves org setup, team list/switch, config explain JSON, and
  one stable text assertion where UX matters.
- Normal CI does not require Docker.
- No product source behavior changes are introduced unless the tests expose a
  real bug.

Validation:

```bash
uv run pytest tests/e2e/test_cli_journeys.py -q --no-cov
uv run ruff check
uv run ruff format --check
uv run mypy src/scc_cli
uv run pytest -q --no-cov
git diff --check
```

Docs:

- No docs update is required in S02 unless command output or behavior changes.
- If tests expose stale docs while implementing S02, update docs in the same
  slice and run `bun run astro check` in `../scc-cli-docs`.

Risk and rollback:

- Low runtime risk if S02 is test-only.
- Rollback is deleting the added E2E assertions.
- If dry-run needs adapter fakes, keep them local to tests and reuse
  `tests/fakes/`; do not add production abstractions.

S02 validation:

- `uv run pytest tests/e2e/test_cli_journeys.py -q --no-cov` passed: 5 passed.
- `uv run ruff check` passed.
- `uv run ruff format --check` passed.
- `uv run mypy src/scc_cli` passed.
- `uv run pytest -q --no-cov` passed: 5224 passed, 14 skipped.
- `git diff --check` passed.

S03 implementation notes:

- `WorkContext.unique_key` now includes provider identity so the same
  team/repo/worktree can maintain separate Claude and Codex quick-resume
  contexts.
- Session recording now deduplicates by workspace, branch, and provider
  identity; missing-provider records are treated as the default Claude identity.
- Session lookup, container update, container lookup, and removal can accept an
  explicit provider identity, preventing provider-specific operations from
  touching the other provider's session entry.
- The stale launch characterization prose claiming Quick Resume lost provider
  identity was removed; the launch test now describes the current provider
  threading behavior.

S03 validation:

- `uv run pytest tests/test_contexts.py tests/test_sessions.py tests/test_session_provider_id.py tests/test_launch_preflight_characterization.py tests/e2e/test_cli_journeys.py -q --no-cov` passed: 138 passed.
- `uv run ruff check` passed.
- `uv run ruff format --check` passed.
- `uv run mypy src/scc_cli` passed.
- `uv run pytest -q --no-cov` passed: 5235 passed, 14 skipped.
- `git diff --check` passed.

S04 implementation notes:

- `tests/e2e/test_cli_journeys.py` now includes a governance decision trace
  journey covering org defaults, allowed team plugins, allowed project plugins,
  blocked project plugins, blocked project MCP servers, denied team MCP
  delegation, ignored project network-policy widening, and text/JSON parity.
- The journey uses fake org fetch/provider onboarding and remains part of normal
  CI without Docker or network access.
- Existing config owners remain canonical: `compute_effective_config` owns merge
  decisions and `config explain` owns text/JSON presentation.

S04 validation:

- `uv run pytest tests/e2e/test_cli_journeys.py -q --no-cov` passed: 6 passed.
- `uv run pytest tests/test_config_explain.py tests/test_effective_context_project_policy.py tests/e2e/test_cli_journeys.py -q --no-cov` passed: 46 passed.

S05 implementation notes:

- `tests/test_launch_preflight_guardrail.py` now requires every migrated launch
  path to call the shared `resolve_launch_provider`,
  `collect_launch_readiness`, and `ensure_launch_ready` sequence.
- `tests/test_import_boundaries.py` now prevents
  `application.start_session` from importing concrete Claude/Codex providers or
  renderers; provider-native artifact rendering remains owned by adapters behind
  the `AgentProvider` port.
- Existing dashboard, worktree, provider-rendering, and E2E tests provide the
  executable launch parity journey without requiring Docker in normal CI.

S05 validation:

- `uv run pytest tests/test_launch_preflight_guardrail.py tests/test_import_boundaries.py::TestProviderArtifactOwnershipBoundary tests/test_application_start_session.py::TestAgentProviderRenderArtifacts tests/test_dashboard_provider_resume.py tests/test_worktree_autostart.py tests/e2e/test_cli_journeys.py -q --no-cov` passed: 26 passed.

S06 implementation notes:

- `tests/test_destination_registry.py` now asserts provider-core destination
  sets use DNS hosts, not direct IP literals, so provider-core allow rules cannot
  punch IP-literal holes in the egress ACL.
- `tests/test_egress_policy.py` now proves provider-core ACLs allow the
  registered host and leave unrelated direct IP targets to the terminal
  `http_access deny all`.
- The egress policy docstring now states the actual invariant: explicit deny
  rules cover private/link-local/metadata ranges, and the terminal deny-all
  blocks unlisted destinations including direct IP-literal attempts.
- `locked-down-web` remains fake-runtime verified through OCI command
  construction (`--network none`); real Docker/OCI smoke remains optional.

S06 validation:

- `uv run pytest tests/test_egress_policy.py tests/test_destination_registry.py tests/test_oci_egress_integration.py tests/test_oci_sandbox_runtime.py -q --no-cov` passed: 140 passed.

S07 implementation notes:

- `tests/test_safety_adapter_audit.py` now compares Claude and Codex full-chain
  adapter verdicts for destructive git, hard reset, explicit network tools, and
  safe commands.
- Existing safety owners prove fail-closed policy loading, network-tool
  detection, destructive git rules, and host/standalone safety engine contract
  parity.

S07 validation:

- `uv run pytest tests/test_safety_engine.py tests/test_safety_policy_loader.py tests/test_safety_adapter_audit.py tests/test_claude_safety_adapter.py tests/test_codex_safety_adapter.py tests/test_network_tool_rules.py tests/test_safety_eval_contract.py -q --no-cov` passed: 119 passed.

S08 implementation notes:

- Support bundles now include a `work_context` section with explicit states:
  `not_requested`, `not_found`, `unavailable`, or `available`.
- When a workspace has a recorded context, the bundle includes team, repo root,
  worktree path/name, branch, provider, last session, and pin state.
- Existing support owners continue to provide launch audit, safety audit,
  effective safety policy, runtime/egress, selected provider, config, org config,
  doctor, and governed-artifact diagnostics.

S08 validation:

- `uv run pytest tests/test_support_bundle.py tests/test_launch_audit_support.py tests/test_safety_audit.py tests/test_safety_adapter_audit.py -q --no-cov` passed: 54 passed.

S09 implementation notes:

- `../scc-cli-docs/src/content/docs/architecture/config-inheritance.mdx` now
  documents actual org -> team -> project merge behavior, project
  `network_policy` narrow-only behavior, ignored widening, work-context project
  identity, and provider-separated sessions.
- `../scc-cli-docs/src/content/docs/reference/docs-claim-map.mdx` records
  security, network, provider, audit, and inheritance claims with docs location,
  implementation owner, test/diagnostic, and status (`true`, `partial`,
  `future`, or `remove`).
- `../scc-cli-docs/src/content/docs/guides/organization/enterprise-pilot.mdx`
  now includes an executable sample org config, sample `.scc.yaml`, expected
  commands, and pilot review signals for a small organization.
- `../scc-cli-docs/src/content/docs/architecture/security-model.mdx` no longer
  overclaims IP literals as part of the explicit pre-allow default deny list;
  it documents terminal deny-all behavior for unlisted destinations instead.
- `tests/test_docs_truthfulness.py` now checks the sibling docs repo for M012
  claim-map, config-inheritance, security wording, and enterprise-pilot journey
  coverage when the clean two-repo workspace is present.

S09 validation:

- `uv run pytest tests/test_docs_truthfulness.py tests/e2e/test_cli_journeys.py -q --no-cov` passed: 46 passed.
- `bun run astro check` passed in `../scc-cli-docs`: 0 errors, 1 existing Astro inline-script hint.

## Validation Gates For M012

Source gates:

```bash
uv run ruff check
uv run ruff format --check
uv run mypy src/scc_cli
uv run pytest -q --no-cov
git diff --check
```

Docs gate when docs change:

```bash
cd ../scc-cli-docs
bun run astro check
```

Optional smoke gates:

- real Docker/OCI network tests must be behind an explicit pytest marker;
- normal CI must remain fake-runtime/dry-run based.

Final M012 validation:

- `uv run ruff check` passed.
- `uv run ruff format --check` passed after formatting three test files.
- `uv run mypy src/scc_cli` passed: 302 source files, 0 issues.
- `uv run pytest tests/test_sessions.py tests/test_contexts.py tests/test_session_provider_id.py tests/test_workspace_provider_persistence.py tests/test_s02_provider_sessions.py -q --no-cov` passed after the post-review session cleanup: 128 passed.
- `uv run pytest -q --no-cov` passed after the post-review session cleanup: 5250 passed, 14 skipped.
- `uv run pytest tests/test_file_sizes.py -q -s --no-cov` passed: 301 files
  scanned, 1 warning-zone file, 0 failing files.
- `git diff --check` passed for source and docs.
- `bun run astro check` passed in `../scc-cli-docs`: 0 errors, 1 existing
  inline-script hint.
- Antigravity final verification passed:
  - iteration 1: green, MIN_SCORE 9, two non-blocking session cleanup findings;
  - iteration 2 after cleanup: green, MIN_SCORE 10, no findings;
  - artifacts:
    `.codex/artifacts/antigravity-peer-loop-m012-final-readiness-verification-20260630T093959Z.md`
    and
    `.codex/artifacts/antigravity-peer-loop-m012-final-readiness-verification-iteration-2-20260630T094613Z.md`.
