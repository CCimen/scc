---
id: M003
title: "Portable Runtime And Enforced Web Egress"
status: complete
completed_at: 2026-04-04T11:19:22.370Z
key_decisions:
  - D012: RuntimeProbe protocol as canonical detection surface — probe() -> RuntimeInfo, DockerRuntimeProbe as sole adapter, bootstrap shares single probe, tokenizer guardrail prevents regression
  - D013: OCI sandbox backend as parallel adapter — bootstrap selects based on RuntimeInfo.preferred_backend; Docker Desktop path untouched; credential handling differs fundamentally between backends
  - D014: Enforced web-egress via internal Docker network + dual-homed Squid proxy sidecar — physical isolation boundary; agent on internal-only network cannot bypass proxy; pure ACL compilation separated from infrastructure management
  - D015: Enterprise egress model articulated — web-egress-enforced is normal cloud mode, locked-down-web is intentional no-web posture; org owns baseline + delegation, teams widen within bounds, project/user narrow only; one team context per session; topology is hard control, wrappers are defense-in-depth
key_files:
  - src/scc_cli/ports/runtime_probe.py
  - src/scc_cli/adapters/docker_runtime_probe.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/adapters/egress_topology.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/core/image_contracts.py
  - src/scc_cli/core/egress_policy.py
  - src/scc_cli/core/destination_registry.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/application/launch/preflight.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/ports/models.py
  - src/scc_cli/doctor/checks/environment.py
  - images/scc-base/Dockerfile
  - images/scc-agent-claude/Dockerfile
  - images/scc-egress-proxy/Dockerfile
  - images/scc-egress-proxy/squid.conf.template
  - images/scc-egress-proxy/entrypoint.sh
  - README.md
  - tests/test_runtime_probe.py
  - tests/test_runtime_detection_hotspots.py
  - tests/test_image_contracts.py
  - tests/test_oci_sandbox_runtime.py
  - tests/test_bootstrap_backend_selection.py
  - tests/test_start_session_image_routing.py
  - tests/test_egress_policy.py
  - tests/test_egress_topology.py
  - tests/test_oci_egress_integration.py
  - tests/test_destination_registry.py
  - tests/test_launch_preflight.py
  - tests/test_doctor_checks.py
  - tests/test_docs_truthfulness.py
lessons_learned:
  - When building a multi-layer enforcement system (egress), keep each layer independently testable: pure policy logic as plain functions, infrastructure management as a separate adapter, and orchestration in the existing runtime adapter. This made 49 tests possible without Docker.
  - Centralize subprocess error handling per adapter via a local _run_docker helper rather than sharing one across adapters — avoids coupling while maintaining consistent error wrapping patterns.
  - For docs truthfulness, regex scanning is sufficient for string-literal and prose content; reserve the tokenize module for Python identifier scanning. Dual scanning strategy keeps guardrails precise.
  - Provider destination registries should start as plain typed dicts, not frameworks. 17 tests cover the entire registry because the implementation is trivial.
  - When adding diagnostic sections to support bundles, wrap each data source in independent try/except — the bundle is most needed exactly when subsystems are broken.
  - Milestone-level success criteria should be formally populated during planning, not compensated at validation time by aggregating slice criteria. S05 validation worked but was more labor-intensive than necessary.
  - The preferred_backend field uses literal strings rather than enum by design — keeps RuntimeInfo lightweight. But if a third backend is added, revisit this decision.
  - Container images defined as Dockerfiles without a build/push pipeline create a gap between tested code and operational readiness. Future milestones should include image distribution strategy.
---

# M003: Portable Runtime And Enforced Web Egress

**Delivered a portable OCI sandbox backend (no Docker Desktop dependency) with topology-enforced web egress via Squid proxy sidecar, provider destination validation, operator diagnostics, and docs truthfulness guardrails — adding 178 net new tests to reach 3464 total.**

## What Happened

M003 delivered five slices that together create a portable container runtime and a hard-enforced web-egress boundary for SCC.

