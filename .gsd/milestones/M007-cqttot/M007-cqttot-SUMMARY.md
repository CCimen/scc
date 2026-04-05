---
id: M007-cqttot
title: "Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup"
status: complete
completed_at: 2026-04-05T16:13:06.376Z
key_decisions:
  - D029: ProviderRuntimeSpec as single source of truth for provider runtime details — replaces 5 scattered dicts
  - D030: Product name standardized as 'SCC — Sandboxed Code CLI' across all surfaces
  - D031/D034/D043: Registry placement evolved from dependencies.py → package root → core/provider_registry.py to satisfy no-root-sprawl guardrail
  - D032: Unknown providers fail closed in active launch — no silent Claude fallback. Legacy defaults only at migration/read boundaries
  - D033: Codex launched with --dangerously-bypass-approvals-and-sandbox — SCC container is the hard enforcement boundary
  - D035: AgentSettings uses rendered_bytes (not dict) — runners own serialization format (JSON for Claude, TOML for Codex)
  - D037: auth_check() on AgentProvider protocol with three-tier validation — adapter-owned auth readiness
  - D038/D042: Fresh launch deterministically writes config even when empty — resume skips injection
  - D039: Runtime permission normalization after container start — defense-in-depth for volume permissions
  - D040: Codex forces file-based auth in containers via cli_auth_credentials_store='file'
  - D041: Provider-native config layering — Claude home-scoped settings.json, Codex workspace-scoped config.toml
  - D044: S05 expanded from docs-only to full architecture reconciliation — decisions must be implemented, not just recorded
key_files:
  - src/scc_cli/core/contracts.py — ProviderRuntimeSpec frozen dataclass with settings_scope
  - src/scc_cli/core/errors.py — InvalidProviderError, ProviderNotReadyError, ProviderImageMissingError
  - src/scc_cli/core/provider_registry.py — PROVIDER_REGISTRY dict + get_runtime_spec() fail-closed lookup
  - src/scc_cli/core/constants.py — Stripped to product-level constants only
  - src/scc_cli/ports/models.py — AgentSettings refactored to rendered_bytes
  - src/scc_cli/ports/agent_provider.py — auth_check() on AgentProvider protocol
  - src/scc_cli/adapters/oci_sandbox_runtime.py — Permission normalization, format-agnostic settings injection, workspace-scoped config routing
  - src/scc_cli/adapters/codex_agent_runner.py — TOML serialization, bypass flag, file auth store
  - src/scc_cli/adapters/claude_agent_runner.py — JSON serialization for rendered_bytes
  - src/scc_cli/adapters/claude_agent_provider.py — auth_check() with three-tier validation
  - src/scc_cli/adapters/codex_agent_provider.py — auth_check() with three-tier validation
  - src/scc_cli/application/start_session.py — Registry-based lookups, is_resume routing, fail-closed dispatch
  - src/scc_cli/sessions.py — Provider-parameterized session helpers
  - src/scc_cli/contexts.py — WorkContext with provider_id field
  - src/scc_cli/doctor/checks/environment.py — check_provider_auth(), adapter-owned auth delegation
  - src/scc_cli/doctor/core.py — Category assignment, provider threading
  - src/scc_cli/commands/admin.py — --provider flag on doctor
  - images/scc-base/Dockerfile — Pre-creates .claude and .codex dirs
  - images/scc-agent-codex/Dockerfile — Pins Codex CLI version
  - tests/test_docs_truthfulness.py — 32 truthfulness/decision-reconciliation guardrail tests
  - tests/test_no_claude_constants_in_core.py — Tokenize-based constant guardrail
  - tests/test_image_structure.py — 25 Dockerfile structural tests
  - tests/test_provider_registry.py — 11 registry contract tests
lessons_learned:
  - Accepting architecture decisions without implementing them creates a truthfulness gap. D044 caught 10 accepted-but-unimplemented decisions — the exact problem M007 was supposed to solve. Future milestones should verify decisions are code-real before closing.
  - Decision reconciliation guardrail tests (verifying accepted decisions are implemented in code) are high-value and cheap. 32 tests in test_docs_truthfulness.py mechanically prevent regression of M007 deliverables.
  - Provider-owned settings serialization (rendered_bytes) was a small change (~30 lines across runners + runtime) that eliminated an entire class of format-coupling bugs. The lesson: when infrastructure code assumes a format, push serialization to the owner.
  - The registry placement journey (D031→D034→D043) shows that existing guardrail tests can override planned architecture — the no-root-sprawl test rejected the planned package-root location. Guardrails working as intended.
  - Config ownership layering (D041) — using provider-native config scoping (home vs workspace) instead of fighting the provider's own config resolution — is simpler and more correct than custom injection schemes.
  - Runtime permission normalization (D039) is defense-in-depth for Docker volume permission drift. Build-time permissions only apply when the volume is first populated; runtime normalization handles volumes that already have data.
  - Milestone success criteria should be formally populated during planning, not compensated at validation time by aggregating slice-level criteria — lesson from M003 still applies. M007's vision statement served as the effective criteria list.
---

