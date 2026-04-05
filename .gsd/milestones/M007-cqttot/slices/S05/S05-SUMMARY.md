---
id: S05
parent: M007-cqttot
milestone: M007-cqttot
provides:
  - rendered_bytes-based AgentSettings model
  - auth_check() protocol method on AgentProvider
  - 32 truthfulness guardrail tests covering M007 decisions
  - 25 image structure tests
  - 7 config persistence transition tests
  - Codex workspace-scoped config ownership
  - Runtime permission normalization
  - File-based Codex auth storage
  - Fail-closed active launch paths (no silent Claude fallback)
requires:
  - slice: S01
    provides: ProviderRuntimeSpec, PROVIDER_REGISTRY, fail-closed get_runtime_spec()
  - slice: S02
    provides: Provider-parameterized session/audit helpers
  - slice: S03
    provides: Doctor provider-awareness, check_provider_auth, typed provider errors
  - slice: S04
    provides: Legacy Claude constants isolated from core
affects:
  []
key_files:
  - README.md
  - pyproject.toml
  - src/scc_cli/ports/models.py
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/core/provider_registry.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/adapters/claude_agent_runner.py
  - src/scc_cli/adapters/codex_agent_runner.py
  - src/scc_cli/adapters/claude_agent_provider.py
  - src/scc_cli/adapters/codex_agent_provider.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/doctor/checks/environment.py
  - images/scc-base/Dockerfile
  - images/scc-agent-codex/Dockerfile
  - tests/test_docs_truthfulness.py
  - tests/test_oci_sandbox_runtime.py
  - tests/test_image_structure.py
key_decisions:
  - D044: Expanded S05 from docs-only to full architecture reconciliation — decisions must be implemented, not just recorded
  - D033 implemented: Codex launches with --dangerously-bypass-approvals-and-sandbox (runner-owned)
  - D035 implemented: AgentSettings uses rendered_bytes, runners own serialization format
  - D037 implemented: auth_check() on AgentProvider protocol with three-tier validation
  - D038/D042 implemented: fresh launch always writes config deterministically, resume skips injection
  - D039 implemented: runtime permission normalization after container start
  - D040 implemented: Codex always gets cli_auth_credentials_store='file'
  - D041 implemented: Codex uses workspace-scoped config, Claude uses home-scoped
  - D032 implemented: all active launch paths fail closed on missing provider — no silent Claude fallback
  - D030 implemented: product name 'Sandboxed Code CLI' across all surfaces
  - D-001 corrected from 'Sandboxed Coding CLI' to 'Sandboxed Code CLI'
patterns_established:
  - AgentRunner.build_settings() → rendered_bytes pattern for format-agnostic settings injection
  - AgentProvider.auth_check() → AuthReadiness pattern for adapter-owned auth readiness
  - Runtime permission normalization step in OCI launch path (after container start, before settings injection)
  - settings_scope field on ProviderRuntimeSpec ('home' vs 'workspace') for provider-native config layering
  - .git/info/exclude for repo cleanliness of SCC-managed dirs (non-mutating, best-effort)
  - Decision-reconciliation guardrail tests that verify accepted decisions are implemented in code
  - Config persistence transition tests (governed→standalone, teamA→teamB, cross-provider, idempotent)
observability_surfaces:
  - auth_check() returns AuthReadiness with ready, mechanism, and guidance fields — surfaced via doctor
  - Runtime permission normalization logs failures as warnings but does not block launch
  - Config freshness guarantee: fresh launch always writes SCC-managed layer, even when empty
drill_down_paths:
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T04-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T05-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T06-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T07-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T08-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T09-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T10-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T11-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S05/tasks/T12-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-05T16:03:05.145Z
blocker_discovered: false
---

# S05: Product naming, documentation truthfulness, and milestone validation

**Expanded from docs-only to full architecture reconciliation — implemented D033/D035/D037/D038/D039/D040/D041/D042 in code and tests, eliminated active-launch Claude fallbacks, hardened images, and validated all M007 decisions against the codebase with 32 truthfulness guardrail tests; 4820 tests pass.**

## What Happened

S05 was originally planned as a single-task docs/naming slice (rename README, update pyproject.toml, add 5 truthfulness tests). User override D044 expanded it to reconcile all M007 architecture decisions against actual code — decisions D033 through D042 had been accepted but not yet implemented.

The reconciliation work delivered 12 tasks across four categories:

**Product naming and truthfulness (T01, T12):** README title changed to 'SCC — Sandboxed Code CLI'. pyproject.toml description made provider-neutral. D-001 in DECISIONS.md corrected from 'Sandboxed Coding CLI' to 'Sandboxed Code CLI'. 15 new truthfulness guardrail tests verify M007 deliverables exist in code (ProviderRuntimeSpec, fail-closed dispatch, doctor auth, core constants cleanliness) and that reconciliation decisions (D033/D035/D037/D040/D041) are implemented.

**Settings serialization and config ownership (T02, T03, T05, T08):** AgentSettings refactored from `content: dict` to `rendered_bytes: bytes` + `path` + `suffix` — runners now own serialization format (JSON for Claude, TOML for Codex via minimal stdlib-only serializer). OCI runtime writes bytes verbatim without format assumption. Codex settings use workspace-scoped .codex/config.toml (D041) with .git/info/exclude for repo cleanliness. SCC-managed defaults (`cli_auth_credentials_store='file'`) always injected into Codex config (D040). Fresh launch deterministically writes config even when empty; resume skips injection to preserve session context (D038/D042).

