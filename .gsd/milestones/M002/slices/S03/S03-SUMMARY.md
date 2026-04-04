---
id: S03
parent: M002
milestone: M002
provides:
  - A second real `AgentProvider` implementation (`CodexAgentProvider`) on the same seam as Claude.
  - Verified coexistence wiring for Claude and Codex in `DefaultAdapters` without breaking bootstrap import boundaries.
  - A reusable provider-adapter characterization pattern that keeps provider-specific facts out of shared launch contracts.
requires:
  - slice: S01
    provides: The live `AgentProvider` / `AgentLaunchSpec` seam and composition-root entrypoint that S03 could exercise with a second real provider.
affects:
  - S04
  - S05
key_files:
  - src/scc_cli/adapters/codex_agent_provider.py
  - tests/test_codex_agent_provider.py
  - src/scc_cli/bootstrap.py
  - tests/fakes/__init__.py
  - tests/test_cli.py
  - tests/test_integration.py
key_decisions:
  - Represent Codex at the seam with minimal `argv=('codex',)`, `openai-core` destination requirements, file-based settings via `artifact_paths`, and empty `env`.
  - Keep Codex capability metadata honest by reporting no resume, skills, or native integrations until those behaviors actually exist.
  - Preserve `bootstrap.py` as the only adapter composition root while allowing `DefaultAdapters` to host multiple providers concurrently.
patterns_established:
  - Add each new provider as a small standalone `AgentProvider` adapter instead of widening core launch orchestration.
  - Pin every real provider with the canonical four-test characterization suite: capability metadata, clean spec, settings artifact path, and env string-safety.
  - Keep file-based provider configuration in `artifact_paths`, not `AgentLaunchSpec.env`.
  - When shared adapter containers gain a field, wire bootstrap, fake factories, and inline test constructions together, using `| None = None` defaults as the missed-construction-site safety net.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M002/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S03/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T19:40:08.375Z
blocker_discovered: false
---

# S03: Codex adapter as a first-class provider on the same seam

**Codex now exists as a first-class `AgentProvider` adapter with honest capability metadata and verified coexistence wiring beside Claude on the same provider-neutral seam.**

## What Happened

T01 added `src/scc_cli/adapters/codex_agent_provider.py` as a small standalone adapter implementing the existing `AgentProvider` protocol without widening shared contracts. Its `capability_profile()` reports `provider_id='codex'`, `display_name='Codex'`, `required_destination_set='openai-core'`, and conservative capability flags (`supports_resume`, `supports_skills`, and `supports_native_integrations` all `False`). Its `prepare_launch(...)` produces a provider-neutral `AgentLaunchSpec` with minimal `argv=('codex',)`, empty `env`, the requested workspace as `workdir`, and optional `artifact_paths` when a settings artifact exists.

T01 also added `tests/test_codex_agent_provider.py` in the canonical four-test provider shape now shared by both real adapters: capability metadata, clean launch without settings, launch with one settings artifact path, and env string-to-string safety. That pins the Codex contract at the adapter edge instead of letting Codex-specific facts leak into shared core models.

T02 closed the composition-root proof from the other side. On inspection, `src/scc_cli/bootstrap.py`, `tests/fakes/__init__.py`, and the inline `DefaultAdapters(...)` construction sites in `tests/test_cli.py` and `tests/test_integration.py` were already coherently wired with `codex_agent_provider`. The task therefore validated coexistence rather than adding new logic: Codex and Claude can sit in the same `DefaultAdapters` container, `bootstrap.py` remains the only permitted importer of `scc_cli.adapters.*`, and higher layers do not need direct adapter imports.

The slice outcome is a genuine two-provider seam. Core launch contracts stayed provider-neutral, Codex-specific behavior stayed adapter-owned, and the repo now has both focused characterization tests and broad suite coverage proving Codex can exist beside Claude without reintroducing Claude-shaped assumptions in core orchestration.

## Verification

- `uv run pytest ./tests/test_codex_agent_provider.py -q` → 4 passed.
- `uv run pyright src/scc_cli/adapters/codex_agent_provider.py tests/test_codex_agent_provider.py` → 0 errors, 0 warnings.
- `uv run pytest tests/test_bootstrap.py tests/test_import_boundaries.py tests/test_application_start_session.py tests/test_core_contracts.py tests/test_cli.py tests/test_integration.py -q` → 96 passed.
- `uv run ruff check` → passed.
- `uv run mypy src/scc_cli` → success, no issues found in 236 source files.
- `uv run pytest --tb=short -q` → 3249 passed, 23 skipped, 3 xfailed, 1 xpassed.

## Requirements Advanced

- R001 — The slice kept Codex support in a small standalone adapter module, preserved provider-neutral core contracts, and reinforced the seam with focused characterization plus full lint/type/test verification instead of widening launch orchestration.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The written plan expected T02 to add bootstrap/test wiring, but verification showed all four `DefaultAdapters` construction sites were already updated. T02 completed as a confirmation and repo-gate proof rather than as a code-edit task.

## Known Limitations

- Codex is present as a first-class adapter and in `DefaultAdapters`, but `agent_provider` remains the current seam entrypoint; broader provider selection, pre-launch destination validation, and durable launch auditing still belong to later slices.
- Codex capability metadata is intentionally conservative: no resume, skills, or native integrations are exposed yet.

## Follow-ups

- S04 should consume `ProviderCapabilityProfile.required_destination_set` from both providers so SCC fails before launch when provider-core access is missing and can persist that verdict to the durable audit sink.
- If Codex later gains resume, skills, or native integrations, update only the adapter capability profile and its characterization tests before touching higher launch layers.

## Files Created/Modified

- `src/scc_cli/adapters/codex_agent_provider.py` — Added a standalone Codex `AgentProvider` implementation with honest capability metadata and a minimal provider-owned launch spec.
- `tests/test_codex_agent_provider.py` — Added the canonical four-test characterization suite for Codex provider metadata, clean launch specs, settings artifact handling, and env safety.
- `src/scc_cli/bootstrap.py` — Carries Codex as a coexisting provider in `DefaultAdapters` at the composition root.
- `tests/fakes/__init__.py` — Builds fake adapters with `codex_agent_provider` populated so seam tests stay coherent.
- `tests/test_cli.py` — Inline `DefaultAdapters(...)` construction includes a fake Codex provider for CLI launch-path tests.
- `tests/test_integration.py` — Inline `DefaultAdapters(...)` construction includes a fake Codex provider for integration tests.