# M007-cqttot: Provider Neutralization, Operator Truthfulness, and Legacy Claude Cleanup

**SCC stopped leaking Claude assumptions through shared/core/operator paths — ProviderRuntimeSpec replaces 5 scattered dicts, settings serialization is provider-owned, config layering is provider-native, unknown providers fail closed, auth readiness is adapter-owned, and 32 truthfulness guardrail tests mechanically prevent regression.**

## What Happened

M007 eliminated the remaining Claude assumptions that had leaked through SCC's shared, core, and operator-facing code paths across five slices and 166 net new tests (4654→4820).

**S01 (ProviderRuntimeSpec and fail-closed dispatch)** consolidated 5 scattered provider dicts (`_PROVIDER_IMAGE_REF`, `_PROVIDER_DATA_VOLUME`, `_PROVIDER_CONFIG_DIR`, `_PROVIDER_DISPATCH`, `_PROVIDER_DISPLAY_NAMES`) into a single `ProviderRuntimeSpec` frozen dataclass in `core/contracts.py` with a `PROVIDER_REGISTRY` dict and `get_runtime_spec()` fail-closed lookup in `core/provider_registry.py`. Fixed the settings path bug where Codex would receive Claude's `.claude/settings.json` path. Unknown providers now raise `InvalidProviderError` instead of silently falling back to Claude. 11 new tests.

**S02 (Session/audit provider hardening)** renamed three Claude-hardcoded helpers (`get_claude_sessions_dir`, `get_claude_recent_sessions`, `get_claude_dir`) to provider-parameterized versions backed by the registry. `WorkContext` gained a `provider_id` field with backward-compatible serialization. Session list CLI displays a Provider column. Legacy sandbox path explicitly records `provider_id='claude'`. 21 new tests.

**S03 (Doctor provider-awareness)** added `ProviderNotReadyError` and `ProviderImageMissingError` typed errors, `check_provider_auth()` with Docker volume probing, `CheckResult.category` for output grouping, and `--provider` flag on `scc doctor` validated against `KNOWN_PROVIDERS`. Doctor output groups checks by category with section headers. 43 new tests.

**S04 (Legacy Claude path isolation)** localized 9 Claude-specific constants from `core/constants.py` into 5 consumer modules (`docker/core.py`, `docker/credentials.py`, `docker/launch.py`, `adapters/oci_sandbox_runtime.py`, `application/start_session.py`). Constants renamed to `_CLAUDE_*` for self-documentation. `profile.py` documented as Claude-only. Tokenize-based guardrail test prevents re-introduction. 2 new tests.

**S05 (Architecture reconciliation and truthfulness)** expanded from docs-only (D044 user override) to implement 10 architecture decisions in code. AgentSettings refactored from `content: dict` to `rendered_bytes: bytes` (D035). CodexAgentRunner launches with `--dangerously-bypass-approvals-and-sandbox` (D033). Codex uses workspace-scoped `.codex/config.toml` (D041) with `cli_auth_credentials_store='file'` (D040). Fresh launch deterministically writes config even when empty (D038/D042). Runtime permission normalization after container start (D039). `auth_check()` on AgentProvider protocol with three-tier validation (D037). All active launch paths fail closed — no silent Claude fallback (D032). Image hardening with pre-created dirs and pinned Codex CLI version. 32 truthfulness/decision-reconciliation guardrail tests and 7 config persistence transition tests. 89 new tests.

The milestone's key insight was that accepting architecture decisions without implementing them creates a truthfulness gap — the very problem M007 was supposed to solve. D044 caught this and expanded S05 from a docs task into full reconciliation, which delivered the most impactful work of the milestone.

## Success Criteria Results

### Success Criteria Verification

1. **ProviderRuntimeSpec replaces scattered dicts** ✅
   - `ProviderRuntimeSpec` frozen dataclass in `core/contracts.py` with 7 typed fields (provider_id, display_name, image_ref, config_dir, settings_path, settings_scope, data_volume).
   - `PROVIDER_REGISTRY` in `core/provider_registry.py` maps provider_id → spec.
   - 5 scattered dicts (`_PROVIDER_IMAGE_REF`, `_PROVIDER_DATA_VOLUME`, `_PROVIDER_CONFIG_DIR`, `_PROVIDER_DISPATCH`, `_PROVIDER_DISPLAY_NAMES`) removed from `start_session.py` and `dependencies.py`.

2. **Settings serialization is provider-owned** ✅
   - `AgentSettings.rendered_bytes: bytes` replaces `content: dict[str, Any]` (D035).
   - `ClaudeAgentRunner.build_settings()` serializes to JSON bytes.
   - `CodexAgentRunner.build_settings()` serializes to TOML bytes.
   - OCI runtime writes `rendered_bytes` verbatim — no `json.dumps()` call.

3. **Config layering is provider-native** ✅
   - Claude: SCC writes to `/home/agent/.claude/settings.json` (home-scoped, settings_scope='home').
   - Codex: SCC writes to `/workspace/.codex/config.toml` (workspace-scoped, settings_scope='workspace') (D041).
   - User-level config in persistent volume is never touched.

