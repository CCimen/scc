---
id: T02
parent: S02
milestone: M006-d622bc
key_files:
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/ports/models.py
  - tests/test_provider_dispatch.py
  - tests/test_application_start_session.py
  - tests/test_codex_agent_runner.py
key_decisions:
  - agent_argv stored as list[str] on SandboxSpec converted from AgentLaunchSpec tuple
  - agent_launch_spec built before sandbox_spec to enable argv flow
  - _PROVIDER_IMAGE_REF dict in start_session.py for provider→image mapping with claude fallback
duration: 
verification_result: passed
completed_at: 2026-04-04T23:43:20.091Z
blocker_discovered: false
---

# T02: Wired CodexAgentRunner into provider dispatch table, threaded runtime_info from probe, and made image selection and agent_argv provider-aware with 10 new tests

**Wired CodexAgentRunner into provider dispatch table, threaded runtime_info from probe, and made image selection and agent_argv provider-aware with 10 new tests**

## What Happened

Extended _PROVIDER_DISPATCH to include agent_runner per-provider, threaded runtime_info from runtime_probe.probe() into StartSessionDependencies, made _build_sandbox_spec select image by provider_id via _PROVIDER_IMAGE_REF mapping, added agent_argv field to SandboxSpec, and reordered prepare_start_session to build agent_launch_spec before sandbox_spec so argv flows through. Fixed pre-existing ruff import sort in test_codex_agent_runner.py.

## Verification

All 5 verification gates passed: targeted test files (45 + 13 passed), ruff check clean, mypy clean, full suite 4554 passed with 0 failures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_dispatch.py tests/test_application_start_session.py -v` | 0 | ✅ pass | 1500ms |
| 2 | `uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v` | 0 | ✅ pass | 1200ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 5000ms |
| 4 | `uv run mypy src/scc_cli/commands/launch/dependencies.py src/scc_cli/application/start_session.py src/scc_cli/ports/models.py` | 0 | ✅ pass | 75800ms |
| 5 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 69900ms |

## Deviations

Fixed pre-existing ruff I001 import sort in test_codex_agent_runner.py. Used resolve_destination_sets mock in unknown-provider test due to FakeAgentProvider using unregistered 'fake-core' destination set.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/ports/models.py`
- `tests/test_provider_dispatch.py`
- `tests/test_application_start_session.py`
- `tests/test_codex_agent_runner.py`