**S01 — Capability-based runtime model.** Replaced scattered docker.check_docker_available() heuristics with a single RuntimeProbe protocol (ports/runtime_probe.py) behind the adapter boundary. DockerRuntimeProbe is the sole adapter calling docker/core helpers defensively. RuntimeInfo was extended with version, desktop_version, daemon_reachable, and sandbox_available fields. DockerSandboxRuntime and the dashboard orchestrator were migrated to probe-backed detection. A tokenizer-based guardrail test prevents regression.

**S02 — OCI backend and image contracts.** Created OciSandboxRuntime implementing the full SandboxRuntime protocol via docker create/start/exec — no Docker Desktop dependency. Introduced frozen ImageRef dataclass with parsing roundtrip and SCC image constants. Added rootless detection and preferred_backend to RuntimeInfo. Bootstrap probes at construction time and selects OciSandboxRuntime or DockerSandboxRuntime. Image routing is backend-aware. Dockerfiles defined for scc-base and scc-agent-claude images.

**S03 — Enforced web-egress topology.** Built three independent layers: pure egress policy logic (build_egress_plan, compile_squid_acl), NetworkTopologyManager infrastructure adapter, and OCI adapter integration. The enforcement boundary is an internal-only Docker network with a dual-homed Squid proxy sidecar — the agent physically cannot bypass the proxy. For locked-down-web, the agent gets --network=none. For open, behavior is unchanged. Squid proxy sidecar image defined with ACL injection entrypoint.

**S04 — Policy integration and diagnostics.** Provider destination registry maps named sets (anthropic-core, openai-core) to typed objects. SandboxSpec carries resolved destination sets through the launch pipeline. Enforced-mode preflight validates destination resolvability before launch. Doctor check reports runtime backend. Support bundle includes effective egress section with per-subsection resilience.

**S05 — Docs truthfulness and guardrails.** Purged all stale network-mode vocabulary from source/tests/docs. README no longer claims Docker Desktop as hard dependency. Added 5 guardrail tests preventing vocabulary drift regression.

The test suite grew from 3286 (S01 baseline) to 3464 (S05 close), adding 178 net new tests with zero regressions. All three exit gates pass: ruff clean, mypy 0 issues in 249 files, 3437 passed + 23 skipped + 4 xfailed.

## Success Criteria Results

## Success Criteria Results

Milestone-level success criteria were not formally populated in the DB. Verification was conducted via comprehensive slice-level criteria (all detailed in M003-VALIDATION.md).

### Portable OCI Runtime
- [x] **RuntimeProbe protocol replaces scattered detection** — S01 delivered RuntimeProbe with probe() -> RuntimeInfo, tokenizer guardrail prevents regression (17 targeted tests)
- [x] **OciSandboxRuntime implements full SandboxRuntime protocol** — S02 delivered create/start/exec based adapter with 34 unit tests
- [x] **Bootstrap auto-selects backend based on runtime capabilities** — S02/T04 delivered probe-at-construction-time selection (4 integration tests)
- [x] **SCC-owned image contracts and Dockerfiles defined** — S02 delivered frozen ImageRef, constants, and 3 Dockerfiles (23 image contract tests)

### Enforced Web Egress
- [x] **Internal Docker network + Squid proxy as hard enforcement boundary** — S03 delivered NetworkTopologyManager + proxy sidecar (49 tests across 3 layers)
- [x] **Pure egress policy and ACL compilation** — S03/T01 delivered build_egress_plan() and compile_squid_acl() (19 tests)
- [x] **OCI adapter integrates topology for all 3 network modes** — S03/T03 delivered enforced/locked-down/open handling with guardrail test
- [x] **Provider destination sets flow through to egress plan** — S04 delivered registry → SandboxSpec → adapter pipeline (17 + 7 tests)