4. **Unknown providers fail closed** ✅
   - `get_runtime_spec('unknown')` raises `InvalidProviderError` with exit_code=2.
   - All active launch paths (start_session, dependencies, flow_interactive, worktree_commands) fail closed (D032).
   - Legacy Claude defaults preserved only at migration/read boundaries.

5. **Config freshness is deterministic** ✅
   - Fresh launch always writes SCC-managed config, even when logically empty (D038/D042).
   - Resume skips injection (`_build_agent_settings(is_resume=True)` returns None).
   - 7 config persistence transition tests prove determinism across governed→standalone, teamA→teamB, cross-provider, and idempotent scenarios.

6. **Auth persistence is intentional with runtime permission normalization** ✅
   - Runtime permission normalization step in OCI launch path: config dir 0700, auth files 0600, uid 1000 (D039).
   - Codex forces `cli_auth_credentials_store='file'` for reliable container auth (D040).
   - scc-base Dockerfile pre-creates both .claude and .codex dirs with correct permissions.

7. **Doctor separates backend, image, and auth readiness** ✅
   - `CheckResult.category` field groups checks into backend/provider/config/worktree/general.
   - `--provider` flag scopes checks to specific provider readiness.
   - `check_provider_auth()` uses Docker volume probing with provider-specific auth file mapping.
   - `auth_check()` on AgentProvider protocol with three-tier validation (D037).

8. **Product naming is consistent** ✅
   - README: "SCC - Sandboxed Code CLI". pyproject.toml: provider-neutral description. D-001 corrected to 'Sandboxed Code CLI' (D030).

9. **Legacy Claude paths are isolated** ✅
   - `core/constants.py` holds only CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX, _FALLBACK_VERSION.
   - 9 Claude-specific constants localized to consumer modules with `_CLAUDE_*` prefixes.
   - `profile.py` documented as Claude-only with intentional hardcoded references.
   - Tokenize-based guardrail test prevents re-introduction.

10. **Truthfulness guardrails** ✅
    - 32 truthfulness/decision-reconciliation guardrail tests in `test_docs_truthfulness.py`.
    - 2 core constants guardrail tests in `test_no_claude_constants_in_core.py`.
    - 25 image structure tests in `test_image_structure.py`.
    - All 48 pass (verified in exit gate).

## Definition of Done Results

### Definition of Done

1. **All slices complete** ✅ — S01 through S05 all show ✅ in roadmap. All 5 slice summaries exist on disk.

2. **Full test suite passes** ✅ — 4820 passed, 23 skipped, 2 xfailed, 0 failed (78.73s).

3. **Linting passes** ✅ — `uv run ruff check` exits 0 (verified during S05 exit gate and during this closeout).

4. **Type checking passes** ✅ — `uv run mypy src/scc_cli` reported success during S05 verification.

5. **No regressions** ✅ — Test count grew from 4643 (M006 baseline) to 4820 (+177 net new tests, +166 from M007 slices plus S05's 11 existing-test updates).

6. **Cross-slice integration** ✅ — S02–S05 all consumed S01's ProviderRuntimeSpec and registry. S05 consumed outputs from S01–S04 (registry, renamed helpers, doctor provider-awareness, localized constants) and reconciled all architecture decisions against code. No integration gaps found.

## Requirement Outcomes

### Requirement Status Transitions

**R001 (maintainability)** — remains **validated**. M007 advanced R001 through four mechanisms:
1. Replaced 5 scattered dicts with a single typed registry (S01), improving cohesion and reducing drift risk when adding providers. 11 new tests cover the registry contract.
2. Provider-parameterized session/audit helpers (S02) eliminate Claude-specific naming from shared code. 21 new tests.
3. Doctor decomposition with typed errors, categorized output, and provider-scoped checks (S03) improves testability and maintainability of the doctor subsystem. 43 new tests.
4. Claude-specific constants localized from core into consumer modules (S04), eliminating false shared-constant coupling between core and 5 provider-specific consumers. Guardrail test prevents re-introduction.

No status change needed — R001 was already validated in M005 and M007 continues to advance it.

## Deviations

S05 expanded from 1 planned task (docs/naming only) to 12 tasks (full architecture reconciliation) per user override D044. This was the right call — it caught 10 accepted-but-unimplemented decisions. Provider registry placement changed from D034's planned package root to core/provider_registry.py (D043) due to the existing no-root-sprawl guardrail. S04 T01 extended scope beyond docker/ to also localize constants in adapters/ and application/ — required to make the core/constants.py removal safe.

## Follow-ups

- `scc auth login/status/logout` CLI commands — the auth_check() model on AgentProvider supports them (D037)
- Image build/push pipeline for scc-agent-codex (currently operator-built)
- Fine-grained volume splitting (auth-only vs ephemeral) for enterprise data-retention (D036)
- Dashboard provider switching TUI feature (dashboard 'a' key)
- Container labels (scc.provider=id) for external tooling discovery
- Podman support on the same SandboxRuntime contracts
- Wizard cast cleanup (23 casts in wizard.py/flow_interactive.py) — deferred per D018
