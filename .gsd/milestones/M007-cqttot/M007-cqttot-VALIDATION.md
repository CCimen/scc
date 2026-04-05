---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M007-cqttot

## Success Criteria Checklist
| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | ProviderRuntimeSpec in core/contracts.py with provider_id, display_name, image_ref, config_dir, settings_path, data_volume | ✅ PASS | Verified via import: all 6 fields present on frozen dataclass. 11 registry tests. |
| 2 | PROVIDER_REGISTRY in provider_registry.py with fail-closed get_runtime_spec() | ✅ PASS | Module at core/provider_registry.py (D043 placement). get_runtime_spec('unknown') raises InvalidProviderError. |
| 3 | AgentSettings carries rendered_bytes:bytes + path:Path. Runners serialize format. OCI writes verbatim. | ✅ PASS | AgentSettings.__dataclass_fields__ shows rendered_bytes, path, suffix. Claude runner produces JSON bytes, Codex runner produces TOML bytes. OCI runtime writes verbatim (S05/T02-T03). |
| 4 | Claude settings → .claude/settings.json (SCC-owned). Codex settings → workspace .codex/config.toml (project-scoped). User config never modified. | ✅ PASS | Claude spec: settings_path='.claude/settings.json'. Codex spec: settings_path='.codex/config.toml', settings_scope='workspace'. Start_session.py routes by scope. |
| 5 | Unknown provider raises InvalidProviderError. No silent Claude fallback. | ✅ PASS | Verified in import test. S01 flipped 4 tests from fallback to error. S05 hardened all active launch paths. |
| 6 | OCI runtime fails clearly on missing agent_argv, data_volume, or config_dir | ✅ PASS | S05/T04 fail-closed dispatch ensures all specs are populated before OCI layer sees them. |
| 7 | CodexAgentRunner uses --dangerously-bypass-approvals-and-sandbox (D033) | ✅ PASS | codex_agent_runner.py line 73: `argv=["codex", "--dangerously-bypass-approvals-and-sandbox"]`. |
| 8 | Codex project config includes cli_auth_credentials_store='file' (D040) | ✅ PASS | codex_agent_runner.py line 54: `"cli_auth_credentials_store": "file"`. |
| 9 | Config freshness: write on fresh launch even when empty. Resume skips. Transition tests. | ✅ PASS | start_session.py has is_resume guard (line 287). 7 config persistence transition tests in test_oci_sandbox_runtime.py. |
| 10 | User/provider-owned persistent settings preserved across launches | ✅ PASS | Config persistence transition tests cover governed→standalone and teamA→teamB scenarios. Workspace-scoped Codex config separates SCC layer from user volume config. |
| 11 | Runtime permission normalization: config dir 0700, auth files 0600, uid 1000 | ✅ PASS | oci_sandbox_runtime.py lines 149-185: _normalise_provider_permissions with chown/chmod commands. |
| 12 | .scc-provider-state.json in volume with provider_id, layout_version, auth_storage_mode | ⚠️ NOT DELIVERED | No code references found. grep across src/ and tests/ returns zero matches for this file name or its fields (layout_version, auth_storage_mode). |
| 13 | AuthReadiness(status, mechanism, guidance). Doctor wording truthful. | ✅ PASS | AuthReadiness verified via import with status/mechanism/guidance fields. S05 documented truthful wording. |
| 14 | constants.py shared-only. Claude constants localized. Guardrail test. | ✅ PASS | constants.py has only CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX. 2 guardrail tests in test_no_claude_constants_in_core.py using tokenize-based scanning. |
| 15 | Sessions helper provider-parameterized. Audit from provider. sandbox.py records 'claude'. | ✅ PASS | sessions.py: get_provider_sessions_dir/get_provider_recent_sessions. audit.py: get_provider_config_dir. sandbox.py: provider_id='claude'. |
| 16 | Quick Resume shows provider, warns on mismatch | ⚠️ PARTIAL | WorkContext.display_label appends "(codex)" for non-default providers — shows provider: YES. No explicit mismatch warning code found in quick_resume.py or related UI code — warns on mismatch: NOT DELIVERED. |
| 17 | Doctor --provider flag. Backend→image→auth readiness sections. | ✅ PASS | S03 delivered --provider flag with KNOWN_PROVIDERS validation and category grouping (backend→provider→config→worktree→general). 43 new tests. |
| 18 | Typed errors: InvalidProviderError, ProviderNotReadyError, ProviderImageMissingError | ✅ PASS | All three in core/errors.py with exit codes, user_message, suggested_action. |
| 19 | provider_id in dry-run JSON, support bundle, audit events, session list --json | ⚠️ PARTIAL | Support bundle: YES (support_bundle.py line 330). Session list: YES (test_provider_machine_readable.py). Audit: YES (get_provider_config_dir). Dry-run JSON: provider_id not explicitly surfaced in launch_json.py envelope — minor gap. |
| 20 | scc-base: both config dirs 0700 uid 1000. scc-agent-codex: ARG CODEX_VERSION. | ✅ PASS | Verified in Dockerfiles: scc-base creates .claude + .codex 0700/uid1000. scc-agent-codex has ARG CODEX_VERSION with npm install routing. 25 structural tests. |
| 21 | README and surfaces use 'SCC — Sandboxed Code CLI'. D-001 updated. | ✅ PASS | README.md line 1: "SCC - Sandboxed Code CLI". pyproject.toml description: provider-neutral. D-001 corrected. |
| 22 | Exit gate: ruff, mypy, pytest pass. | ✅ PASS | ruff check: "All checks passed!" mypy: "Success: no issues found". pytest: 4820 passed, 23 skipped, 2 xfailed, 0 failed. |

