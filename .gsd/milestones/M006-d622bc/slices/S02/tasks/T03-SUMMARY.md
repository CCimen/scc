---
id: T03
parent: S02
milestone: M006-d622bc
key_files:
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/ports/models.py
  - src/scc_cli/application/start_session.py
  - tests/test_oci_sandbox_runtime.py
  - tests/test_application_start_session.py
key_decisions:
  - _build_exec_cmd branches on agent_argv presence to avoid appending Claude-specific --dangerously-skip-permissions to non-Claude providers
  - _build_create_cmd resolves volume_name and config_dirname from spec with empty-string fallback to existing constants
  - _PROVIDER_DATA_VOLUME and _PROVIDER_CONFIG_DIR dicts in start_session.py parallel _PROVIDER_IMAGE_REF pattern
duration: 
verification_result: passed
completed_at: 2026-04-04T23:50:12.185Z
blocker_discovered: false
---

# T03: Made OCI runtime exec command and credential volume mount provider-aware with backward-compat fallbacks and 15 new tests

**Made OCI runtime exec command and credential volume mount provider-aware with backward-compat fallbacks and 15 new tests**

## What Happened

Added data_volume and config_dir fields to SandboxSpec. Extended _build_sandbox_spec with _PROVIDER_DATA_VOLUME and _PROVIDER_CONFIG_DIR dicts mapping provider_id to volume names and config directories. Updated _build_exec_cmd to use spec.agent_argv when non-empty (avoiding Claude-specific --dangerously-skip-permissions for Codex), with fallback to AGENT_NAME. Updated _build_create_cmd to resolve volume_name and config_dirname from spec fields with empty-string fallback to existing constants. Added 15 new tests covering exec cmd, create cmd, and start_session population paths.

## Verification

All 5 verification gates passed: 81 targeted tests pass, ruff check clean on 3 source files, mypy clean on 3 source files, full suite 4568 passed with 0 failures, and slice-level contract tests still pass (13 tests).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py -v` | 0 | ✅ pass | 7800ms |
| 2 | `uv run ruff check src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` | 0 | ✅ pass | 4300ms |
| 3 | `uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` | 0 | ✅ pass | 4300ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 71300ms |
| 5 | `uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v` | 0 | ✅ pass | 6900ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/ports/models.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_oci_sandbox_runtime.py`
- `tests/test_application_start_session.py`
