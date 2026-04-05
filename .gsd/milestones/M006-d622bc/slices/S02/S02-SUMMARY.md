---
id: S02
parent: M006-d622bc
milestone: M006-d622bc
provides:
  - CodexAgentRunner adapter implementing AgentRunner protocol
  - SCC_CODEX_IMAGE_REF and SCC_CODEX_IMAGE constants
  - Provider-aware SandboxSpec (agent_argv, data_volume, config_dir, image_ref)
  - OCI runtime exec/create commands that branch on spec fields
  - images/scc-agent-codex/Dockerfile
requires:
  - slice: S01
    provides: Provider resolution, _PROVIDER_DISPATCH table, --provider CLI flag, bootstrap codex_agent_provider/codex_safety_adapter fields
affects:
  - S03
  - S04
key_files:
  - src/scc_cli/adapters/codex_agent_runner.py
  - src/scc_cli/core/image_contracts.py
  - images/scc-agent-codex/Dockerfile
  - src/scc_cli/bootstrap.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/ports/models.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - tests/test_codex_agent_runner.py
  - tests/contracts/test_agent_runner_contract.py
  - tests/test_provider_dispatch.py
  - tests/test_application_start_session.py
  - tests/test_oci_sandbox_runtime.py
key_decisions:
  - Codex argv is bare ["codex"] with no permission-skip flags — --dangerously-skip-permissions is Claude-specific
  - agent_argv stored as list[str] on SandboxSpec (converted from AgentLaunchSpec tuple) for direct use in exec commands
  - _build_sandbox_spec resolves provider_id to concrete values via dict lookups; OCI runtime consumes spec fields, never provider_id — keeps infrastructure provider-agnostic
  - Empty-string/empty-tuple fallbacks in OCI runtime preserve full backward compat for existing Claude specs without SandboxSpec field population
patterns_established:
  - SandboxSpec field-forwarding: application layer resolves provider_id → data fields (_PROVIDER_IMAGE_REF, _PROVIDER_DATA_VOLUME, _PROVIDER_CONFIG_DIR dicts), infrastructure adapter consumes fields with fallback defaults
  - Parametric contract tests via @pytest.mark.parametrize for all AgentRunner implementations — add new runner, add to parametrize list
  - agent_launch_spec built before sandbox_spec in prepare_start_session to enable argv flow-through
observability_surfaces:
  - SandboxSpec fields (agent_argv, data_volume, config_dir, image_ref) visible in diagnostic dumps and dry-run debug output
  - runtime_info now flows into StartSessionDependencies for downstream consumption
  - Missing runner raises InvalidLaunchPlanError with clear message via _require pattern in dependencies.py
drill_down_paths:
  - .gsd/milestones/M006-d622bc/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S02/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T23:55:56.053Z
blocker_discovered: false
---

# S02: CodexAgentRunner, provider-aware image selection, and launch path wiring

**Codex launch path is fully wired: CodexAgentRunner adapter, provider-aware image/volume/config/argv selection in SandboxSpec, and OCI runtime exec/create commands that branch on spec fields with backward-compatible fallbacks — 38 net new tests, 4568 total.**

## What Happened

This slice made the launch pipeline genuinely provider-aware from provider selection (S01) through to the Docker exec command line.