### Operator Diagnostics and Docs
- [x] **Doctor check reports runtime backend** — S04/T03 delivered check_runtime_backend() (4 tests)
- [x] **Support bundle includes effective egress section** — S04/T03 delivered with per-subsection resilience (2 tests)
- [x] **Docs truthful to actual enforcement** — S05 purged stale vocabulary, updated README (5 guardrail tests)

### Exit Gate
- [x] **ruff clean** — All checks passed ✅
- [x] **mypy clean** — 0 issues in 249 source files ✅
- [x] **Full test suite green** — 3437 passed, 23 skipped, 4 xfailed (3464 total) ✅

## Definition of Done Results

## Definition of Done Results

- [x] **All slices complete** — S01 ✅, S02 ✅, S03 ✅, S04 ✅, S05 ✅ (all checked in roadmap)
- [x] **All slice summaries exist** — S01-SUMMARY.md through S05-SUMMARY.md verified on disk
- [x] **Cross-slice integration points work** — VALIDATION.md confirms all 6 boundary map edges (S01→S02, S01→S03, S02→S03, S02→S04, S03→S04, S03+S04→S05) substantiated by code and test evidence
- [x] **No cross-slice boundary mismatches** — All produces/consumes relationships verified
- [x] **Exit gate passes on final codebase** — Fresh run confirms ruff clean, mypy clean, 3464 tests (3437 passed, 23 skipped, 4 xfailed)
- [x] **Net test growth** — +178 tests from milestone start (3286) to close (3464)
- [x] **Code changes are substantive** — git diff shows 147 non-.gsd/ files changed (1293 insertions, 10818 deletions)

## Requirement Outcomes

## Requirement Outcomes

### R001 — Maintainability (non-functional)
**Status: validated → validated (no transition, continued advancement)**

R001 was already validated by M002/S05. M003 advanced it further across all 5 slices without regression:

- **S01:** Replaced scattered detection heuristics with typed RuntimeProbe protocol + tokenizer guardrail
- **S02:** OciSandboxRuntime follows adapter-boundary conventions (D003/D012), centralizes error handling in _run_docker helper, frozen typed ImageRef module
- **S03:** Three-layer egress enforcement (pure policy → infra adapter → runtime integration), each independently testable; local _run_docker avoids cross-adapter coupling
- **S04:** Pure destination registry in core, SandboxSpec threading respects frozen dataclass contracts, doctor checks respect import boundary, support-bundle per-subsection resilience
- **S05:** 5 guardrail tests mechanically prevent vocabulary drift in user-facing strings and docs

No requirement status transition needed — R001 remains validated with strengthened evidence.

## Deviations

Minor deviations from plans, all documented in task summaries:
- S01/T03: Switched from regex to tokenize for guardrail scanning after regex falsely flagged docstrings.
- S02/T03: Used sleep infinity as container entrypoint instead of /bin/bash.
- S02/T04: Updated test_bootstrap.py to accept either runtime type due to environment-dependent probe results.
- S03: All three tasks produced more tests than planned (additive coverage improvements).
- S04/T02: Used TYPE_CHECKING guard for DestinationSet import to avoid circular dependency.
- S04/T03: Used bootstrap.get_default_adapters() instead of direct adapter import for runtime probe (cleaner than planned).
- S05/T01: Transient edit-tool failures on README.md resolved via absolute paths and sed fallback.
No plan-invalidating deviations occurred.

## Follow-ups

- Container images (scc-base, scc-agent-claude, scc-egress-proxy) are defined as Dockerfiles but not built or pushed to any registry. Image distribution strategy needed before OCI path works end-to-end.
- HTTPS CONNECT method through Squid proxy is configured in squid.conf.template but not explicitly integration-tested.
- Enforcement is IPv4-only in v1 (disclosed in README). IPv6 is deferred.
- Destination registry is hardcoded with anthropic-core and openai-core. Config-driven registry deferred until provider set grows.
- preferred_backend uses literal strings; revisit if a third backend is added.
- M004 (Cross-Agent Runtime Safety) is the next milestone.
- M005 reserves repo-wide decomposition, guardrail restoration, xfail removal, and the broader coverage campaign.