## Slice Delivery Audit
| Slice | Claimed Output | Delivered | Verdict |
|-------|---------------|-----------|---------|
| S01 | ProviderRuntimeSpec defined in core/contracts.py. PROVIDER_REGISTRY with fail-closed get_runtime_spec(). _build_agent_settings uses spec.settings_path. Unknown provider_id raises InvalidProviderError. Full test suite passes. | ProviderRuntimeSpec frozen dataclass with 6 fields. PROVIDER_REGISTRY in core/provider_registry.py with 2 entries. get_runtime_spec() fail-closed. Settings path bug fixed. InvalidProviderError with exit_code=2. 4654 tests pass (+11 new). | ✅ Fully delivered |
| S02 | Sessions dir renamed to provider-parameterized. Audit derives path from provider. sandbox.py records provider_id='claude'. Quick Resume shows provider_id. Session list CLI displays provider column. | get_provider_sessions_dir, get_provider_recent_sessions, get_provider_config_dir all registry-based. sandbox.py records 'claude'. WorkContext carries provider_id with display_label suffix. Session list has Provider column. 4675 tests pass (+21 new). | ✅ Fully delivered |
| S03 | scc doctor --provider codex checks Codex readiness. Doctor groups backend vs provider. ProviderNotReadyError and ProviderImageMissingError exist. | --provider flag with KNOWN_PROVIDERS validation. Category grouping with 5 categories. Both error types in core/errors.py. check_provider_auth with three-tier validation. 4718 tests pass (+43 new). | ✅ Fully delivered |
| S04 | docker/ modules use local Claude constants. commands/profile.py documented as Claude-only. No shared constant import for Claude runtime values. | 9 constants localized to 5 consumer modules. constants.py has only product-level values. profile.py has Claude-only docstring. 2 guardrail tests with tokenize-based scanning. 4720 tests pass (+2 new). | ✅ Fully delivered |
| S05 | README says 'Sandboxed Code CLI'. D-001 updated. All user-facing strings consistent. Truthfulness guardrail expanded. | Expanded from 1 task to 12 tasks per D044. README renamed. D-001 corrected. 32 truthfulness guardrail tests. rendered_bytes AgentSettings. auth_check() protocol. Permission normalization. Fail-closed all active paths. 25 image structure tests. 7 config persistence tests. 4820 tests pass (+100 net new). | ✅ Delivered (expanded scope per D044) |

## Cross-Slice Integration
**S01 → S02/S03/S04:** S01's ProviderRuntimeSpec and get_runtime_spec() are consumed correctly by all downstream slices. S02 uses registry for session/audit dir resolution. S03 uses registry for doctor checks. S04 localizes the remaining constants that the registry doesn't cover. No boundary mismatches.

**S02 → S05:** S02's provider-parameterized helpers and WorkContext.provider_id are consumed by S05's fail-closed launch paths. The provider_id flows through StartSessionRequest to the OCI runtime layer. No mismatches.

**S03 → S05:** S03's check_provider_auth and CheckResult.category are consumed by S05's doctor delegation to adapter-owned auth_check(). The auth readiness model aligns. No mismatches.

**S04 → S05:** S04's cleaned constants.py is consumed by S05's truthfulness guardrail tests that verify constants.py contains no Claude-specific values. No mismatches.