**T01 — CodexAgentRunner adapter and image contracts.** Created `codex_agent_runner.py` mirroring the Claude runner pattern with codex-specific settings path (`/home/agent/.codex/config.toml`), bare `["codex"]` argv (no `--dangerously-skip-permissions` — that's Claude-specific), and `"Codex"` describe. Added `SCC_CODEX_IMAGE` and `SCC_CODEX_IMAGE_REF` to image_contracts.py. Created `images/scc-agent-codex/Dockerfile` installing Node.js 20 + `@openai/codex`. Wired `codex_agent_runner` into `DefaultAdapters` (with `None` default per the established pattern) and `build_fake_adapters()`. Extended `test_agent_runner_contract.py` with parametric coverage of both runners. 13 tests.

**T02 — Provider dispatch, runtime_info threading, image selection.** Extended `_PROVIDER_DISPATCH` to include `agent_runner` per-provider. Threaded `runtime_info` from `runtime_probe.probe()` into `StartSessionDependencies`. Made `_build_sandbox_spec` select image by provider_id via `_PROVIDER_IMAGE_REF` dict instead of hardcoding Claude's image. Added `agent_argv` field to `SandboxSpec` and reordered `prepare_start_session` to build `agent_launch_spec` before `sandbox_spec` so the argv flows through. 10 new tests covering dispatch, image selection, and argv propagation.

**T03 — OCI runtime provider-aware exec and create commands.** The highest-risk task. Added `data_volume` and `config_dir` fields to `SandboxSpec`. Extended `_build_sandbox_spec` with `_PROVIDER_DATA_VOLUME` and `_PROVIDER_CONFIG_DIR` dicts. Updated `_build_exec_cmd` to use `spec.agent_argv` when non-empty (skipping Claude's `--dangerously-skip-permissions` for Codex), with fallback to `AGENT_NAME`. Updated `_build_create_cmd` to resolve volume name and config dirname from spec fields with empty-string fallback to existing constants. 15 new tests covering exec cmd, create cmd, continue-session, and all fallback paths.

The key architectural pattern: provider-specific values are resolved in the application layer (`start_session.py`) via provider_id → dict lookups and forwarded as plain data fields on `SandboxSpec`. The infrastructure adapter (`oci_sandbox_runtime.py`) consumes spec fields with empty/fallback defaults and never inspects provider_id. This keeps the infrastructure layer provider-agnostic.

## Verification

All slice verification gates passed:

1. **Targeted tests** — 111 tests across 5 test files (codex runner, contracts, dispatch, start_session, OCI runtime): all pass
2. **Ruff check** — all 7 source files clean
3. **Mypy** — all 7 source files clean (0 issues)
4. **Full suite** — 4568 passed, 23 skipped, 2 xfailed, 0 failures (up from 4529 at S01 close)

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor: T01 had an alphabetical import order issue caught by ruff I001, fixed immediately. T02 fixed a pre-existing ruff I001 import sort in test_codex_agent_runner.py. T02 used a mock for `resolve_destination_sets` in unknown-provider test because FakeAgentProvider uses an unregistered destination set. No plan-level deviations.

## Known Limitations

- The Codex Dockerfile (`images/scc-agent-codex/Dockerfile`) is a build definition only — no image build/push pipeline exists yet. Image distribution strategy is deferred.
- Unknown provider_id falls back to Claude defaults (image, volume, config_dir, argv) rather than failing closed. This is intentional for backward compat but means a typo in provider_id silently runs Claude.
- `runtime_info` is threaded into dependencies but not yet consumed by downstream diagnostics or branding (that's S03 territory).

## Follow-ups

- S03 should consume provider_id for branding, panels, diagnostics, and string cleanup.
- S04 should verify end-to-end that `scc start --provider codex` produces the correct Docker exec command line.
- Future milestone: image build/push pipeline for scc-agent-codex.

## Files Created/Modified

- `src/scc_cli/adapters/codex_agent_runner.py` — New CodexAgentRunner adapter with codex argv, .codex settings path, and Codex describe
- `src/scc_cli/core/image_contracts.py` — Added SCC_CODEX_IMAGE and SCC_CODEX_IMAGE_REF constants
- `images/scc-agent-codex/Dockerfile` — New Codex container image: Node.js 20 + @openai/codex on Debian base
- `src/scc_cli/bootstrap.py` — Added codex_agent_runner field to DefaultAdapters with None default and CodexAgentRunner() instantiation
- `src/scc_cli/commands/launch/dependencies.py` — Extended _PROVIDER_DISPATCH with agent_runner per-provider, threaded runtime_info from probe
- `src/scc_cli/application/start_session.py` — Provider-aware image/volume/config_dir/argv selection via _PROVIDER_* dicts, agent_launch_spec built before sandbox_spec
- `src/scc_cli/ports/models.py` — Added agent_argv, data_volume, config_dir fields to SandboxSpec
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — Provider-aware _build_exec_cmd (uses agent_argv) and _build_create_cmd (uses data_volume, config_dir) with backward-compat fallbacks
- `tests/fakes/__init__.py` — Added codex_agent_runner=FakeAgentRunner() to build_fake_adapters()
- `tests/test_codex_agent_runner.py` — New 4-test file for CodexAgentRunner plus import sort fix
- `tests/contracts/test_agent_runner_contract.py` — Parametric contract tests covering both Claude and Codex runners
- `tests/test_provider_dispatch.py` — Runner dispatch and runtime_info threading tests added
- `tests/test_application_start_session.py` — Provider-aware image, argv, volume, config_dir tests added
- `tests/test_oci_sandbox_runtime.py` — 15 new tests for codex exec/create commands and fallback paths