**Launch hardening and fail-closed dispatch (T04, T07):** CodexAgentRunner launches with `--dangerously-bypass-approvals-and-sandbox` per D033. All active launch paths (start_session, dependencies, flow_interactive, worktree_commands) now use three-step fail-closed provider resolution — missing provider wiring raises typed errors (InvalidProviderError, ProviderNotReadyError) instead of silently defaulting to Claude. Legacy read/migration boundaries preserved per D032.

**Auth, permissions, and image hardening (T06, T09, T10):** auth_check() added to AgentProvider protocol with three-tier validation (volume existence → file content → parseable JSON). Both Claude and Codex adapters implement it; doctor delegates to adapter-owned results with truthful wording ('auth cache present' not 'logged in'). Runtime permission normalization step added to OCI launch path — docker exec sets provider config dir 0700, auth files 0600, uid 1000 after container start. scc-base Dockerfile now pre-creates both .claude and .codex dirs. scc-agent-codex pins Codex CLI version via ARG. 25 structural tests cover all image Dockerfiles.

**Persistence determinism (T11):** 7 runtime-layer tests prove config persistence is deterministic across governed→standalone, teamA→teamB, settings→no-settings, cross-provider, and idempotent transitions.

## Verification

All three slice verification gates pass:
1. `uv run ruff check` — zero errors (exit 0)
2. `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` — 50/50 passed (exit 0)
3. `uv run pytest -q` — 4820 passed, 23 skipped, 2 xfailed, 0 failed (exit 0, threshold ≥4750 met)

## Requirements Advanced

- R001 — S05 reconciled 10 architecture decisions into working code with 100 net new tests, ensuring provider-neutral contracts (settings serialization, auth readiness, config layering, fail-closed dispatch) are real and tested, not just documented. 32 truthfulness guardrail tests mechanically prevent regression.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

S05 expanded from 1 task (docs/naming only) to 12 tasks (full architecture reconciliation) per user override D044. Test file paths in some tasks differ from plan (tests/ root instead of tests/adapters/ or tests/doctor/) — follows existing repo convention. T03 added minimal _serialize_toml stdlib helper instead of tomli_w dependency. T08 updated one existing test assertion invalidated by D038 fresh-launch-always-writes semantics.

## Known Limitations

Test count (4820 passed) includes 23 skips and 2 xfails that are pre-existing from prior milestones, not S05 regressions. Image Dockerfile tests are structural (parsing) — they do not build or run actual Docker images. Auth readiness checks require Docker to be running for volume inspection; in test they are mocked.

## Follow-ups

- `scc auth login/status/logout` CLI commands — the auth_check() model supports them (D037).
- Image build/push pipeline for scc-agent-codex (currently operator-built).
- Fine-grained volume splitting (auth-only vs ephemeral) for enterprise data-retention (D036).
- Dashboard provider switching TUI feature (dashboard 'a' key).
- Container labels (scc.provider=<id>) for external tooling discovery.
- Podman support on the same SandboxRuntime contracts.

## Files Created/Modified

- `README.md` — Title changed from 'Sandboxed Claude CLI' to 'Sandboxed Code CLI'
- `pyproject.toml` — Description made provider-neutral ('Run AI coding agents...')
- `src/scc_cli/ports/models.py` — AgentSettings refactored: content:dict → rendered_bytes:bytes + suffix:str
- `src/scc_cli/ports/agent_provider.py` — Added auth_check() → AuthReadiness to AgentProvider protocol
- `src/scc_cli/core/contracts.py` — Added settings_scope field to ProviderRuntimeSpec
- `src/scc_cli/core/provider_registry.py` — Codex settings_scope set to 'workspace'
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — Writes rendered_bytes verbatim, .git/info/exclude, permission normalization
- `src/scc_cli/adapters/claude_agent_runner.py` — build_settings() serializes to JSON bytes
- `src/scc_cli/adapters/codex_agent_runner.py` — build_settings() serializes to TOML bytes, bypass flag, file auth store
- `src/scc_cli/adapters/claude_agent_provider.py` — Implements auth_check() with three-tier validation
- `src/scc_cli/adapters/codex_agent_provider.py` — Implements auth_check() with three-tier validation
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — Backward-compat: deserializes rendered_bytes to dict
- `src/scc_cli/application/start_session.py` — is_resume parameter, workspace-scoped routing, fail-closed dispatch
- `src/scc_cli/commands/launch/dependencies.py` — Fail-closed provider resolution (no silent Claude fallback)
- `src/scc_cli/commands/launch/flow_interactive.py` — Fail-closed provider resolution
- `src/scc_cli/commands/worktree/worktree_commands.py` — Fail-closed provider resolution
- `src/scc_cli/doctor/checks/environment.py` — Delegates to adapter-owned auth_check() via bootstrap
- `images/scc-base/Dockerfile` — Pre-creates .claude and .codex dirs with 0700/uid1000
- `images/scc-agent-codex/Dockerfile` — Pins Codex CLI version via ARG
- `tests/test_docs_truthfulness.py` — +15 M007 guardrail tests + 10 decision-reconciliation tests
- `tests/test_oci_sandbox_runtime.py` — +7 config persistence transition tests + permission normalization tests
- `tests/test_image_structure.py` — New: 25 structural tests for all image Dockerfiles
- `tests/test_claude_agent_runner.py` — New: Claude runner tests for rendered_bytes
- `tests/fakes/fake_agent_provider.py` — Updated for auth_check() protocol compliance
- `.gsd/DECISIONS.md` — D-001 corrected to 'Sandboxed Code CLI'