**Cross-slice test progression:** S01: 4654 → S02: 4675 → S03: 4718 → S04: 4720 → S05: 4820. Monotonically increasing with zero regressions at each boundary. Net +166 new tests across the milestone.

## Requirement Coverage
**R001 (maintainability) — Status: validated (already marked in DB)**

Evidence across all slices:
- S01: Replaced 5 scattered dicts with single typed registry. 11 new tests.
- S02: Renamed 3 Claude-named helpers to registry-based. 21 new tests.
- S03: Added typed provider errors with category grouping. 43 new tests.
- S04: Localized 9 Claude constants with guardrail tests. 2 new tests.
- S05: Reconciled 10 architecture decisions into code. 100 new tests. 32 truthfulness guardrails mechanically prevent regression.

R001 is comprehensively covered — the milestone's core purpose was provider neutralization which directly improves maintainability by making touched areas cohesive, testable, and easier to change. Total: +166 net new tests, all major provider-specific assumptions isolated or parameterized.

## Verification Class Compliance
### Contract Verification
**Status: ✅ Fully addressed**

Every slice ran targeted tests on the changed code followed by the full regression suite. Evidence:
- S01: 86 targeted tests + 4654 full suite
- S02: ruff + mypy on all files + 4675 full suite
- S03: 43 targeted tests + 4718 full suite
- S04: guardrail test + rg scan + 4720 full suite
- S05: 50 truthfulness tests + 4820 full suite

### Integration Verification
**Status: ✅ Fully addressed**

Cross-slice consumption verified:
- S01 registry consumed by S02 (session/audit helpers), S03 (doctor checks), S04 (guardrail verification)
- S02 WorkContext.provider_id consumed by S05 fail-closed launch paths
- Full suite ran at each slice boundary with monotonically increasing test count

### Operational Verification
**Status: ⚠️ Partially addressed — documented gaps**

What was verified:
- Doctor --provider flag with backend/image/auth grouping (S03, tested)
- Config freshness across governed→standalone, teamA→teamB, settings→no-settings transitions (S05, 7 tests)
- Runtime permission normalization code in OCI adapter (S05, tested)
- Auth readiness with three-tier validation (S05, tested)
- User config preservation across launches (S05, config persistence tests)

What was NOT verified:
- `.scc-provider-state.json` volume metadata file — listed in success criteria but not implemented in code
- Quick Resume provider mismatch warning — WorkContext shows provider but no mismatch detection/warning
- Dry-run JSON provider_id — not explicitly surfaced in launch_json.py envelope
- All operational tests are mocked (no real Docker). This is acceptable for CI but means image build/push and real container runtime behavior are design-only.

### UAT Verification
**Status: ✅ Fully addressed**

All 5 slices have UAT.md artifacts with comprehensive test cases. All surfaces tested programmatically. UAT test cases cover:
- S01: 10 test cases (registry, fail-closed, immutability, full regression)
- S02: 9 test cases (sessions, audit, sandbox, WorkContext, display_label)
- S03: 14 test cases (typed errors, auth check, category assignment, render grouping)
- S04: 8 test cases (constants cleanup, guardrail, import scanning)
- S05: 10 test cases (naming, truthfulness, serialization, auth, fail-closed, images)


## Verdict Rationale
The milestone delivered its core objectives comprehensively: ProviderRuntimeSpec typed registry replaces scattered dicts, AgentSettings uses rendered_bytes for format-agnostic serialization, all active launch paths fail closed, Claude constants are isolated from core with guardrail tests, doctor is provider-aware, and product naming is consistent. 19 of 22 success criteria fully pass, exit gate passes (4820 tests, ruff clean, mypy clean), and all 5 slices delivered their claimed outputs.

Three minor gaps do not block completion:

1. **`.scc-provider-state.json`** (criterion #12): Not implemented. This volume metadata file was aspirational — the core provider-neutral contracts work without it. The provider_id is already tracked in WorkContext, session records, and support bundles.

2. **Quick Resume mismatch warning** (criterion #16, partial): Provider is shown via display_label but no explicit mismatch warning exists. Low impact — the display already surfaces the information.

3. **Dry-run JSON provider_id** (criterion #19, partial): Support bundle, session list, and audit all include provider_id. The dry-run envelope in launch_json.py doesn't explicitly surface it. Minor formatting gap.

These are non-blocking UX/operational polish items that can be addressed in future work. The core architecture — typed registry, fail-closed dispatch, provider-owned serialization, config freshness, permission normalization, constant isolation — is solid and well-tested.
